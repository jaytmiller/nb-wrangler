"""Tests for hubenv env install/uninstall + hubenv env relock (Phase 5)."""

from subprocess import CompletedProcess
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


def _patch_env_exists(return_value: bool = True):
    """Return a context manager that patches environment_exists."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.environment_exists",
        return_value=return_value,
    )


def _patch_env_run(returncode: int = 0):
    """Return a context manager that patches env_run with a CompletedProcess."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.env_run",
        return_value=CompletedProcess(
            args=[], returncode=returncode, stdout="", stderr=""
        ),
    )


def _patch_wl_run(returncode: int = 0):
    """Return a context manager that patches wrangler_run with a CompletedProcess."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.wrangler_run",
        return_value=CompletedProcess(
            args=[], returncode=returncode, stdout="", stderr=""
        ),
    )


def _patch_handle_result(return_value: bool = True):
    """Return a context manager that patches handle_result."""
    return patch(
        "nb_wrangler.environment.EnvironmentManager.handle_result",
        return_value=return_value,
    )


def _patch_nbw_root(tmp_path):
    """Return a context manager patching NBW_ROOT + NBW_PANTRY_DIRS."""
    return patch.multiple(
        "nb_wrangler.hubenv.config",
        NBW_ROOT=tmp_path,
        NBW_PANTRY_DIRS=[tmp_path / "pantry"],
    )


def _spec_path(tmp_path, name="demo"):
    """Canonical path where the hubenv spec now lives (shelf location)."""
    return tmp_path / "pantry" / "shelves" / name / "nbw-wrangler-spec.yaml"


def _write_shelf_spec(tmp_path, name="demo", spec=None):
    """Write a mamba-view spec through the public API."""
    with _patch_nbw_root(tmp_path):
        from nb_wrangler.hubenv.config import PantryStore
        from nb_wrangler.hubenv.env_spec import save_hubenv_spec

        if spec is None:
            spec = {"name": name, "channels": ["conda-forge"], "dependencies": []}
        save_hubenv_spec(PantryStore(), name, spec)


def _read_shelf_spec(tmp_path, name="demo"):
    """Read a mamba-view spec through the public API."""
    with _patch_nbw_root(tmp_path):
        from nb_wrangler.hubenv.config import PantryStore
        from nb_wrangler.hubenv.env_spec import load_hubenv_spec

        return load_hubenv_spec(PantryStore(), name)


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


class TestInstall:
    """Tests for hubenv env install."""

    def test_install_updates_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "numpy", "pandas"])

        assert rc == 0
        spec_path = _spec_path(tmp_path)
        assert spec_path.exists()

        spec = _read_shelf_spec(tmp_path, "demo")
        pip_deps = spec["dependencies"][-1]["pip"]
        assert "numpy" in pip_deps
        assert "pandas" in pip_deps

    def test_install_prints_suggestion(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "numpy"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "hubenv env relock" in out
        assert "demo" in out

    def test_install_no_relock(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "numpy", "--no-relock"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "hubenv env relock" not in out

    def test_install_dry_run(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "numpy", "pandas", "--dry-run"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "Dry-run" in out
        assert "pip install" in out or "uv pip install" in out
        assert "+ numpy" in out
        assert "+ pandas" in out

    def test_install_dry_run_no_change(self, tmp_path, capsys):
        """Dry-run must not write the spec file."""
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "numpy", "--dry-run"])

        assert rc == 0
        spec_path = _spec_path(tmp_path)
        assert not spec_path.exists()

    def test_install_uv(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            patch(
                "nb_wrangler.environment.EnvironmentManager.env_run",
                return_value=CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ) as mock_env_run,
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "numpy", "--using", "uv"])

        assert rc == 0
        call_args = mock_env_run.call_args
        assert "uv pip install" in str(call_args)

    def test_install_mamba(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        # Pre-create a spec with pip section so we can verify conda add

        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        env_dir.mkdir(parents=True, exist_ok=True)
        _write_shelf_spec(tmp_path, "demo", spec)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_wl_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "scipy", "--using", "mamba"])

        assert rc == 0

        updated = _read_shelf_spec(tmp_path)
        deps = updated["dependencies"]
        assert "scipy" in deps
        # pip section should still be intact
        pip_section = [d for d in deps if isinstance(d, dict) and "pip" in d]
        assert pip_section

    def test_install_missing_env(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(False),
        ):
            rc = main(["env", "install", "nonexistent", "numpy"])

        assert rc == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_install_failure(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(1),  # failure
            _patch_handle_result(False),
        ):
            rc = main(["env", "install", "demo", "numpy"])

        assert rc == 1
        # spec should not be updated on failure
        spec_path = _spec_path(tmp_path)
        assert not spec_path.exists()


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


class TestUninstall:
    """Tests for hubenv env uninstall."""

    def test_uninstall_removes_from_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy", "pandas"]}],
        }
        _write_shelf_spec(tmp_path, "demo", spec)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "uninstall", "demo", "numpy"])

        assert rc == 0
        updated = _read_shelf_spec(tmp_path)
        pip_deps = updated["dependencies"][-1]["pip"]
        assert "numpy" not in pip_deps
        assert "pandas" in pip_deps

    def test_uninstall_no_relock(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        _write_shelf_spec(tmp_path, "demo", spec)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "uninstall", "demo", "numpy", "--no-relock"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "hubenv env relock" not in out

    def test_uninstall_dry_run(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        _write_shelf_spec(tmp_path, "demo", spec)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "uninstall", "demo", "numpy", "--dry-run"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "Dry-run" in out
        assert "- numpy" in out
        # spec should not be changed

        updated = _read_shelf_spec(tmp_path)
        pip_deps = updated["dependencies"][-1]["pip"]
        assert "numpy" in pip_deps


# ---------------------------------------------------------------------------
# relock
# ---------------------------------------------------------------------------


class TestRelock:
    """Tests for hubenv env relock."""

    def test_relock_dry_run(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy", "pandas"]}],
        }
        _write_shelf_spec(tmp_path, "demo", spec)

        compiled = ["numpy==1.26.4", "pandas==2.2.0"]
        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            patch(
                "nb_wrangler.hubenv.env_relock.compile_pip_packages",
                return_value=compiled,
            ),
        ):
            rc = main(["env", "relock", "demo", "--dry-run"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "Dry-run" in out
        assert "numpy==1.26.4" in out
        assert "pandas==2.2.0" in out

    def test_relock_dry_run_no_write(self, tmp_path, capsys):
        """Dry-run relock must not modify the spec file."""
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        _write_shelf_spec(tmp_path, "demo", spec)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            patch(
                "nb_wrangler.hubenv.env_relock.compile_pip_packages",
                return_value=["numpy==1.26.4"],
            ),
        ):
            rc = main(["env", "relock", "demo", "--dry-run"])

        assert rc == 0
        # Spec should still have unpinned numpy
        updated = _read_shelf_spec(tmp_path)
        pip_deps = updated["dependencies"][-1]["pip"]
        assert "numpy" in pip_deps
        assert "numpy==1.26.4" not in pip_deps

    def test_relock_writes_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        _write_shelf_spec(tmp_path, "demo", spec)

        compiled = ["numpy==1.26.4", "pillow==10.2.0"]
        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            patch(
                "nb_wrangler.hubenv.env_relock.compile_pip_packages",
                return_value=compiled,
            ),
        ):
            rc = main(["env", "relock", "demo"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "Relocked 2 packages" in out
        updated = _read_shelf_spec(tmp_path)
        pip_deps = updated["dependencies"][-1]["pip"]
        assert "numpy==1.26.4" in pip_deps
        assert "pillow==10.2.0" in pip_deps

    def test_relock_no_pip_packages(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        # Spec with empty pip section
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": []}],
        }
        _write_shelf_spec(tmp_path, "demo", spec)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
        ):
            rc = main(["env", "relock", "demo"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "No pip packages to relock" in out

    def test_relock_missing_env(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(False),
        ):
            rc = main(["env", "relock", "nonexistent"])

        assert rc == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_relock_compile_failure(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        _write_shelf_spec(tmp_path, "demo", spec)

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            patch(
                "nb_wrangler.hubenv.env_relock.compile_pip_packages",
                return_value=None,
            ),
        ):
            rc = main(["env", "relock", "demo"])

        assert rc == 1

    def test_relock_delegates_to_compiler(self, tmp_path):
        """``compile_pip_packages`` adapter must call through to
        ``RequirementsCompiler.compile_packages_for_env`` with the pip list
        and the env manager's ``nbw_temp_dir``."""
        from unittest.mock import PropertyMock
        from nb_wrangler.environment import EnvironmentManager
        from nb_wrangler.hubenv.env_relock import compile_pip_packages

        em = EnvironmentManager()
        temp_dir = tmp_path / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        expected = ["numpy==1.26.4", "pandas==2.2.0"]
        with (
            patch.object(
                EnvironmentManager,
                "nbw_temp_dir",
                new_callable=PropertyMock,
                return_value=temp_dir,
            ),
            patch(
                "nb_wrangler.compiler.RequirementsCompiler.compile_packages_for_env",
                return_value=expected,
            ) as mock_compile,
        ):
            got = compile_pip_packages(em, "demo", ["numpy", "pandas"])
            mock_compile.assert_called_once_with(["numpy", "pandas"], temp_dir)
        assert got == expected


