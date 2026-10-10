"""Tests for ``nb_wrangler/activation.py`` (shared shell-activation core) and the
equivalent ``nbw`` vs ``hubenv`` surfaces it powers.

The core invariant (the "foreign mamba" fix) being asserted: the emitted snippet
pins ``MAMBA_ROOT_PREFIX`` and activates the environment by **absolute path**
(independent of the activating binary's own root prefix).
"""

import contextlib
import io
import types
from unittest.mock import patch

from nb_wrangler import activation as A
from nb_wrangler.config import WranglerConfig, set_args_config

MM = "/opt/nbw/mm"
MAMBA = MM + "/bin/micromamba"
ENV_PATH = MM + "/envs/demo"


def _args(name):
    ns = types.SimpleNamespace(name=name, quiet=True, verbose=False, debug=False)
    return ns


class TestDetectShell:
    def test_bash(self):
        assert A.detect_shell({"BASH_VERSION": "5.0"}) == "bash"

    def test_zsh(self):
        assert A.detect_shell({"ZSH_VERSION": "5.9"}) == "zsh"

    def test_fish(self):
        assert A.detect_shell({"FISH_VERSION": "3.6"}) == "fish"

    def test_nbw_shell_wins(self):
        assert A.detect_shell({"NBW_SHELL": "zsh", "BASH_VERSION": "5"}) == "zsh"

    def test_shell_env_fallback(self):
        assert A.detect_shell({"SHELL": "/usr/local/bin/fish"}) == "fish"

    def test_default_bash(self):
        assert A.detect_shell({}) == "bash"


class TestEmitActivationBash:
    def test_pins_root_prefix_and_activates_by_path(self):
        out = A.emit_activation(MM, MAMBA, "bash", ENV_PATH, name="demo")
        lines = out.splitlines()
        assert lines[0] == "export NBW_ACTIVE_ENV=demo"
        assert f"export NBW_ENV_ROOT={ENV_PATH}" in out
        assert f"export MAMBA_ROOT_PREFIX={MM}" in out
        assert f"{MAMBA} activate {ENV_PATH}" in out
        assert "shell hook" in out

    def test_no_name_omits_env_markers(self):
        out = A.emit_activation(MM, MAMBA, "bash", ENV_PATH)
        assert "NBW_ACTIVE_ENV" not in out
        assert "NBW_ENV_ROOT" not in out
        assert f"{MAMBA} activate {ENV_PATH}" in out

    def test_data_exports_appended(self):
        out = A.emit_activation(
            MM, MAMBA, "bash", ENV_PATH, name="demo", extra_exports=['export FOO="bar"']
        )
        assert out.splitlines()[-1] == 'export FOO="bar"'

    def test_paths_with_spaces_are_quoted(self):
        mm = "/a b/mm"
        env = "/a b/mm/envs/d"
        out = A.emit_activation(mm, mm + "/bin/micromamba", "bash", env, name="d")
        assert "'/a b/mm'" in out
        assert "'/a b/mm/envs/d'" in out


class TestEmitActivationFish:
    def test_uses_set_gx(self):
        out = A.emit_activation(MM, MAMBA, "fish", ENV_PATH, name="demo")
        assert "set -gx MAMBA_ROOT_PREFIX" in out
        assert "eval (" in out
        assert "export MAMBA_ROOT_PREFIX" not in out


class TestEmitDeactivate:
    def test_bash(self):
        out = A.emit_deactivate(MAMBA, "bash")
        assert f"{MAMBA} deactivate" in out
        assert "shell hook" in out

    def test_fish(self):
        out = A.emit_deactivate(MAMBA, "fish")
        assert "eval (" in out
        assert f"{MAMBA} deactivate" in out.replace("'", "")


class TestEquivalence:
    """The core snippet is identical between the pure core and the nbw-identical emit."""

    def test_shared_appears_in_emit_activation(self):
        core = "\n".join(A.activation_lines(MM, MAMBA, "bash", ENV_PATH))
        assert core in A.emit_activation(MM, MAMBA, "bash", ENV_PATH, name="demo")


