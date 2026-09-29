"""Tests for hubenv env ensure / register / unregister (Phase 7)."""

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
    shelf = pantry / "shelves" / name / "archives"
    shelf.mkdir(parents=True)
    if with_can:
        (shelf / f"env-{name}.tar").write_text("fake archive")
    if save_hash:
        (shelf / "last-save.sha256").write_text(save_hash + "\n")
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


def _patch_unregister_env(return_value=True):
    """Patch EnvironmentManager.unregister_environment."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.unregister_environment",
        return_value=return_value,
    )


def _patch_env_exists(exists=True):
    """Patch EnvironmentManager.environment_exists."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.environment_exists",
        return_value=exists,
    )


# ---------------------------------------------------------------------------
# ensure
# ---------------------------------------------------------------------------


class TestEnsure:
    """Tests for hubenv env ensure."""

    def test_ensure_live_env_noop(self, tmp_path, capsys):
        """When a live env exists, ensure is a no-op."""
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_env_exists(True),
        ):
            rc = main(["env", "ensure", "demo"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "already live" in out
            assert "export NBW_ACTIVE_ENV=demo" in out

    def test_ensure_archive_restores(self, tmp_path, capsys):
        """When only an archive exists, ensure restores it."""
        from nb_wrangler.hubenv.cli import main

        pantry = _make_pantry(tmp_path, save_hash="abc123")

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_env_exists(False),
            _patch_unpack_env(True),
            _patch_register_env(True),
        ):
            rc = main(["env", "ensure", "demo"])
            assert rc == 0

    def test_ensure_neither_live_nor_archive_errors(self, tmp_path, capsys):
        """When neither live env nor archive exists, ensure errors."""
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_env_exists(False),
        ):
            rc = main(["env", "ensure", "demo"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "no live environment and no archive" in err.lower()
            assert "hubenv env create" in err.lower()

    def test_ensure_is_non_interactive(self, tmp_path, capsys):
        """ensure must never prompt — even with no stdin."""
        from nb_wrangler.hubenv.cli import main

        pantry = _make_pantry(tmp_path, save_hash="abc123")

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_env_exists(False),
            _patch_unpack_env(True),
            _patch_register_env(True),
        ):
            rc = main(["env", "ensure", "demo"])
            assert rc == 0

    def test_ensure_dry_run(self, tmp_path, capsys):
        """ensure --dry-run prints plan without executing."""
        from nb_wrangler.hubenv.cli import main

        pantry = _make_pantry(tmp_path, save_hash="abc123")

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_env_exists(False),
            _patch_unpack_env(True) as mock_unpack,
            _patch_register_env(True),
        ):
            rc = main(["env", "ensure", "demo", "--dry-run"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "dry-run" in out.lower()
            mock_unpack.assert_not_called()


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for hubenv env register."""

    def test_register_calls_register_environment(self, tmp_path, capsys):
        """register calls em.register_environment with env name as display."""
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_register_env(True) as mock_reg,
        ):
            rc = main(["env", "register", "demo"])
            assert rc == 0
            mock_reg.assert_called_once_with("demo", "demo", {})
            out = capsys.readouterr().out
            assert "Registered" in out

    def test_register_with_display_name(self, tmp_path, capsys):
        """register --display-name uses the given display name."""
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_register_env(True) as mock_reg,
        ):
            rc = main(["env", "register", "demo", "--display-name", "My Env"])
            assert rc == 0
            mock_reg.assert_called_once_with("demo", "My Env", {})

    def test_register_dry_run(self, tmp_path, capsys):
        """register --dry-run prints plan without calling register."""
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_register_env(True) as mock_reg,
        ):
            rc = main(["env", "register", "demo", "--dry-run"])
            assert rc == 0
            mock_reg.assert_not_called()
            out = capsys.readouterr().out
            assert "dry-run" in out.lower()

    def test_register_failure_returns_error(self, tmp_path, capsys):
        """register failure returns non-zero."""
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_register_env(False),
        ):
            rc = main(["env", "register", "demo"])
            assert rc == 1


# ---------------------------------------------------------------------------
# unregister
# ---------------------------------------------------------------------------


class TestUnregister:
    """Tests for hubenv env unregister."""

    def test_unregister_calls_unregister_environment(self, tmp_path, capsys):
        """unregister calls em.unregister_environment."""
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_unregister_env(True) as mock_unreg,
        ):
            rc = main(["env", "unregister", "demo"])
            assert rc == 0
            mock_unreg.assert_called_once_with("demo")
            out = capsys.readouterr().out
            assert "Unregistered" in out

    def test_unregister_tolerates_missing_kernel(self, tmp_path, capsys):
        """unregister succeeds even if kernel doesn't exist (warning logged)."""
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_unregister_env(True) as mock_unreg,
        ):
            rc = main(["env", "unregister", "nonexistent"])
            assert rc == 0
            mock_unreg.assert_called_once_with("nonexistent")

    def test_unregister_dry_run(self, tmp_path, capsys):
        """unregister --dry-run prints plan without calling unregister."""
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            _patch_unregister_env(True) as mock_unreg,
        ):
            rc = main(["env", "unregister", "demo", "--dry-run"])
            assert rc == 0
            mock_unreg.assert_not_called()
            out = capsys.readouterr().out
            assert "dry-run" in out.lower()
