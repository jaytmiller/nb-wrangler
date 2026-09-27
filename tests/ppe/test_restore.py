"""Tests for ppe env restore (Phase 3)."""

import os
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


def _make_pantry(tmp_path, name="demo", with_can=True, save_hash=None):
    """Create a pantry with a shelf and optional can + save-hash."""
    pantry = tmp_path / "pantry"
    pantry.mkdir()
    shelf = pantry / "shelves" / name
    archives = shelf / "archives"
    archives.mkdir(parents=True)
    if with_can:
        can = archives / f"env-{name}.tar"
        can.write_text("fake archive content")
    if save_hash:
        (archives / "last-save.sha256").write_text(save_hash + "\n")
    return pantry


def _patch_unpack_env(return_value=True):
    """Patch NbwShelf.unpack_environment."""
    return patch(
        "nb_wrangler.pantry.NbwShelf.unpack_environment",
        return_value=return_value,
    )


def _patch_register_env(return_value=True):
    """Patch EnvironmentManager.register_environment."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.register_environment",
        return_value=return_value,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestRestoreHappyPath:
    """Tests for basic ppe env restore functionality."""

    def test_restore_prints_exports(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path)

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_unpack_env(True),
            _patch_register_env(True),
        ):
            rc = main(["env", "restore", "demo"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "export NBW_ACTIVE_ENV=demo" in out

    def test_restore_calls_unpack(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path)

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_unpack_env(True) as mock_unpack,
            _patch_register_env(True) as mock_reg,
        ):
            rc = main(["env", "restore", "demo"])
            assert rc == 0
            mock_unpack.assert_called_once_with("demo", "demo", ".tar")
            mock_reg.assert_called_once()

    def test_restore_no_can_returns_error(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path, with_can=False)

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]):
            rc = main(["env", "restore", "demo"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "no archive" in err.lower()

    def test_restore_no_shelf_returns_error(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]):
            rc = main(["env", "restore", "demo"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "no shelf" in err.lower()

    def test_restore_unpack_failure_returns_error(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path)

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            _patch_unpack_env(False),
        ):
            rc = main(["env", "restore", "demo"])
            assert rc == 1


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestRestoreIdempotency:
    """Tests for restore idempotency (save-hash == restore-hash skip)."""

    def test_idempotent_skip_when_hashes_match(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path, save_hash="abc123")

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.ppe.config.NBW_ROOT", tmp_path),
        ):
            # Pre-create restore hash matching save hash
            restore_hash_file = tmp_path / ".ppe-restore" / "demo.sha256"
            restore_hash_file.parent.mkdir(parents=True)
            restore_hash_file.write_text("abc123\n")

            with _patch_unpack_env(True) as mock_unpack:
                rc = main(["env", "restore", "demo"])
                assert rc == 0
                out = capsys.readouterr().out
                assert "idempotent skip" in out
                mock_unpack.assert_not_called()

    def test_force_re_unpacks_even_if_hashes_match(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path, save_hash="abc123")

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.ppe.config.NBW_ROOT", tmp_path),
        ):
            restore_hash_file = tmp_path / ".ppe-restore" / "demo.sha256"
            restore_hash_file.parent.mkdir(parents=True)
            restore_hash_file.write_text("abc123\n")

            with _patch_unpack_env(True) as mock_unpack:
                rc = main(["env", "restore", "demo", "--force"])
                assert rc == 0
                mock_unpack.assert_called_once()

    def test_restore_records_restore_hash(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path, save_hash="def456")

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.ppe.config.NBW_ROOT", tmp_path),
            _patch_unpack_env(True),
            _patch_register_env(True),
        ):
            rc = main(["env", "restore", "demo"])
            assert rc == 0

        hash_file = tmp_path / ".ppe-restore" / "demo.sha256"
        assert hash_file.exists()
        assert hash_file.read_text().strip() == "def456"

    def test_no_hashes_does_not_skip(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path, save_hash="abc123")

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.ppe.config.NBW_ROOT", tmp_path),
            _patch_unpack_env(True) as mock_unpack,
            _patch_register_env(True),
        ):
            rc = main(["env", "restore", "demo"])
            assert rc == 0
            mock_unpack.assert_called_once()


# ---------------------------------------------------------------------------
# Forced pantry
# ---------------------------------------------------------------------------


class TestRestoreForcedPantry:
    """Tests for the --pantry flag."""

    def test_forced_pantry_finds_shelf(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        forced = tmp_path / "forced"
        forced.mkdir()
        shelf = forced / "shelves" / "demo"
        shelf.mkdir(parents=True)
        (shelf / "archives").mkdir()
        (shelf / "archives" / "env-demo.tar").write_text("fake")

        with _patch_unpack_env(True), _patch_register_env(True):
            rc = main(["env", "restore", "demo", "--pantry", str(forced)])
            assert rc == 0

    def test_forced_pantry_missing_shelf(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        forced = tmp_path / "forced"
        forced.mkdir()

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [forced]):
            rc = main(["env", "restore", "demo", "--pantry", str(forced)])
            assert rc == 1
            err = capsys.readouterr().err
            assert "no shelf" in err.lower()


# ---------------------------------------------------------------------------
# Multi-match error
# ---------------------------------------------------------------------------


class TestRestoreMultiMatch:
    """Tests for multi-match error handling."""

    def test_multi_match_without_pantry_errors(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry1 = tmp_path / "pantry1"
        pantry2 = tmp_path / "pantry2"
        for p in [pantry1, pantry2]:
            shelf = p / "shelves" / "demo"
            (shelf / "archives").mkdir(parents=True)

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry1, pantry2]):
            rc = main(["env", "restore", "demo"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "multiple pantries" in err.lower()
            assert str(pantry1) in err
            assert str(pantry2) in err

    def test_multi_match_with_pantry_selects_one(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry1 = tmp_path / "pantry1"
        pantry2 = tmp_path / "pantry2"
        for p in [pantry1, pantry2]:
            shelf = p / "shelves" / "demo"
            (shelf / "archives").mkdir(parents=True)
            (shelf / "archives" / "env-demo.tar").write_text("fake")

        # Use --pantry to select pantry1
        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry1, pantry2]),
            _patch_unpack_env(True),
            _patch_register_env(True),
        ):
            rc = main(["env", "restore", "demo", "--pantry", str(pantry1)])
            assert rc == 0


# ---------------------------------------------------------------------------
# At-boot snippet
# ---------------------------------------------------------------------------


class TestRestoreAtBoot:
    """Tests for --at-boot snippet writing."""

    def test_at_boot_writes_snippet(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path)
        home = tmp_path / "home"
        home.mkdir()

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            patch.dict(os.environ, {"HOME": str(home)}),
            _patch_unpack_env(True),
            _patch_register_env(True),
        ):
            rc = main(["env", "restore", "demo", "--at-boot"])

        assert rc == 0
        snippet = home / ".ppe" / "env-demo.sh"
        assert snippet.exists()
        content = snippet.read_text()
        assert "NBW_ACTIVE_ENV" in content
        assert "ppe env ensure demo" in content

    def test_at_boot_appends_to_bashrc(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path)
        home = tmp_path / "home"
        home.mkdir()
        bashrc = home / ".bashrc"
        bashrc.write_text("# existing content\n")

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            patch.dict(os.environ, {"HOME": str(home)}),
            _patch_unpack_env(True),
            _patch_register_env(True),
        ):
            rc = main(["env", "restore", "demo", "--at-boot"])

        assert rc == 0
        content = bashrc.read_text()
        assert "source ~/.ppe/env-demo.sh" in content
        assert content.count("source ~/.ppe/env-demo.sh") == 1

    def test_at_boot_idempotent_no_duplicate(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        pantry = _make_pantry(tmp_path)
        home = tmp_path / "home"
        home.mkdir()
        bashrc = home / ".bashrc"
        bashrc.write_text("# existing\n# Added by ppe\nsource ~/.ppe/env-demo.sh\n")

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry]),
            patch.dict(os.environ, {"HOME": str(home)}),
            _patch_unpack_env(True),
            _patch_register_env(True),
        ):
            rc = main(["env", "restore", "demo", "--at-boot"])

        assert rc == 0
        content = bashrc.read_text()
        assert content.count("source ~/.ppe/env-demo.sh") == 1
