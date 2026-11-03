"""Regression tests for the canonical spec_sha256 routine (single hash algorithm).

The latent instability this locks down (docs/combine-branches.md §5): the hash
input must not depend on in-process dump history (ruamel comment state drifting
across dumps/copies) nor on whether the ``spec_sha256`` key is absent vs
present-but-blank.  Both nbw stamping/validation and hubenv's seed stamping go
through ``canonical_spec_sha256``; old on-disk hashes are accepted for one
release of migration via the legacy file-derived candidate.
"""

import copy
import re
import shutil
from pathlib import Path

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.spec_manager import (
    SpecManager,
    canonical_spec_sha256,
    legacy_spec_sha256,
)

SPEC_DIR = Path(__file__).resolve().parents[1] / "sample-specs"
COMMENTS_SPEC = SPEC_DIR / "RomanNexus-2026.2.yaml"  # YAML comments present
TWO_DOC_SPEC = SPEC_DIR / "inline-mamba-spec.yaml"  # second (mamba) document


def _set_config(tmp_path: Path) -> None:
    set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))


def _set_hash_line(spec_file: Path, value: str) -> None:
    text = spec_file.read_text()
    new_text, n = re.subn(
        r"(?m)^(?P<i>\s*spec_sha256:).*$",
        lambda m: m.group("i") + f" {value}",
        text,
        count=1,
    )
    assert n == 1, f"spec_sha256 line not found in {spec_file}"
    spec_file.write_text(new_text)


class TestCanonicalStability:
    def test_fresh_load_equals_hash_after_prior_serializations(self, tmp_path):
        """A just-loaded spec hashes the same after live/copy dumps in-process."""
        _set_config(tmp_path)
        pristine = SpecManager()
        assert pristine.load_spec(str(COMMENTS_SPEC))
        expected = canonical_spec_sha256(pristine._spec, pristine.inline_mamba_spec)

        sm = SpecManager()
        assert sm.load_spec(str(COMMENTS_SPEC))
        for _ in range(3):
            sm.to_string()  # live dump
            copy.deepcopy(sm._spec)  # copy dump
            sm._content_fp()  # fingerprint (blanks+restores the hash)
            copy.deepcopy(sm._spec)
        for _ in range(3):
            assert canonical_spec_sha256(sm._spec, sm.inline_mamba_spec) == expected

    def test_two_document_spec_stable(self, tmp_path):
        _set_config(tmp_path)
        sm = SpecManager()
        assert sm.load_spec(str(TWO_DOC_SPEC))
        assert sm.inline_mamba_spec is not None
        expected = canonical_spec_sha256(sm._spec, sm.inline_mamba_spec)
        for _ in range(3):
            sm.to_string()
            sm._content_fp()
            assert canonical_spec_sha256(sm._spec, sm.inline_mamba_spec) == expected

    def test_absent_vs_blank_hash_same_digest(self, tmp_path):
        _set_config(tmp_path)
        sm = SpecManager()
        assert sm.load_spec(str(COMMENTS_SPEC))
        system = sm._spec["system"]
        stored = system.pop("spec_sha256")
        try:
            absent_digest = canonical_spec_sha256(sm._spec, sm.inline_mamba_spec)
            system["spec_sha256"] = ""
            blank_digest = canonical_spec_sha256(sm._spec, sm.inline_mamba_spec)
        finally:
            system["spec_sha256"] = stored
        assert absent_digest == blank_digest

    def test_canonical_is_non_mutating(self, tmp_path):
        _set_config(tmp_path)
        sm = SpecManager()
        assert sm.load_spec(str(COMMENTS_SPEC))
        system = sm._spec["system"]
        stored = system["spec_sha256"]
        canonical_spec_sha256(sm._spec, sm.inline_mamba_spec)
        assert system["spec_sha256"] == stored  # live spec value untouched


class TestShippedSamples:
    def test_sample_specs_validate(self, tmp_path):
        """The shipped sample specs carry the canonical digest and validate."""
        _set_config(tmp_path)
        for spec_file in sorted(SPEC_DIR.glob("*.y*ml")):
            sm = SpecManager()
            assert sm.load_spec(str(spec_file)), spec_file
            if not sm._spec.get("system", {}).get("spec_sha256"):
                continue
            assert canonical_spec_sha256(sm._spec, sm.inline_mamba_spec) == (
                sm._spec["system"]["spec_sha256"]
            ), spec_file


class TestStampRoundTrip:
    def test_stamp_save_reload_validate(self, tmp_path):
        _set_config(tmp_path)
        spec_file = tmp_path / "spec.yaml"
        shutil.copy(COMMENTS_SPEC, spec_file)
        _set_hash_line(spec_file, "deadbeef" * 8)  # force a stale stored hash

        sm = SpecManager()
        assert sm.load_spec(str(spec_file))
        assert sm.save_spec_as(spec_file, add_sha256=True) is True

        reloaded = SpecManager()
        assert reloaded.load_spec(str(spec_file))
        assert reloaded.validate_sha256() is True
        assert reloaded._spec["system"]["spec_sha256"] == canonical_spec_sha256(
            reloaded._spec, reloaded.inline_mamba_spec
        )

    def test_legacy_candidate_accepted_one_release_grace(self, tmp_path):
        """A stored hash equal to the file-text legacy candidate still validates."""
        _set_config(tmp_path)
        spec_file = tmp_path / "spec.yaml"
        shutil.copy(TWO_DOC_SPEC, spec_file)
        _set_hash_line(spec_file, legacy_spec_sha256(spec_file.read_text()))

        sm = SpecManager()
        assert sm.load_spec(str(spec_file))
        assert sm.validate_sha256() is True
        assert sm._stored_hash_is_valid() is True


class TestRejection:
    def test_wrong_hash_rejected(self, tmp_path):
        _set_config(tmp_path)
        spec_file = tmp_path / "spec.yaml"
        shutil.copy(COMMENTS_SPEC, spec_file)
        _set_hash_line(spec_file, "f" * 64)

        sm = SpecManager()
        assert sm.load_spec(str(spec_file))
        assert sm.validate_sha256() is False
        assert sm._stored_hash_is_valid() is False


class TestHubenvParity:
    def test_hubenv_stamp_routine_matches_canonical(self):
        """hubenv's seed stamping must produce exactly the digest nbw validates."""
        from nb_wrangler.hubenv.env_spec import _compute_spec_sha256

        doc1 = {
            "image_spec_header": {"image_name": "demo"},
            "system": {"date_updated": "2026-01-01T00:00:00", "spec_sha256": ""},
        }
        doc2 = {"name": "demo", "channels": ["conda-forge"], "dependencies": []}
        _compute_spec_sha256(doc1, doc2)
        assert doc1["system"]["spec_sha256"] == canonical_spec_sha256(doc1, doc2)
