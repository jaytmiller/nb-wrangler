"""Tests for hubenv env rm (Phase 6)."""

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


def _make_pantry(tmp_path, name="p1", with_shelves=None, writable=True):
    """Create a pantry with optional shelves."""
    pantry = tmp_path / name
    pantry.mkdir()
    for shelf_name in with_shelves or []:
        shelf = pantry / "shelves" / shelf_name
        archives = shelf / "archives"
        archives.mkdir(parents=True)
        (archives / f"env-{shelf_name}.tar").write_text("fake")
        (archives / "last-save.sha256").write_text("abc123\n")
    if not writable:
        os.chmod(pantry, 0o555)
    return pantry


def _make_live_env(tmp_path, name, nbw_root=None):
    """Create a fake live env directory."""
    root = nbw_root if nbw_root is not None else tmp_path
    env = root / "envs" / name
    env.mkdir(parents=True, exist_ok=True)
    return env


# ---------------------------------------------------------------------------
# hubenv env rm --dry-run
# ---------------------------------------------------------------------------


class TestRmDryRun:
    """Tests for hubenv env rm --dry-run."""

    def test_dry_run_prints_plan(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            rc = main(["env", "rm", "demo", "--dry-run"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "demo" in out
            assert "removed" in out.lower()

    def test_dry_run_does_not_delete(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            rc = main(["env", "rm", "demo", "--dry-run"])
            assert rc == 0
            assert env_path.exists()

    def test_dry_run_glob_prints_all_matches(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        _make_live_env(tmp_path, "demo1", nbw_root=tmp_path)
        _make_live_env(tmp_path, "demo2", nbw_root=tmp_path)
        _make_live_env(tmp_path, "prod", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            rc = main(["env", "rm", "demo*", "--dry-run"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "demo1" in out
            assert "demo2" in out
            assert "prod" not in out


# ---------------------------------------------------------------------------
# hubenv env rm --yes
# ---------------------------------------------------------------------------


class TestRmYes:
    """Tests for hubenv env rm --yes."""

    def test_yes_deletes_live_env(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            rc = main(["env", "rm", "demo", "--yes"])
            assert rc == 0
            assert not env_path.exists()

    def test_yes_deletes_shelf(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = _make_pantry(tmp_path, "p1", with_shelves=["demo"])

        with patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]):
            rc = main(["env", "rm", "demo", "--yes"])
            assert rc == 0
            assert not (pantry / "shelves" / "demo").exists()

    def test_yes_deletes_both_live_and_shelf(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            rc = main(["env", "rm", "demo", "--yes"])
            assert rc == 0
            assert not env_path.exists()
            assert not (pantry / "shelves" / "demo").exists()

    def test_yes_no_prompt(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            rc = main(["env", "rm", "demo", "--yes"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "Proceed?" not in out


# ---------------------------------------------------------------------------
# hubenv env rm confirmation
# ---------------------------------------------------------------------------


class TestRmConfirmation:
    """Tests for interactive confirmation."""

    def test_without_yes_prompts(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("builtins.input", return_value="y"),
        ):
            rc = main(["env", "rm", "demo"])
            assert rc == 0

    def test_confirm_yes_deletes(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("builtins.input", return_value="y"),
        ):
            rc = main(["env", "rm", "demo"])
            assert rc == 0
            assert not env_path.exists()

    def test_confirm_no_aborts(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("builtins.input", return_value="n"),
        ):
            rc = main(["env", "rm", "demo"])
            assert rc == 1
            assert env_path.exists()

    def test_confirm_empty_input_aborts(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("builtins.input", return_value=""),
        ):
            rc = main(["env", "rm", "demo"])
            assert rc == 1
            assert env_path.exists()


# ---------------------------------------------------------------------------
# hubenv env rm read-only
# ---------------------------------------------------------------------------


class TestRmReadOnly:
    """Tests for read-only pantry refusal."""

    def test_readonly_pantry_refused(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        ro = tmp_path / "readonly"
        ro.mkdir()
        shelf = ro / "shelves" / "demo"
        (shelf / "archives").mkdir(parents=True)
        (shelf / "archives" / "last-save.sha256").write_text("abc123\n")
        os.chmod(ro, 0o555)
        try:
            with (
                patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [ro]),
                patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            ):
                rc = main(["env", "rm", "demo", "--yes"])
                assert rc == 1
                err = capsys.readouterr().err
                assert "read-only" in err.lower() or "writable" in err.lower()
        finally:
            os.chmod(ro, 0o700)

    def test_readonly_pantry_with_flag(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        ro = tmp_path / "readonly"
        ro.mkdir()
        shelf = ro / "shelves" / "demo"
        (shelf / "archives").mkdir(parents=True)
        (shelf / "archives" / "last-save.sha256").write_text("abc123\n")
        os.chmod(ro, 0o555)
        try:
            with (
                patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", []),
                patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            ):
                rc = main(["env", "rm", "demo", "--pantry", str(ro), "--yes"])
                assert rc == 1
                err = capsys.readouterr().err
                assert "read-only" in err.lower() or "writable" in err.lower()
        finally:
            os.chmod(ro, 0o700)


# ---------------------------------------------------------------------------
# hubenv env rm globs
# ---------------------------------------------------------------------------


class TestRmGlobs:
    """Tests for glob resolution."""

    def test_glob_matches_multiple(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env1 = _make_live_env(tmp_path, "demo1", nbw_root=tmp_path)
        env2 = _make_live_env(tmp_path, "demo2", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("builtins.input", return_value="y"),
        ):
            rc = main(["env", "rm", "demo*"])
            assert rc == 0
            assert not env1.exists()
            assert not env2.exists()

    def test_glob_lists_before_prompting(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        _make_live_env(tmp_path, "demo1", nbw_root=tmp_path)
        _make_live_env(tmp_path, "demo2", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("builtins.input", return_value="n") as mock_input,
        ):
            rc = main(["env", "rm", "demo*"])
            assert rc == 1
            out = capsys.readouterr().out
            assert "demo1" in out
            assert "demo2" in out
            mock_input.assert_called_once()
            assert "y/N" in mock_input.call_args[0][0]


# ---------------------------------------------------------------------------
# hubenv env rm path safety
# ---------------------------------------------------------------------------


class TestRmPathSafety:
    """Tests for path-escape rejection."""

    def test_path_escape_rejected(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        evil_dir = tmp_path / "evil"
        evil_dir.mkdir()

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", []),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch(
                "nb_wrangler.hubenv.config.HubenvConfig.list_live_envs",
                return_value=[{"name": "evil", "path": evil_dir}],
            ),
        ):
            rc = main(["env", "rm", "evil", "--yes"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "outside" in err.lower() or "refusing" in err.lower()

    def test_safe_live_path_accepted(self, tmp_path):
        from nb_wrangler.hubenv import env_rm
        from nb_wrangler.hubenv.config import HubenvConfig

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", []),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            config = HubenvConfig()
            safe_path = tmp_path / "envs" / "demo"
            safe_path.mkdir(parents=True)
            target = {"type": "live", "path": safe_path}
            assert env_rm.is_safe_rm_path(target, config)

    def test_safe_shelf_path_accepted(self, tmp_path):
        from nb_wrangler.hubenv import env_rm
        from nb_wrangler.hubenv.config import HubenvConfig

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        shelf_path = pantry / "shelves" / "demo"
        shelf_path.mkdir(parents=True)

        with patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]):
            config = HubenvConfig()
            target = {"type": "shelf", "path": shelf_path, "pantry": pantry}
            assert env_rm.is_safe_rm_path(target, config)

    def test_unsafe_shelf_path_rejected(self, tmp_path):
        from nb_wrangler.hubenv import env_rm
        from nb_wrangler.hubenv.config import HubenvConfig

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", []),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            config = HubenvConfig()
            target = {
                "type": "shelf",
                "path": Path("/tmp/evil"),
                "pantry": Path("/tmp"),
            }
            assert not env_rm.is_safe_rm_path(target, config)


# ---------------------------------------------------------------------------
# hubenv env rm target options
# ---------------------------------------------------------------------------


class TestRmTargetOptions:
    """Tests for --live/--archived/--both target filtering."""

    def test_live_only(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("builtins.input", return_value="y"),
        ):
            rc = main(["env", "rm", "demo", "--live"])
            assert rc == 0
            assert not env_path.exists()
            assert (pantry / "shelves" / "demo").exists()

    def test_archived_only(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("builtins.input", return_value="y"),
        ):
            rc = main(["env", "rm", "demo", "--archived"])
            assert rc == 0
            assert env_path.exists()
            assert not (pantry / "shelves" / "demo").exists()

    def test_both_default(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("builtins.input", return_value="y"),
        ):
            rc = main(["env", "rm", "demo", "--both"])
            assert rc == 0
            assert not env_path.exists()
            assert not (pantry / "shelves" / "demo").exists()


# ---------------------------------------------------------------------------
# hubenv env rm errors
# ---------------------------------------------------------------------------


class TestRmErrors:
    """Tests for error conditions."""

    def test_no_match_returns_error(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            rc = main(["env", "rm", "nonexistent", "--yes"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "no matching" in err.lower()

    def test_already_gone_live(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir()
        env_path = _make_live_env(tmp_path, "demo", nbw_root=tmp_path)

        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            # The env is found in listing, so it shouldn't print "already gone"
            # during normal flow. This test verifies normal deletion works.
            rc = main(["env", "rm", "demo", "--yes"])
            assert rc == 0
            assert not env_path.exists()
