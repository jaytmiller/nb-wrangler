"""Tests for ``--spec-readonly`` and content-aware spec saving.

These tests load the real sample spec (which round-trips byte-exactly through
``SpecManager.to_string``) so the "unchanged = byte-for-byte no-op" contract
is verifiable.
"""

import shutil
from pathlib import Path

from nb_wrangler.cli import parse_args
from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.spec_manager import SpecManager

SAMPLE_SPEC = (
    Path(__file__).resolve().parents[1] / "sample-specs" / "RomanNexus-2026.2.yaml"
)


def _copy_sample_to(tmp_path: Path) -> Path:
    """Copy the sample spec under *tmp_path* and return the source Path."""
    spec_file = tmp_path / "sample-specs" / "RomanNexus-2026.2.yaml"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(SAMPLE_SPEC, spec_file)
    return spec_file


def _load_spec(tmp_path: Path, spec_readonly: bool = False) -> tuple[SpecManager, Path]:
    """Load a fresh copy of the sample spec into a SpecManager."""
    set_args_config(
        WranglerConfig(
            workflows=[],
            repos_dir=tmp_path / "repos",
            spec_readonly=spec_readonly,
        )
    )
    sm = SpecManager()
    spec_file = _copy_sample_to(tmp_path)
    assert sm.load_spec(spec_file), "failed to load sample spec"
    return sm, spec_file


def _change_content(sm: SpecManager) -> None:
    """Add a package so the in-memory content differs from the source."""
    sm._spec.setdefault("common_pip_packages", []).append("requests==2.31.0")


class TestSpecReadonlyFlag:
    def test_cli_parses_flag_true(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["nb-wrangler", "--spec-readonly"])
        assert parse_args().spec_readonly is True

    def test_cli_parses_flag_default_false(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["nb-wrangler"])
        assert parse_args().spec_readonly is False

    def test_config_field_default(self):
        assert WranglerConfig(workflows=[]).spec_readonly is False

    def test_config_field_set(self):
        assert WranglerConfig(workflows=[], spec_readonly=True).spec_readonly is True

    def test_from_args_maps_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["nb-wrangler", "--spec-readonly"])
        args = parse_args()
        assert WranglerConfig.from_args(args).spec_readonly is True


class TestContentAwareSaving:
    def test_unchanged_source_save_is_noop(self, tmp_path):
        sm, spec_file = _load_spec(tmp_path)
        original_bytes = spec_file.read_bytes()
        original_date = sm.system["date_updated"]
        original_hash = sm.sha256

        assert sm.save_spec_as(spec_file) is True

        # byte-for-byte no-op: file untouched and metadata stable
        assert spec_file.read_bytes() == original_bytes
        assert sm.system["date_updated"] == original_date
        assert sm.sha256 == original_hash

    def test_unchanged_copy_matches_source(self, tmp_path):
        sm, spec_file = _load_spec(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        assert sm.save_spec(out_dir) is True
        out_file = out_dir / "RomanNexus-2026.2.yaml"
        assert out_file.exists()
        # unchanged copy re-serializes the spec as-is
        assert out_file.read_bytes() == spec_file.read_bytes()

    def test_content_change_updates_date_and_writes(self, tmp_path):
        sm, spec_file = _load_spec(tmp_path)
        original_date = sm.system["date_updated"]
        original_bytes = spec_file.read_bytes()
        _change_content(sm)

        assert sm.save_spec_as(spec_file) is True
        assert sm.system["date_updated"] != original_date
        assert spec_file.read_bytes() != original_bytes
        assert b"requests==2.31.0" in spec_file.read_bytes()

    def test_content_change_add_sha256_recomputes(self, tmp_path):
        sm, spec_file = _load_spec(tmp_path)
        _change_content(sm)
        assert sm.save_spec_as(spec_file, add_sha256=True) is True
        # embedded hash must be a valid, self-consistent value
        assert sm.sha256 is not None and len(sm.sha256) == 64
        assert sm.validate_sha256() is True

    def test_readonly_aborts_source_write_on_change(self, tmp_path):
        sm, spec_file = _load_spec(tmp_path, spec_readonly=True)
        original_bytes = spec_file.read_bytes()
        _change_content(sm)

        result = sm.save_spec_as(spec_file)
        assert result is False
        # source untouched after the refused write
        assert spec_file.read_bytes() == original_bytes

    def test_readonly_allows_unchanged_source_write(self, tmp_path):
        sm, spec_file = _load_spec(tmp_path, spec_readonly=True)
        # unchanged + source is a no-op even under --spec-readonly
        assert sm.save_spec_as(spec_file) is True
        assert sm.save_spec_as(spec_file, add_sha256=True) is True
        # still byte-for-byte untouched
        assert sm.save_spec_as(spec_file) is True


class TestReadonlyGuardIsSourceScoped:
    def test_copy_write_not_blocked_by_readonly(self, tmp_path):
        sm, spec_file = _load_spec(tmp_path, spec_readonly=True)
        _change_content(sm)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        # a copy (not the source) may be written even under --spec-readonly
        assert sm.save_spec(out_dir) is True
        assert (out_dir / "RomanNexus-2026.2.yaml").exists()

    def test_relative_and_absolute_source_same(self, tmp_path):
        sm, spec_file = _load_spec(tmp_path)
        # same file via an absolute path is still recognized as the source
        assert sm._readonly_source_write(spec_file.resolve()) is True
        assert sm._readonly_source_write(spec_file) is True
        other = tmp_path / "other.yaml"
        assert sm._readonly_source_write(other) is False
