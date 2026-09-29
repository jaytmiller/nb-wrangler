"""Tests for ppe env save (Phase 2)."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from nb_wrangler.config import WranglerConfig, set_args_config


@pytest.fixture(autouse=True)
def _set_config(tmp_path):
    """Ensure a WranglerConfig is set for all tests."""
    set_args_config(
        WranglerConfig(
            workflows=[],
            spec_file="",
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
        )
    )


def _patch_env_path(env_path: Path):
    """Return a context manager that patches env_live_path to a fake path."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.env_live_path",
        return_value=env_path,
    )


def _patch_pack(return_value: bool = True):
    """Return a context manager that patches NbwShelf.pack_environment."""
    return patch(
        "nb_wrangler.pantry.NbwShelf.pack_environment",
        return_value=return_value,
    )


def _fake_hash():
    """Return a context manager that patches sha256_file to return a fake hash."""
    return patch("nb_wrangler.ppe.env_save.sha256_file", return_value="abc123def456")


class TestSaveDryRun:
    """Tests for ppe env save --dry-run."""

    def test_dry_run_prints_paths(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_env_path(env_dir),
        ):
            rc = main(["env", "save", "demo", "--dry-run"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "shelf:" in out
            assert "can:" in out
            assert "live env:" in out

    def test_dry_run_does_not_write(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_env_path(env_dir),
        ):
            rc = main(["env", "save", "demo", "--dry-run"])
            assert rc == 0
            # No archives directory should be created during dry-run
            assert not (pantry / "shelves" / "demo" / "archives").exists()

    def test_dry_run_forced_pantry(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        forced = tmp_path / "forced"
        forced.mkdir()
        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", []),
            _patch_env_path(env_dir),
        ):
            rc = main(["env", "save", "demo", "--pantry", str(forced), "--dry-run"])
            assert rc == 0
            out = capsys.readouterr().out
            assert str(forced) in out


class TestSaveActual:
    """Tests for actual ppe env save (with mocked pack routine)."""

    def test_save_writes_hash(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_env_path(env_dir),
            _patch_pack(True),
            _fake_hash(),
        ):
            rc = main(["env", "save", "demo"])
            assert rc == 0

        hash_file = pantry / "shelves" / "demo" / "archives" / "last-save.sha256"
        assert hash_file.exists()
        assert hash_file.read_text().strip() == "abc123def456"

    def test_save_prints_success_message(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_env_path(env_dir),
            _patch_pack(True),
            _fake_hash(),
        ):
            rc = main(["env", "save", "demo"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "Saved environment 'demo'" in out

    def test_save_pack_failure_returns_error(self, tmp_path):
        from nb_wrangler.ppe.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_env_path(env_dir),
            _patch_pack(False),
        ):
            rc = main(["env", "save", "demo"])
            assert rc == 1

    def test_save_force_overwrites_existing(self, tmp_path):
        from nb_wrangler.ppe.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        # Pre-create the can file
        can_path = pantry / "shelves" / "demo" / "archives" / "env-demo.tar"
        can_path.parent.mkdir(parents=True, exist_ok=True)
        can_path.write_text("old archive content")

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_env_path(env_dir),
            _patch_pack(True),
            _fake_hash(),
        ):
            rc = main(["env", "save", "demo", "--force"])
            assert rc == 0

    def test_save_refuses_existing_without_force(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        # Pre-create the can file
        can_path = pantry / "shelves" / "demo" / "archives" / "env-demo.tar"
        can_path.parent.mkdir(parents=True, exist_ok=True)
        can_path.write_text("old archive content")

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_env_path(env_dir),
        ):
            rc = main(["env", "save", "demo"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "already exists" in err
            assert "--force" in err


class TestSaveErrors:
    """Tests for ppe env save error conditions."""

    def test_readonly_pantry_returns_error(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        ro = tmp_path / "readonly"
        ro.mkdir()
        os.chmod(ro, 0o500)
        try:
            with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [ro]):
                rc = main(["env", "save", "demo"])
                assert rc == 1
                err = capsys.readouterr().err
                # Error should mention pantry/writable issue
                assert "pantry" in err.lower() or "writable" in err.lower()
        finally:
            os.chmod(ro, 0o700)

    def test_missing_env_returns_error(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        # No env directory created

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_env_path(tmp_path / "nonexistent"),
        ):
            rc = main(["env", "save", "demo"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "not found" in err.lower()

    def test_all_readonly_pantries_returns_error(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        ro = tmp_path / "readonly"
        ro.mkdir()
        os.chmod(ro, 0o500)
        try:
            with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [ro]):
                rc = main(["env", "save", "demo"])
                assert rc == 1
        finally:
            os.chmod(ro, 0o700)
