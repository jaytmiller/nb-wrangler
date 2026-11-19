"""Tests for ``--spec-legacy-sha256``: mode-selectable spec_sha256 stamping.

Validation permanently accepts both digests (canonical and legacy); the
active mode decides which digest future stamps produce.  This lets specs
curated on the consolidated line stay validatable by nb-wrangler releases
that predate the canonical routine, and back.

Golden constants provenance: computed with the real 0.9.5 (``main``)
``SpecManager`` — ``sm.load_spec(file); sm.add_sha256()`` — against the
current on-disk sample specs (hash value irrelevant, it is blanked in the
hashed input).  The RomanNexus golden equals the pre-canonical shipped
hash (``f041f10a…``, reverted by commit 49a4dbf's re-stamp), confirming the
replica is byte-exact 0.9.x behavior.
"""

import re
import shutil
import sys
from pathlib import Path

from nb_wrangler import cli
from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.hubenv import env_spec
from nb_wrangler.spec_manager import (
    SpecManager,
    canonical_spec_sha256,
    legacy_spec_sha256,
)

SPEC_DIR = Path(__file__).resolve().parents[1] / "sample-specs"
ROMAN = SPEC_DIR / "RomanNexus-2026.2.yaml"
INLINE = SPEC_DIR / "inline-mamba-spec.yaml"

# sha256 as 0.9.x (main) computes it over the current sample file bytes
ROMAN_LEGACY_GOLDEN = "f041f10a2cdb74cd3fa2ce8fc477881e16e270bbe760eb077bcb2493951d54db"
INLINE_LEGACY_GOLDEN = (
    "ee03926e876887fc767312da018b1dba844b513fb455427911044476215bdc89"
)
# canonical digest shipped in the sample specs (commit 49a4dbf re-stamp)
ROMAN_CANONICAL = "f0d2471c00fe2e5e658902ee2c53eebcdecead65f6337ed4eb82a46684485843"


def _cfg(tmp_path: Path, legacy: bool = False) -> None:
    set_args_config(
        WranglerConfig(
            workflows=[], repos_dir=tmp_path / "repos", spec_legacy_hash=legacy
        )
    )


def _copy(spec: Path, tmp_path: Path) -> Path:
    dst = tmp_path / spec.name
    shutil.copy(spec, dst)
    return dst


def _hash_line(text: str) -> str:
    m = re.search(r"(?m)^\s*spec_sha256: (\S+)\s*$", text)
    assert m, "spec_sha256 line not found"
    return m.group(1)


def _set_hash_line(spec_file: Path, value: str) -> None:
    text = spec_file.read_text()
    new_text, n = re.subn(
        r"(?m)^(\s*spec_sha256:).*$", lambda m: m.group(1) + f" {value}", text, count=1
    )
    assert n == 1
    spec_file.write_text(new_text)


class TestModeStamping:
    def test_legacy_mode_stamps_0_9_x_golden(self, tmp_path):
        """--spec-legacy-sha256 produces the byte-exact 0.9.x digest."""
        _cfg(tmp_path, legacy=True)
        sm = SpecManager()
        assert sm.load_spec(str(_copy(ROMAN, tmp_path)))
        assert sm.add_sha256() == ROMAN_LEGACY_GOLDEN

    def test_legacy_mode_two_document_golden(self, tmp_path):
        _cfg(tmp_path, legacy=True)
        sm = SpecManager()
        assert sm.load_spec(str(_copy(INLINE, tmp_path)))
        assert sm.add_sha256() == INLINE_LEGACY_GOLDEN

    def test_default_mode_stamps_canonical_idempotently(self, tmp_path):
        """Default mode re-stamps to the canonical digest already shipped."""
        _cfg(tmp_path)
        sm = SpecManager()
        assert sm.load_spec(str(_copy(ROMAN, tmp_path)))
        assert sm.sha256 == ROMAN_CANONICAL
        assert sm.add_sha256() == ROMAN_CANONICAL != ROMAN_LEGACY_GOLDEN


class TestDualAcceptance:
    def test_canonical_hash_validates_under_legacy_mode(self, tmp_path):
        _cfg(tmp_path, legacy=True)
        sm = SpecManager()
        assert sm.load_spec(str(_copy(ROMAN, tmp_path)))
        assert sm.validate_sha256()

    def test_legacy_hash_validates_under_default_mode(self, tmp_path):
        _cfg(tmp_path)
        spec_file = _copy(ROMAN, tmp_path)
        _set_hash_line(spec_file, ROMAN_LEGACY_GOLDEN)
        sm = SpecManager()
        assert sm.load_spec(str(spec_file))
        assert sm.validate_sha256()


class TestModeSwitching:
    def test_update_converts_canonical_to_legacy(self, tmp_path):
        """Unchanged content + add_sha256 under legacy mode re-stamps."""
        _cfg(tmp_path, legacy=True)
        spec_file = _copy(ROMAN, tmp_path)
        sm = SpecManager()
        assert sm.load_spec(str(spec_file))
        assert sm.save_spec(spec_file.parent, add_sha256=True)
        assert _hash_line(spec_file.read_text()) == ROMAN_LEGACY_GOLDEN

    def test_update_converts_legacy_to_canonical(self, tmp_path):
        _cfg(tmp_path)
        spec_file = _copy(ROMAN, tmp_path)
        _set_hash_line(spec_file, ROMAN_LEGACY_GOLDEN)
        sm = SpecManager()
        assert sm.load_spec(str(spec_file))
        assert sm.save_spec(spec_file.parent, add_sha256=True)
        assert _hash_line(spec_file.read_text()) == ROMAN_CANONICAL

    def test_mode_matching_save_is_noop(self, tmp_path):
        """Hash already in active mode + unchanged content: byte-for-byte no-op."""
        _cfg(tmp_path)
        spec_file = _copy(ROMAN, tmp_path)
        before = spec_file.read_text()
        sm = SpecManager()
        assert sm.load_spec(str(spec_file))
        assert sm.save_spec(spec_file.parent, add_sha256=True)
        assert spec_file.read_text() == before


class TestHubenvParity:
    """hubenv seed stamping honors the same mode flag."""

    _VIEW = {
        "name": "demo",
        "channels": ["conda-forge"],
        "dependencies": ["python=3.12", "numpy=1.26"],
    }

    def test_hubenv_legacy_stamp_is_legacy_digest(self, tmp_path):
        _cfg(tmp_path, legacy=True)
        text = env_spec.to_wrangler_yaml("demo", dict(self._VIEW))
        assert _hash_line(text) == legacy_spec_sha256(text)

    def test_hubenv_default_stamp_is_canonical(self, tmp_path):
        _cfg(tmp_path)
        text = env_spec.to_wrangler_yaml("demo", dict(self._VIEW))
        spec_file = tmp_path / "nbw-wrangler-spec.yaml"
        spec_file.write_text(text)
        sm = SpecManager()
        assert sm.load_spec(str(spec_file))
        assert _hash_line(text) == canonical_spec_sha256(sm._spec, sm.inline_mamba_spec)


class TestCliWiring:
    def test_flag_parses_and_defaults_false(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["nbw", "spec.yaml"])
        assert cli.parse_args().spec_legacy_hash is False
        monkeypatch.setattr(sys, "argv", ["nbw", "--spec-legacy-sha256", "spec.yaml"])
        assert cli.parse_args().spec_legacy_hash is True