class TestHubenvCmdIntegration:
    def test_activate_emits_absolute_path(self, tmp_path, monkeypatch):
        mm = tmp_path / "mm"
        (mm / "envs" / "demo" / "bin").mkdir(parents=True)
        (mm / "envs" / "demo" / "bin" / "python").touch()
        monkeypatch.setenv("NBW_MM", str(mm))
        set_args_config(
            WranglerConfig(
                workflows=[],
                repos_dir=tmp_path / "r",
                quiet=True,
                mamba_command=str(mm / "bin" / "micromamba"),
            )
        )
        from nb_wrangler.hubenv import env_activate

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = env_activate.cmd_env_activate(_args("demo"))
        out = buf.getvalue()
        assert rc == 0
        assert str(mm / "envs" / "demo") in out
        assert "export MAMBA_ROOT_PREFIX=" in out
        assert "export NBW_ACTIVE_ENV=demo" in out
        # activate by absolute path (the foreign-mamba fix), regardless of quoting
        assert f"activate {mm}/envs/demo" in out.replace("'", "")

    def test_missing_env_errors(self, tmp_path, monkeypatch):
        mm = tmp_path / "mm"
        mm.mkdir(parents=True)
        monkeypatch.setenv("NBW_MM", str(mm))
        set_args_config(
            WranglerConfig(workflows=[], repos_dir=tmp_path / "r", quiet=True)
        )
        from nb_wrangler.hubenv import env_activate

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = env_activate.cmd_env_activate(_args("nope"))
        assert rc == 1


# ---------------------------------------------------------------------------
# (a) hubenv env activate must ALSO emit the shelf's environment_vars,
# byte-identically to `hubenv var ls NAME --export`, so `hubenv` users get
# full parity with `nbw --env-activate` (spec data exports).
# ---------------------------------------------------------------------------


class TestHubenvActivateShelfEnvVars:
    def _write_shelf(self, tmp_path, pantry, name, env_vars):
        with (
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
        ):
            from nb_wrangler.hubenv.config import PantryStore
            from nb_wrangler.hubenv.env_spec import save_hubenv_spec

            save_hubenv_spec(
                PantryStore(),
                name,
                {
                    "name": name,
                    "channels": ["conda-forge"],
                    "dependencies": [],
                    "environment_vars": env_vars,
                },
            )

    def test_activated_env_var_exports_match_var_ls_export(self, tmp_path, monkeypatch):
        mm = tmp_path / "mm"
        (mm / "envs" / "demo" / "bin").mkdir(parents=True)
        pantry = tmp_path / "pantry"
        pantry.mkdir()
        self._write_shelf(
            tmp_path,
            pantry,
            "demo",
            {"Z_LAST": "z", "DEBUG": "1", "URL": "http://x?a=1&b=2"},
        )
        monkeypatch.setenv("NBW_MM", str(mm))
        monkeypatch.setattr("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry])
        monkeypatch.setattr("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path)
        set_args_config(
            WranglerConfig(
                workflows=[],
                repos_dir=tmp_path / "r",
                quiet=True,
                mamba_command=str(mm / "bin" / "micromamba"),
            )
        )
        from nb_wrangler.hubenv import env_activate
        from nb_wrangler.hubenv.var import filter_vars_by_glob, print_var_ls_export

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = env_activate.cmd_env_activate(_args("demo"))
        out_lines = buf.getvalue().splitlines()
        assert rc == 0
        assert "export NBW_ACTIVE_ENV=demo" in out_lines
        assert f"activate {mm}/envs/demo" in buf.getvalue().replace("'", "")

        env_vars = {"Z_LAST": "z", "DEBUG": "1", "URL": "http://x?a=1&b=2"}
        expected = [f for f in (f"export {k}={v}" for k, v in sorted(env_vars.items()))]
        # env-var exports are the LAST lines of the snippet
        assert out_lines[-len(expected) :] == expected
        # byte-identical to `hubenv var ls demo --export`
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            print_var_ls_export(filter_vars_by_glob(env_vars, []))
        assert out_lines[-len(expected) :] == b.getvalue().splitlines()

    def test_activate_without_shelf_vars_still_works(self, tmp_path, monkeypatch):
        mm = tmp_path / "mm"
        (mm / "envs" / "demo" / "bin").mkdir(parents=True)
        empty_pantry = tmp_path / "empty_pantry"
        empty_pantry.mkdir()
        monkeypatch.setenv("NBW_MM", str(mm))
        monkeypatch.setattr("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [empty_pantry])
        set_args_config(
            WranglerConfig(
                workflows=[],
                repos_dir=tmp_path / "r",
                quiet=True,
                mamba_command=str(mm / "bin" / "micromamba"),
            )
        )
        from nb_wrangler.hubenv import env_activate

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = env_activate.cmd_env_activate(_args("demo"))
        out = buf.getvalue()
        assert rc == 0
        assert "export NBW_ACTIVE_ENV=demo" in out
        assert f"activate {mm}/envs/demo" in out.replace("'", "")
        # No spurious env-var lines
        assert "export Z_" not in out and "export URL=" not in out
