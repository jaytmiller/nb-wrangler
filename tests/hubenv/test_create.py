"""Tests for hubenv CLI scaffold and env create (Phase 1)."""

from unittest.mock import patch

import pytest

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.environment import EnvironmentManager

_CANNED_EXPORT_YAML = """
name: astro-py
channels:
  - conda-forge
dependencies:
  - python=3.11.5
  - numpy=1.26.0
  - pandas=2.1.0
  - pip
  - pip:
    - requests==2.31.0
    - scipy==1.11.0
prefix: /tmp/envs/astro-py
"""


# ---------------------------------------------------------------------------
# CLI scaffold tests
# ---------------------------------------------------------------------------


class TestParser:
    """Tests for the argparse parser structure."""

    def test_main_no_command_prints_help(self, capsys):
        from nb_wrangler.hubenv.cli import main

        rc = main([])
        assert rc == 0
        out = capsys.readouterr()
        assert "env" in out.out
        assert "var" in out.out
        assert "data" in out.out
        assert "export" in out.out
        assert "status" in out.out
        assert "doctor" in out.out

    def test_parses_env_create(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["env", "create", "--from-empty", "--name", "demo", "--python", "3.11"]
        )
        assert args.command == "env"
        assert args.env_command == "create"
        assert args.name == "demo"
        assert args.python == "3.11"
        assert args.from_empty is True

    def test_create_requires_name(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(["env", "create", "--from-empty"])
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for missing --name")

    def test_create_mutually_exclusive_sources(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(
                [
                    "env",
                    "create",
                    "--from-empty",
                    "--from-requirements",
                    "req.txt",
                    "--name",
                    "x",
                ]
            )
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for conflicting seed sources")

    def test_create_requires_one_source(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(["env", "create", "--name", "x"])
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for no seed source")

    def test_parses_from_existing_env(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["env", "create", "--from-existing-env", "astro-py", "--name", "myproject"]
        )
        assert args.from_existing_env == "astro-py"
        assert args.name == "myproject"

    def test_from_existing_env_mutually_exclusive(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(
                [
                    "env",
                    "create",
                    "--from-empty",
                    "--from-existing-env",
                    "x",
                    "--name",
                    "y",
                ]
            )
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for conflicting seed sources")


# ---------------------------------------------------------------------------
# Not-implemented stub tests
# ---------------------------------------------------------------------------


class TestNotImplemented:
    """Commands that are genuinely not yet implemented should exit 2 cleanly.

    (export/status/doctor were previously in this category but are now
    implemented in Phase 10 — see tests/hubenv/test_export_status_doctor.py.)
    """

    def test_env_no_subcommand_prints_help(self, capsys):
        from nb_wrangler.hubenv.cli import main

        rc = main(["env"])
        assert rc == 0  # prints help


# ---------------------------------------------------------------------------
# seed_from_existing_env tests
# ---------------------------------------------------------------------------


class TestSeedFromExistingEnv:
    """Tests for seed_from_existing_env in seeds.py."""

    def test_seed_overrides_name(self):
        from nb_wrangler.hubenv.seeds import seed_from_existing_env

        with (
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch(
                "nb_wrangler.hubenv.seeds._run_pip_freeze",
                return_value=["requests==2.31.0"],
            ),
        ):
            spec = seed_from_existing_env("myproject", "astro-py")

        assert spec["name"] == "myproject"

    def test_seed_includes_pip_packages(self):
        from nb_wrangler.hubenv.seeds import seed_from_existing_env

        with (
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch(
                "nb_wrangler.hubenv.seeds._run_pip_freeze",
                return_value=["requests==2.31.0", "scipy==1.11.0"],
            ),
        ):
            spec = seed_from_existing_env("myproject", "astro-py")

        pip_deps = spec["dependencies"][-1]["pip"]
        assert "requests==2.31.0" in pip_deps
        assert "scipy==1.11.0" in pip_deps

    def test_seed_strips_python_without_override(self):
        from nb_wrangler.hubenv.seeds import seed_from_existing_env

        with (
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch("nb_wrangler.hubenv.seeds._run_pip_freeze", return_value=[]),
        ):
            spec = seed_from_existing_env("myproject", "astro-py")

        conda_deps = [d for d in spec["dependencies"] if isinstance(d, str)]
        assert not any(d.startswith("python") for d in conda_deps)

    def test_seed_python_override(self):
        from nb_wrangler.hubenv.seeds import seed_from_existing_env

        with (
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch("nb_wrangler.hubenv.seeds._run_pip_freeze", return_value=[]),
        ):
            spec = seed_from_existing_env("myproject", "astro-py", python="3.10")

        conda_deps = [d for d in spec["dependencies"] if isinstance(d, str)]
        assert "python=3.10" in conda_deps
        assert not any(d == "python=3.11.5" for d in conda_deps)

    def test_seed_no_duplicate_pip(self):
        from nb_wrangler.hubenv.seeds import seed_from_existing_env

        with (
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch(
                "nb_wrangler.hubenv.seeds._run_pip_freeze",
                return_value=["requests==2.31.0"],
            ),
        ):
            spec = seed_from_existing_env("myproject", "astro-py")

        conda_deps = [d for d in spec["dependencies"] if isinstance(d, str)]
        pip_count = sum(1 for d in conda_deps if d == "pip")
        assert pip_count == 1

    def test_seed_error_on_missing_env(self):
        from nb_wrangler.hubenv.seeds import seed_from_existing_env

        err = ValueError("mamba env export failed for 'ghost': env not found")

        with (patch("nb_wrangler.hubenv.seeds._run_mamba_export", side_effect=err),):
            try:
                seed_from_existing_env("myproject", "ghost")
            except ValueError as exc:
                assert "ghost" in str(exc)
                return
        raise AssertionError("Expected ValueError")


# ---------------------------------------------------------------------------
# hubenv env create --from-existing-env tests
# ---------------------------------------------------------------------------


class TestCreateFromExistingEnv:
    """Tests for hubenv env create --from-existing-env CLI."""

    @pytest.fixture(autouse=True)
    def _set_config(self, tmp_path):
        set_args_config(
            WranglerConfig(
                workflows=[],
                spec_file="",
                repos_dir=tmp_path / "repos",
                output_dir=tmp_path / "output",
            )
        )

    def test_import_persists_shadow_spec(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir(exist_ok=True)

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch(
                "nb_wrangler.hubenv.seeds._run_pip_freeze",
                return_value=["requests==2.31.0"],
            ),
            patch.object(EnvironmentManager, "environment_exists", return_value=True),
            patch.object(EnvironmentManager, "register_environment", return_value=True),
        ):
            rc = main(
                [
                    "env",
                    "create",
                    "--from-existing-env",
                    "astro-py",
                    "--name",
                    "myproject",
                ]
            )

        assert rc == 0
        shadow = tmp_path / "envs" / "myproject" / ".hubenv-spec.yaml"
        assert shadow.exists()

    def test_import_writes_shelf_spec(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir(exist_ok=True)

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch(
                "nb_wrangler.hubenv.seeds._run_pip_freeze",
                return_value=["requests==2.31.0"],
            ),
            patch.object(EnvironmentManager, "environment_exists", return_value=True),
            patch.object(EnvironmentManager, "register_environment", return_value=True),
        ):
            rc = main(
                [
                    "env",
                    "create",
                    "--from-existing-env",
                    "astro-py",
                    "--name",
                    "myproject",
                ]
            )

        assert rc == 0
        shelf_spec = (
            tmp_path / "pantry" / "shelves" / "myproject" / "nbw-wrangler-spec.yaml"
        )
        assert shelf_spec.exists()

    def test_import_registers_kernel(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir(exist_ok=True)

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch(
                "nb_wrangler.hubenv.seeds._run_pip_freeze",
                return_value=["requests==2.31.0"],
            ),
            patch.object(EnvironmentManager, "environment_exists", return_value=True),
            patch.object(
                EnvironmentManager, "register_environment", return_value=True
            ) as mock_register,
        ):
            rc = main(
                [
                    "env",
                    "create",
                    "--from-existing-env",
                    "astro-py",
                    "--name",
                    "myproject",
                ]
            )

        assert rc == 0
        mock_register.assert_called_once()

    def test_import_does_not_create_env(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir(exist_ok=True)

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch(
                "nb_wrangler.hubenv.seeds._run_pip_freeze",
                return_value=["requests==2.31.0"],
            ),
            patch.object(EnvironmentManager, "environment_exists", return_value=True),
            patch.object(EnvironmentManager, "register_environment", return_value=True),
            patch.object(
                EnvironmentManager, "create_environment", return_value=True
            ) as mock_create,
        ):
            rc = main(
                [
                    "env",
                    "create",
                    "--from-existing-env",
                    "astro-py",
                    "--name",
                    "myproject",
                ]
            )

        assert rc == 0
        mock_create.assert_not_called()

    def test_import_dry_run_writes_nothing(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        with (
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch(
                "nb_wrangler.hubenv.seeds._run_pip_freeze",
                return_value=["requests==2.31.0"],
            ),
        ):
            rc = main(
                [
                    "env",
                    "create",
                    "--from-existing-env",
                    "astro-py",
                    "--name",
                    "myproject",
                    "--dry-run",
                ]
            )

        assert rc == 0
        out = capsys.readouterr().out
        assert "name: myproject" in out
        shadow = tmp_path / "envs" / "myproject" / ".hubenv-spec.yaml"
        assert not shadow.exists()

    def test_import_not_found(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir(exist_ok=True)

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=_CANNED_EXPORT_YAML,
            ),
            patch(
                "nb_wrangler.hubenv.seeds._run_pip_freeze",
                return_value=["requests==2.31.0"],
            ),
            patch.object(EnvironmentManager, "environment_exists", return_value=False),
        ):
            rc = main(
                [
                    "env",
                    "create",
                    "--from-existing-env",
                    "astro-py",
                    "--name",
                    "myproject",
                ]
            )

        assert rc == 1
