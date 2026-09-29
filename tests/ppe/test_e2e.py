"""End-to-end test for the full ppe MVP flow (Phase 11).

Tests the complete lifecycle:

    create -> save -> restore -> install -> relock -> rm

All heavy operations (mamba/micromamba env creation, tarball
pack/unpack, pip compile) are faked so the test is fast and needs no
network.  The test asserts state transitions at each step using a
temp ``NBW_ROOT``/``NBW_PANTRY``.
"""

from subprocess import CompletedProcess
from unittest.mock import patch
import os

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


@pytest.fixture
def _ppe_env(tmp_path):
    """Set up temp NBW_ROOT and NBW_PANTRY directories."""
    nbw_root = tmp_path / "nbw-root"
    nbw_root.mkdir()
    pantry_dir = tmp_path / "nbw-pantry"
    pantry_dir.mkdir()

    # Patch NBW_ROOT/NBW_PANTRY_DIRS for ppe.config, and NBW_MM for
    # EnvironmentManager.env_live_path (which reads NBW_MM at runtime via
    # the nbw_mm_dir property).
    with (
        patch("nb_wrangler.ppe.config.NBW_ROOT", nbw_root),
        patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [pantry_dir]),
        patch.dict(os.environ, {"NBW_MM": str(nbw_root)}),
        patch("nb_wrangler.constants.NBW_ROOT", nbw_root),
        patch("nb_wrangler.constants.NBW_MM", nbw_root),
        patch("nb_wrangler.pantry.NBW_PANTRY", pantry_dir),
    ):
        yield {"root": nbw_root, "pantry": pantry_dir}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _patch_create_env():
    """Mock create_environment to return True (env dir pre-created by test)."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.create_environment",
        return_value=True,
    )


def _patch_env_exists(return_value: bool = True):
    """Mock environment_exists."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.environment_exists",
        return_value=return_value,
    )


def _patch_pack(pantry_path, result=True):
    """Mock NbwShelf.pack_environment, creating a fake can file.

    Note: Mock side_effect does not receive the bound ``self``, so the
    function signature must match the call args without ``self``.
    """

    def _fake_pack(env_name, moniker, archive_format):
        can = (
            pantry_path
            / "shelves"
            / moniker
            / "archives"
            / ("env-" + moniker + archive_format)
        )
        can.parent.mkdir(parents=True, exist_ok=True)
        can.write_text("fake archive")
        return result

    return patch(
        "nb_wrangler.pantry.NbwShelf.pack_environment",
        side_effect=_fake_pack,
    )


def _patch_unpack(result=True):
    """Mock NbwShelf.unpack_environment."""
    return patch("nb_wrangler.pantry.NbwShelf.unpack_environment", return_value=result)


def _patch_register(result=True):
    """Mock EnvironmentManager.register_environment."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.register_environment",
        return_value=result,
    )


def _patch_env_run():
    """Mock env_run with a success CompletedProcess."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.env_run",
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )


