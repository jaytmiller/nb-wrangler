"""Tests for hubenv var add/rm/ls (Phase 8)."""

from unittest.mock import patch

import contextlib

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


def _pantry_dir(tmp_path):
    """Create (and return) the tmp pantry root for *tmp_path*."""
    pantry = tmp_path / "pantry"
    pantry.mkdir(parents=True, exist_ok=True)
    return pantry


def _write_spec(tmp_path, name, env_vars=None):
    """Write a minimal hubenv spec (mamba view) via the public API."""
    pantry = _pantry_dir(tmp_path)
    with (
        patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
        patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
    ):
        from nb_wrangler.hubenv.config import PantryStore
        from nb_wrangler.hubenv.env_spec import save_hubenv_spec

        store = PantryStore()
        spec = {"name": name, "channels": ["conda-forge"], "dependencies": []}
        if env_vars is not None:
            spec["environment_vars"] = env_vars
        save_hubenv_spec(store, name, spec)
    return pantry


def _read_spec(tmp_path, name):
    """Read back the hubenv mamba-view for *name* via the public API."""
    pantry = _pantry_dir(tmp_path)
    with (
        patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
        patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
    ):
        from nb_wrangler.hubenv.config import PantryStore
        from nb_wrangler.hubenv.env_spec import load_hubenv_spec

        return load_hubenv_spec(PantryStore(), name)