class TestCompilePackagesForEnv:
    """Direct unit tests on ``RequirementsCompiler.compile_packages_for_env``."""

    def test_uv_path_success_calls_read_package_versions(self, tmp_path):
        from nb_wrangler.compiler import RequirementsCompiler

        compiler = RequirementsCompiler(spec_manager=None, repo_manager=None)
        compiler.config.pip_command = "uv pip"
        with (
            patch.object(type(compiler), "_run_uv_compile", return_value=True),
            patch.object(
                type(compiler),
                "read_package_versions",
                return_value=["numpy==1.26.4"],
            ) as mock_rpv,
        ):
            out = compiler.compile_packages_for_env(["numpy"], tmp_path)
            expected = tmp_path / "relock_compiled.txt"
            mock_rpv.assert_called_once_with([expected])
        assert out == ["numpy==1.26.4"]

    def test_pip_fallback_path_is_reachable(self, tmp_path):
        """When ``pip_command`` does not include ``uv pip``, the pip fallback runs."""
        from nb_wrangler.compiler import RequirementsCompiler

        compiler = RequirementsCompiler(spec_manager=None, repo_manager=None)
        compiler.config.pip_command = "pip"
        with (
            patch.object(
                type(compiler), "_run_pip_compile", return_value=True
            ) as mock_pipc,
            patch.object(
                type(compiler),
                "read_package_versions",
                return_value=["numpy==1.26.4"],
            ),
        ):
            out = compiler.compile_packages_for_env(["numpy"], tmp_path)
            mock_pipc.assert_called_once()
        assert out == ["numpy==1.26.4"]

    def test_uv_failure_returns_none(self, tmp_path):
        from nb_wrangler.compiler import RequirementsCompiler

        compiler = RequirementsCompiler(spec_manager=None, repo_manager=None)
        compiler.config.pip_command = "uv pip"
        with (
            patch.object(type(compiler), "_run_uv_compile", return_value=False),
            patch.object(
                type(compiler),
                "read_package_versions",
            ) as mock_rpv,
        ):
            out = compiler.compile_packages_for_env(["numpy"], tmp_path)
            mock_rpv.assert_not_called()
        assert out is None

    def test_wrangler_run_uses_pip_compile_timeout(self, tmp_path):
        """The uv compile path threads ``PIP_COMPILE_TIMEOUT`` into ``wrangler_run``."""
        from nb_wrangler.compiler import RequirementsCompiler
        from nb_wrangler.constants import PIP_COMPILE_TIMEOUT
        from nb_wrangler.environment import EnvironmentManager

        compiler = RequirementsCompiler(spec_manager=None, repo_manager=None)
        compiler.config.pip_command = "uv pip"
        fake_result = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with (
            patch.object(
                EnvironmentManager, "wrangler_run", return_value=fake_result
            ) as mock_run,
            patch.object(EnvironmentManager, "handle_result", return_value=True),
            patch.object(
                type(compiler),
                "read_package_versions",
                return_value=["numpy==1.26.4"],
            ),
        ):
            compiler.compile_packages_for_env(["numpy"], tmp_path)
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            assert kwargs.get("timeout") == PIP_COMPILE_TIMEOUT


# ---------------------------------------------------------------------------
# parser tests
# ---------------------------------------------------------------------------


class TestParser:
    """Tests for the argparse parser structure for install/uninstall/relock."""

    def test_parses_install(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["env", "install", "demo", "numpy", "pandas", "--using", "uv"]
        )
        assert args.env_command == "install"
        assert args.name == "demo"
        assert args.packages == ["numpy", "pandas"]
        assert args.using == "uv"
        assert args.no_relock is False
        assert args.dry_run is False

    def test_parses_uninstall(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["env", "uninstall", "demo", "numpy", "--no-relock"])
        assert args.env_command == "uninstall"
        assert args.name == "demo"
        assert args.packages == ["numpy"]
        assert args.no_relock is True

    def test_parses_relock(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["env", "relock", "demo", "--dry-run"])
        assert args.env_command == "relock"
        assert args.name == "demo"
        assert args.dry_run is True

    def test_install_requires_packages(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(["env", "install", "demo"])
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for missing packages")

    def test_install_invalid_using(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(["env", "install", "demo", "numpy", "--using", "cargo"])
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for invalid --using")
