"""Tests for the designated save contract (``SpecManager.save_spec_as``).

Pinned behavior:

* An unchanged copy of a spec with a *verifiable* hash is byte-for-byte
  identical to the source — hash and ``date_updated`` preserved.
* A copy never carries an unverifiable hash forward: without ``add_sha256``
  the hash line is dropped from the copy (source still untouched, bad hash
  and all); with ``add_sha256`` the copy gets a repaired, self-consistent
  stamp instead.
* Writes are atomic (temp file + ``os.replace``): existing permissions are
  carried over and no temp residue remains.
"""

import os
import re
from pathlib import Path

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.spec_manager import SpecManager

SAMPLE_SPEC = (
    Path(__file__).resolve().parents[1] / "sample-specs" / "RomanNexus-2026.2.yaml"
)

BAD_HASH = "deadbeef" * 8


def _load(tmp_path: Path, stale_hash: bool = False) -> tuple[SpecManager, Path]:
    """Load a copy of the sample spec, optionally with an unverifiable hash."""
    set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
    spec_file = tmp_path / "specs" / SAMPLE_SPEC.name
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    text = SAMPLE_SPEC.read_text()
    if stale_hash:
        text = re.sub(r"spec_sha256: \S+", f"spec_sha256: {BAD_HASH}", text)
        assert BAD_HASH in text
    spec_file.write_text(text)
    sm = SpecManager()
    assert sm.load_spec(spec_file), "failed to load sample spec"
    return sm, spec_file


class TestCopyHashHygiene:
    def test_valid_hash_copy_preserves_hash_and_date(self, tmp_path):
        sm, spec_file = _load(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert sm.save_spec(out_dir) is True

        out_file = out_dir / spec_file.name
        # byte-for-byte identical: the verifiable hash and date carry over
        assert out_file.read_bytes() == spec_file.read_bytes()

    def test_stale_hash_stripped_from_copy_source_untouched(self, tmp_path):
        sm, spec_file = _load(tmp_path, stale_hash=True)
        before = spec_file.read_bytes()
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert sm.save_spec(out_dir) is True

        out_file = out_dir / spec_file.name
        # the unverifiable hash never propagates into the copy...
        assert "spec_sha256" not in out_file.read_text()
        # ...and the source file is never mutated for cleanliness
        assert spec_file.read_bytes() == before
        assert BAD_HASH in spec_file.read_text()
        assert sm.sha256 is None

    def test_copy_repair_when_hash_update_requested(self, tmp_path):
        sm, spec_file = _load(tmp_path, stale_hash=True)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert sm.save_spec(out_dir, add_sha256=True) is True

        out_file = out_dir / spec_file.name
        assert BAD_HASH not in out_file.read_text()
        # the copied spec's embedded hash must self-validate on reload
        sm2 = SpecManager()
        assert sm2.load_spec(out_file)
        assert sm2.validate_sha256() is True


class TestAtomicWrite:
    def test_existing_mode_preserved_and_no_residue(self, tmp_path):
        sm, spec_file = _load(tmp_path)
        os.chmod(spec_file, 0o640)
        sm.set_output_data("marker", "content-change")

        assert sm.save_spec_as(spec_file, add_sha256=True) is True

        # permission bits carried over across the atomic replace
        assert spec_file.stat().st_mode & 0o777 == 0o640
        # no temp-file residue left behind in the destination directory
        assert [p.name for p in spec_file.parent.iterdir()] == [spec_file.name]