def _patch_register_env(return_value=True):
    """Patch EnvironmentManager.register_environment."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.register_environment",
        return_value=return_value,
    )


@contextlib.contextmanager
def _base_patch(tmp_path):
    """Common patches: NBW_ROOT + NBW_PANTRY_DIRS point at tmp_path.

    Yields the register_environment mock so callers can assert on it.
    """
    pantry = _pantry_dir(tmp_path)
    with (
        patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
        patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        _patch_register_env(True) as p_reg,
    ):
        yield p_reg


@contextlib.contextmanager
def _ls_patch(tmp_path):
    """Pantry root + NBW_ROOT patched for read-only helpers (no register)."""
    pantry = _pantry_dir(tmp_path)
    with (
        patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
        patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
    ):
        yield


# ---------------------------------------------------------------------------
# var ls
# ---------------------------------------------------------------------------


class TestVarLs:
    """Tests for hubenv var ls."""

    def test_ls_table_default(self, tmp_path, capsys):
        """Default output is a two-column table."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"DEBUG": "1", "API_KEY": "secret"})
        with _ls_patch(tmp_path):
            rc = main(["var", "ls", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "VAR" in out and "VALUE" in out
        assert "DEBUG" in out and "1" in out
        assert "API_KEY" in out and "secret" in out

    def test_ls_table_sorted(self, tmp_path, capsys):
        """Vars are listed in sorted order."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"ZED": "1", "ALPHA": "2"})
        with _ls_patch(tmp_path):
            rc = main(["var", "ls", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        lines = out.splitlines()
        alpha_pos = next(i for i, l in enumerate(lines) if "ALPHA" in l)
        zed_pos = next(i for i, l in enumerate(lines) if "ZED" in l)
        assert alpha_pos < zed_pos

    def test_ls_export(self, tmp_path, capsys):
        """--export prints 'export VAR=VALUE' lines."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"DEBUG": "1", "PATH": "/x"})
        with _ls_patch(tmp_path):
            rc = main(["var", "ls", "demo", "--export"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "export DEBUG=1" in out
        assert "export PATH=/x" in out

    def test_ls_json(self, tmp_path, capsys):
        """--format json prints a JSON object."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"DEBUG": "1"})
        with _ls_patch(tmp_path):
            rc = main(["var", "ls", "demo", "--format", "json"])
        assert rc == 0
        out = capsys.readouterr().out
        assert '"name": "demo"' in out
        assert '"DEBUG": "1"' in out

    def test_ls_glob_filter(self, tmp_path, capsys):
        """GLOB positional filters variables by name."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"API_KEY": "1", "API_URL": "2", "DB": "3"})
        with _ls_patch(tmp_path):
            rc = main(["var", "ls", "demo", "API_*"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "API_KEY" in out
        assert "API_URL" in out
        assert "DB" not in out

    def test_ls_no_vars(self, tmp_path, capsys):
        """ls with no env vars prints a helpful message."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {})
        with _ls_patch(tmp_path):
            rc = main(["var", "ls", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "no environment variables" in out.lower()

    def test_ls_missing_spec_no_error(self, tmp_path, capsys):
        """ls on a name with no spec does not crash."""
        from nb_wrangler.hubenv.cli import main

        with _ls_patch(tmp_path):
            rc = main(["var", "ls", "ghost"])
        assert rc == 0
        assert "no environment variables" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# var add
# ---------------------------------------------------------------------------


class TestVarAdd:
    """Tests for hubenv var add."""

    def test_add_single(self, tmp_path, capsys):
        """add writes the var to the spec and refreshes the kernel."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {})
        with _base_patch(tmp_path) as p_reg:
            rc = main(["var", "add", "demo", "DEBUG=1"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Set DEBUG=1" in out
        assert "Kernel refreshed" in out
        p_reg.assert_called_once()
        args, kwargs = p_reg.call_args
        assert args[0] == "demo"  # env name
        assert args[2] == {"DEBUG": "1"}  # env vars
        spec = _read_spec(tmp_path, "demo")
        assert spec["environment_vars"] == {"DEBUG": "1"}

    def test_add_multiple(self, tmp_path, capsys):
        """add accepts several VAR=VALUE assignments at once."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"DEBUG": "0"})
        with _base_patch(tmp_path):
            rc = main(["var", "add", "demo", "DEBUG=1", "API_KEY=secret"])
        assert rc == 0
        spec = _read_spec(tmp_path, "demo")
        assert spec["environment_vars"] == {"DEBUG": "1", "API_KEY": "secret"}

    def test_add_value_with_equals(self, tmp_path):
        """add splits on the first '=' so values may contain '='."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {})
        with _base_patch(tmp_path):
            rc = main(["var", "add", "demo", "URL=http://x?a=1&b=2"])
        assert rc == 0
        spec = _read_spec(tmp_path, "demo")
        assert spec["environment_vars"]["URL"] == "http://x?a=1&b=2"

    def test_add_invalid_assignment(self, tmp_path, capsys):
        """add with no '=' returns an error and does not modify the spec."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"DEBUG": "0"})
        with _base_patch(tmp_path):
            rc = main(["var", "add", "demo", "DEBUG"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "not a VAR=VALUE" in err
        spec = _read_spec(tmp_path, "demo")
        assert spec.get("environment_vars") == {"DEBUG": "0"}

    def test_add_creates_spec_section_when_missing(self, tmp_path):
        """add works even when no environment_vars section existed."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", None)  # no environment_vars key
        with _base_patch(tmp_path):
            rc = main(["var", "add", "demo", "DEBUG=1"])
        assert rc == 0
        spec = _read_spec(tmp_path, "demo")
        assert spec["environment_vars"] == {"DEBUG": "1"}


# ---------------------------------------------------------------------------
# var rm
# ---------------------------------------------------------------------------


class TestVarRm:
    """Tests for hubenv var rm."""

    def test_rm_glob_removes_matching(self, tmp_path, capsys):
        """rm removes glob-matched vars from the spec + refreshes kernel."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"API_KEY": "1", "API_URL": "2", "DB": "3"})
        with _base_patch(tmp_path) as p_reg:
            rc = main(["var", "rm", "demo", "API_*"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Removed API_KEY" in out
        assert "Removed API_URL" in out
        assert "DB" not in out
        p_reg.assert_called_once()
        remaining = p_reg.call_args.args[2]
        assert "DB" in remaining
        assert "API_KEY" not in remaining
        spec = _read_spec(tmp_path, "demo")
        assert spec["environment_vars"] == {"DB": "3"}

    def test_rm_no_match_is_noop(self, tmp_path, capsys):
        """rm with no matches does not save or refresh."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"DEBUG": "1"})
        with _base_patch(tmp_path) as p_reg:
            rc = main(["var", "rm", "demo", "NONEXISTENT_*"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "No matching" in out
        p_reg.assert_not_called()
        spec = _read_spec(tmp_path, "demo")
        assert spec["environment_vars"] == {"DEBUG": "1"}

    def test_rm_exact_name(self, tmp_path):
        """rm works with a plain (non-glob) name."""
        from nb_wrangler.hubenv.cli import main

        _write_spec(tmp_path, "demo", {"DEBUG": "1", "KEEP": "2"})
        with _base_patch(tmp_path):
            rc = main(["var", "rm", "demo", "DEBUG"])
        assert rc == 0
        spec = _read_spec(tmp_path, "demo")
        assert spec["environment_vars"] == {"KEEP": "2"}