def _patch_handle_result(result=True):
    """Mock handle_result."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.handle_result",
        return_value=result,
    )


def _patch_sha256(value="deadbeef"):
    """Mock sha256_file used by env save."""
    return patch("nb_wrangler.ppe.env_save.sha256_file", return_value=value)


def _patch_compile(packages):
    """Mock _compile_pip_packages to return pre-set package list."""
    return patch(
        "nb_wrangler.ppe.env_relock.compile_pip_packages", return_value=packages
    )


# ---------------------------------------------------------------------------
# The full e2e flow
# ---------------------------------------------------------------------------


class TestE2EFlow:
    """End-to-end: create -> save -> restore -> install -> relock -> rm."""

    def test_full_lifecycle(self, _ppe_env, capsys):
        from nb_wrangler.ppe.cli import main

        root = _ppe_env["root"]
        pantry = _ppe_env["pantry"]

        # --- Step 1: create ---
        env_dir = root / "envs" / "demo"
        env_dir.mkdir(parents=True)
        with _patch_create_env():
            rc = main(["env", "create", "--from-empty", "--name", "demo"])
        assert rc == 0
        assert env_dir.exists()

        # --- Step 2: save ---
        with (
            _patch_pack(pantry, True),
            _patch_sha256("abc123"),
        ):
            rc = main(["env", "save", "demo"])
        assert rc == 0

        # Shelf + can should exist in pantry
        shelf_path = pantry / "shelves" / "demo"
        can_path = shelf_path / "archives" / "env-demo.tar"
        assert shelf_path.exists()
        assert can_path.exists()
        # Save hash persisted
        hash_file = shelf_path / "archives" / "last-save.sha256"
        assert hash_file.exists()
        assert hash_file.read_text().strip() == "abc123"

        # Env should appear in ls as both live and archived
        rc = main(["env", "ls"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "demo" in out

        # --- Step 3: restore ---
        with (
            _patch_unpack(True),
            _patch_register(True),
        ):
            rc = main(["env", "restore", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "export NBW_ACTIVE_ENV=demo" in out

        # Restore hash should be recorded
        restore_hash = root / ".ppe-restore" / "demo.sha256"
        assert restore_hash.exists()
        assert restore_hash.read_text().strip() == "abc123"

        # --- Step 4: install ---
        with (
            _patch_env_exists(True),
            _patch_env_run(),
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "numpy", "pandas"])
        assert rc == 0

        # Package should be recorded in spec
        from nb_wrangler.utils import get_yaml

        spec = get_yaml().load((env_dir / ".ppe-spec.yaml").read_text())
        pip_deps = [
            d for d in spec["dependencies"] if isinstance(d, dict) and "pip" in d
        ]
        assert "numpy" in pip_deps[0]["pip"]
        assert "pandas" in pip_deps[0]["pip"]

        # --- Step 5: relock ---
        compiled = ["numpy==1.26.4", "pandas==2.2.0"]
        with (
            _patch_env_exists(True),
            _patch_compile(compiled),
        ):
            rc = main(["env", "relock", "demo"])
        assert rc == 0

        # Locks should be updated (pinned versions)
        spec = get_yaml().load((env_dir / ".ppe-spec.yaml").read_text())
        pip_deps = [
            d for d in spec["dependencies"] if isinstance(d, dict) and "pip" in d
        ]
        assert "numpy==1.26.4" in pip_deps[0]["pip"]
        assert "pandas==2.2.0" in pip_deps[0]["pip"]

        # --- Step 6: rm ---
        with patch("builtins.input", return_value="n") as mock_input:
            rc = main(["env", "rm", "demo"])
        assert rc == 1  # aborted by user
        assert mock_input.call_count == 1
        assert env_dir.exists()  # env still exists

        with patch("builtins.input", return_value="y"):
            rc = main(["env", "rm", "demo", "--yes"])
        assert rc == 0
        assert not env_dir.exists()

    def test_create_dry_run_does_not_install(self, _ppe_env):
        """Dry-run create should not create an env."""
        from nb_wrangler.ppe.cli import main

        root = _ppe_env["root"]
        with patch(
            "nb_wrangler.environment.EnvironmentManager.create_environment"
        ) as mock_create:
            rc = main(["env", "create", "--from-empty", "--name", "demo", "--dry-run"])
        assert rc == 0
        mock_create.assert_not_called()
        assert not (root / "envs" / "demo").exists()

    def test_install_dry_run_does_not_change_spec(self, _ppe_env, capsys):
        """Install dry-run should not write the spec."""
        from nb_wrangler.ppe.cli import main

        root = _ppe_env["root"]
        env_dir = root / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            _patch_env_exists(True),
            _patch_env_run(),
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "numpy", "--dry-run"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Dry-run" in out
        # Spec should not exist (dry-run doesn't write)
        spec_path = env_dir / ".ppe-spec.yaml"
        assert not spec_path.exists()

    def test_restore_idempotent_skip(self, _ppe_env, capsys):
        """Restore should skip when restore hash matches save hash."""
        from nb_wrangler.ppe.cli import main

        pantry = _ppe_env["pantry"]
        root = _ppe_env["root"]

        # Create shelf with save hash
        shelf = pantry / "shelves" / "demo" / "archives"
        shelf.mkdir(parents=True)
        (shelf / "env-demo.tar").write_text("fake archive")
        (shelf / "last-save.sha256").write_text("abc123\n")

        # Pre-create matching restore hash
        restore_file = root / ".ppe-restore" / "demo.sha256"
        restore_file.parent.mkdir(parents=True)
        restore_file.write_text("abc123\n")

        with _patch_unpack(True) as mock_unpack:
            rc = main(["env", "restore", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "idempotent skip" in out
        mock_unpack.assert_not_called()

    def test_save_refuses_existing_without_force(self, _ppe_env, capsys):
        """Save should refuse when can already exists, unless --force."""
        from nb_wrangler.ppe.cli import main

        root = _ppe_env["root"]
        pantry = _ppe_env["pantry"]

        env_dir = root / "envs" / "demo"
        env_dir.mkdir(parents=True)

        # Pre-create the can
        can_path = pantry / "shelves" / "demo" / "archives" / "env-demo.tar"
        can_path.parent.mkdir(parents=True, exist_ok=True)
        can_path.write_text("old archive")

        with (
            _patch_pack(True),
            _patch_sha256("abc123"),
        ):
            rc = main(["env", "save", "demo"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "already exists" in err
        assert "--force" in err

    def test_save_force_overwrites(self, _ppe_env):
        """Save with --force should overwrite existing can."""
        from nb_wrangler.ppe.cli import main

        root = _ppe_env["root"]
        pantry = _ppe_env["pantry"]

        env_dir = root / "envs" / "demo"
        env_dir.mkdir(parents=True)

        can_path = pantry / "shelves" / "demo" / "archives" / "env-demo.tar"
        can_path.parent.mkdir(parents=True, exist_ok=True)
        can_path.write_text("old archive")

        with (
            _patch_pack(pantry, True),
            _patch_sha256("newhash"),
        ):
            rc = main(["env", "save", "demo", "--force"])
        assert rc == 0

        hash_file = pantry / "shelves" / "demo" / "archives" / "last-save.sha256"
        assert hash_file.read_text().strip() == "newhash"

    def test_rm_dry_run_does_not_delete(self, _ppe_env, capsys):
        """RM dry-run should list but not delete."""
        from nb_wrangler.ppe.cli import main

        root = _ppe_env["root"]
        env_dir = root / "envs" / "demo"
        env_dir.mkdir(parents=True)

        rc = main(["env", "rm", "demo", "--dry-run", "--yes"])
        assert rc == 0
        assert env_dir.exists()  # still there
        out = capsys.readouterr().out
        assert "demo" in out
        assert "removed" in out.lower() or "remove" in out.lower()

    def test_rm_no_match_returns_error(self, _ppe_env, capsys):
        """RM of nonexistent env should error."""
        from nb_wrangler.ppe.cli import main

        rc = main(["env", "rm", "nonexistent", "--yes"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "no matching" in err.lower()


# ---------------------------------------------------------------------------
# Completions tests
# ---------------------------------------------------------------------------


class TestCompletions:
    """Tests for the completions subcommand."""

    def test_bash_completion_script(self, capsys):
        from nb_wrangler.ppe.cli import main

        rc = main(["completions", "bash"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "pep_completion_function" in out
        assert "complete -F" in out
        assert "env" in out
        assert "create" in out

    def test_zsh_completion_script(self, capsys):
        from nb_wrangler.ppe.cli import main

        rc = main(["completions", "zsh"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "#compdef ppe" in out
        assert "env" in out
        assert "create" in out

    def test_fish_completion_script(self, capsys):
        from nb_wrangler.ppe.cli import main

        rc = main(["completions", "fish"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "complete -c ppe" in out
        assert "__fish_use_subcommand" in out
        assert "env" in out
        assert "create" in out

    def test_fish_sees_subcommand_for_env(self, capsys):
        from nb_wrangler.ppe.cli import main

        main(["completions", "fish"])
        out = capsys.readouterr().out
        assert "__fish_seen_subcommand_from env" in out

    def test_completions_invalid_shell_errors(self, capsys):
        """Invalid shell should produce argparse error (exit 2)."""
        from nb_wrangler.ppe.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(["completions", "powershell"])
        except SystemExit as exc:
            assert exc.code == 2
            return
        raise AssertionError("Expected SystemExit for invalid shell")
