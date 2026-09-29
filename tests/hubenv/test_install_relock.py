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
    """Return a context manager that patches NBW_ROOT in hubenv.config."""
    return patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path)


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
        spec_path = env_dir / ".hubenv-spec.yaml"
        assert spec_path.exists()

        from nb_wrangler.utils import get_yaml

        spec = get_yaml().load(spec_path.read_text())
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
        spec_path = env_dir / ".hubenv-spec.yaml"
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
        from nb_wrangler.utils import yaml_dumps

        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / ".hubenv-spec.yaml").write_text(yaml_dumps(spec))

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_wl_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "install", "demo", "scipy", "--using", "mamba"])

        assert rc == 0
        from nb_wrangler.utils import get_yaml

        updated = get_yaml().load((env_dir / ".hubenv-spec.yaml").read_text())
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
        spec_path = env_dir / ".hubenv-spec.yaml"
        assert not spec_path.exists()


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


class TestUninstall:
    """Tests for hubenv env uninstall."""

    def test_uninstall_removes_from_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main
        from nb_wrangler.utils import yaml_dumps, get_yaml

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy", "pandas"]}],
        }
        (env_dir / ".hubenv-spec.yaml").write_text(yaml_dumps(spec))

        with (
            _patch_nbw_root(tmp_path),
            _patch_env_exists(True),
            _patch_env_run(0),
            _patch_handle_result(True),
        ):
            rc = main(["env", "uninstall", "demo", "numpy"])

        assert rc == 0
        updated = get_yaml().load((env_dir / ".hubenv-spec.yaml").read_text())
        pip_deps = updated["dependencies"][-1]["pip"]
        assert "numpy" not in pip_deps
        assert "pandas" in pip_deps

    def test_uninstall_no_relock(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main
        from nb_wrangler.utils import yaml_dumps

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        (env_dir / ".hubenv-spec.yaml").write_text(yaml_dumps(spec))

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
        from nb_wrangler.utils import yaml_dumps

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        (env_dir / ".hubenv-spec.yaml").write_text(yaml_dumps(spec))

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
        from nb_wrangler.utils import get_yaml

        updated = get_yaml().load((env_dir / ".hubenv-spec.yaml").read_text())
        pip_deps = updated["dependencies"][-1]["pip"]
        assert "numpy" in pip_deps


# ---------------------------------------------------------------------------
# relock
# ---------------------------------------------------------------------------


class TestRelock:
    """Tests for hubenv env relock."""

    def test_relock_dry_run(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main
        from nb_wrangler.utils import yaml_dumps

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy", "pandas"]}],
        }
        (env_dir / ".hubenv-spec.yaml").write_text(yaml_dumps(spec))

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
        from nb_wrangler.utils import yaml_dumps, get_yaml

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        (env_dir / ".hubenv-spec.yaml").write_text(yaml_dumps(spec))

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
        updated = get_yaml().load((env_dir / ".hubenv-spec.yaml").read_text())
        pip_deps = updated["dependencies"][-1]["pip"]
        assert "numpy" in pip_deps
        assert "numpy==1.26.4" not in pip_deps

    def test_relock_writes_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main
        from nb_wrangler.utils import yaml_dumps, get_yaml

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        (env_dir / ".hubenv-spec.yaml").write_text(yaml_dumps(spec))

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
        updated = get_yaml().load((env_dir / ".hubenv-spec.yaml").read_text())
        pip_deps = updated["dependencies"][-1]["pip"]
        assert "numpy==1.26.4" in pip_deps
        assert "pillow==10.2.0" in pip_deps

    def test_relock_no_pip_packages(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main
        from nb_wrangler.utils import yaml_dumps

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        # Spec with empty pip section
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": []}],
        }
        (env_dir / ".hubenv-spec.yaml").write_text(yaml_dumps(spec))

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
        from nb_wrangler.utils import yaml_dumps

        env_dir = tmp_path / "envs" / "demo"
        env_dir.mkdir(parents=True)
        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "pip", {"pip": ["numpy"]}],
        }
        (env_dir / ".hubenv-spec.yaml").write_text(yaml_dumps(spec))

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
