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

_MAMBA_SPEC_YAML = """
name: old-name
channels:
  - conda-forge
dependencies:
  - python=3.11
  - numpy=1.26.0
  - pip
"""

_WRANGLER_SPEC_YAML = """
image_spec_header:
  image_name: old-name
  kernel_name: old-name
  display_name: old-name
  python_version: "3.11"
repositories: {}
extra_mamba_packages:
  - numpy=1.26.0
extra_pip_packages:
  - requests==2.31.0
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
        assert "create" in out.out
        assert "var" in out.out
        assert "data" in out.out
        assert "export" in out.out
        assert "status" in out.out
        assert "doctor" in out.out

    def test_parses_env_create(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["create", "--from-empty", "--name", "demo", "--python", "3.11"]
        )
        assert args.command == "create"
        assert args.name == "demo"
        assert args.python == "3.11"
        assert args.from_empty is True

    def test_create_requires_name(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(["create", "--from-empty"])
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for missing --name")

    def test_create_mutually_exclusive_sources(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(
                [
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
            parser.parse_args(["create", "--name", "x"])
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for no seed source")

    def test_parses_from_existing_env(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["create", "--from-existing-env", "astro-py", "--name", "myproject"]
        )
        assert args.from_existing_env == "astro-py"
        assert args.name == "myproject"

    def test_from_existing_env_mutually_exclusive(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(
                [
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

    def test_legacy_env_group_rejected(self):
        """``env`` is no longer a command group — a bare ``hubenv env`` must fail.

        The former ``hubenv env <verb>`` surface was flattened to top-level
        verbs; a bare ``hubenv env`` is now an invalid command, so argparse
        rejects it with exit code 2.
        """
        from nb_wrangler.hubenv.cli import main

        with pytest.raises(SystemExit) as exc:
            main(["env"])
        assert exc.value.code == 2


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
# hubenv create --from-existing-env tests
# ---------------------------------------------------------------------------


class TestCreateFromExistingEnv:
    """Tests for hubenv create --from-existing-env CLI."""

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
                    "create",
                    "--from-existing-env",
                    "astro-py",
                    "--name",
                    "myproject",
                ]
            )

        assert rc == 0
        shadow = (
            tmp_path / "pantry" / "shelves" / "myproject" / "nbw-wrangler-spec.yaml"
        )
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
        shadow = (
            tmp_path / "pantry" / "shelves" / "myproject" / "nbw-wrangler-spec.yaml"
        )
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
                    "create",
                    "--from-existing-env",
                    "astro-py",
                    "--name",
                    "myproject",
                ]
            )

        assert rc == 1


# ---------------------------------------------------------------------------
# Default persistence: all install sources persist spec + register kernel
# ---------------------------------------------------------------------------


class TestDefaultPersist:
    """All four install sources persist the shelf spec and register the
    kernel by default (no extra flags needed)."""

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

    @pytest.fixture
    def _pantry(self, tmp_path):
        pantry = tmp_path / "pantry"
        pantry.mkdir(exist_ok=True)
        return pantry

    def _shelf_spec(self, pantry, name):
        return pantry / "shelves" / name / "nbw-wrangler-spec.yaml"

    def test_from_empty_persists_and_registers(self, tmp_path, _pantry):
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [_pantry]),
            patch.object(
                EnvironmentManager, "create_environment", return_value=True
            ) as mock_create,
            patch.object(
                EnvironmentManager, "register_environment", return_value=True
            ) as mock_register,
        ):
            rc = main(["create", "--from-empty", "--name", "demo"])

        assert rc == 0
        mock_create.assert_called_once()
        mock_register.assert_called_once()
        assert self._shelf_spec(_pantry, "demo").exists()

    def test_from_requirements_persists_and_registers(self, tmp_path, _pantry):
        from nb_wrangler.hubenv.cli import main

        reqs = tmp_path / "reqs.txt"
        reqs.write_text("numpy==1.26.0\npandas\n")

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [_pantry]),
            patch.object(
                EnvironmentManager, "create_environment", return_value=True
            ) as mock_create,
            patch.object(
                EnvironmentManager, "register_environment", return_value=True
            ) as mock_register,
        ):
            rc = main(
                [
                    "create",
                    "--from-requirements",
                    str(reqs),
                    "--name",
                    "demo",
                    "--python",
                    "3.11",
                ]
            )

        assert rc == 0
        mock_create.assert_called_once()
        mock_register.assert_called_once()
        assert self._shelf_spec(_pantry, "demo").exists()

    def test_from_mamba_spec_persists_and_registers(self, tmp_path, _pantry):
        from nb_wrangler.hubenv.cli import main

        mspec = tmp_path / "mamba-spec.yaml"
        mspec.write_text(_MAMBA_SPEC_YAML)

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [_pantry]),
            patch.object(
                EnvironmentManager, "create_environment", return_value=True
            ) as mock_create,
            patch.object(
                EnvironmentManager, "register_environment", return_value=True
            ) as mock_register,
        ):
            rc = main(
                [
                    "create",
                    "--from-mamba-spec",
                    str(mspec),
                    "--name",
                    "demo",
                ]
            )

        assert rc == 0
        mock_create.assert_called_once()
        mock_register.assert_called_once()
        assert self._shelf_spec(_pantry, "demo").exists()

    def test_from_wrangler_spec_persists_and_registers(self, tmp_path, _pantry):
        from nb_wrangler.hubenv.cli import main

        wspec = tmp_path / "wrangler-spec.yaml"
        wspec.write_text(_WRANGLER_SPEC_YAML)

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [_pantry]),
            patch.object(
                EnvironmentManager, "create_environment", return_value=True
            ) as mock_create,
            patch.object(
                EnvironmentManager, "register_environment", return_value=True
            ) as mock_register,
        ):
            rc = main(
                [
                    "create",
                    "--from-wrangler-spec",
                    str(wspec),
                    "--name",
                    "demo",
                ]
            )

        assert rc == 0
        mock_create.assert_called_once()
        mock_register.assert_called_once()
        assert self._shelf_spec(_pantry, "demo").exists()

    def test_install_failure_no_persistence(self, tmp_path, _pantry, capsys):
        from nb_wrangler.hubenv.cli import main

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [_pantry]),
            patch.object(EnvironmentManager, "create_environment", return_value=False),
            patch.object(EnvironmentManager, "register_environment") as mock_register,
        ):
            rc = main(["create", "--from-empty", "--name", "demo"])

        assert rc == 1
        mock_register.assert_not_called()
        assert not self._shelf_spec(_pantry, "demo").exists()


# ---------------------------------------------------------------------------
# --ephemeral: opt out of persistence
# ---------------------------------------------------------------------------


class TestEphemeral:
    """``--ephemeral`` builds the live env but skips shelf spec and kernel."""

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

    def test_from_empty_ephemeral_skips_persistence(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        pantry = tmp_path / "pantry"
        pantry.mkdir(exist_ok=True)

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [pantry]),
            patch.object(
                EnvironmentManager, "create_environment", return_value=True
            ) as mock_create,
            patch.object(EnvironmentManager, "register_environment") as mock_register,
        ):
            rc = main(["create", "--from-empty", "--name", "demo", "--ephemeral"])

        assert rc == 0
        mock_create.assert_called_once()
        mock_register.assert_not_called()
        spec = pantry / "shelves" / "demo" / "nbw-wrangler-spec.yaml"
        assert not spec.exists()
        err = capsys.readouterr().err
        assert "ephemeral" in err.lower()

    def test_from_existing_env_ephemeral_skips_persistence(self, tmp_path, capsys):
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
            patch("nb_wrangler.hubenv.seeds._run_pip_freeze", return_value=[]),
            patch.object(EnvironmentManager, "environment_exists", return_value=True),
            patch.object(EnvironmentManager, "register_environment") as mock_register,
        ):
            rc = main(
                [
                    "create",
                    "--from-existing-env",
                    "astro-py",
                    "--name",
                    "myproject",
                    "--ephemeral",
                ]
            )

        assert rc == 0
        mock_register.assert_not_called()
        spec = pantry / "shelves" / "myproject" / "nbw-wrangler-spec.yaml"
        assert not spec.exists()


# ---------------------------------------------------------------------------
# --pantry: forced pantry directory is honored
# ---------------------------------------------------------------------------


class TestPantryFlag:
    """``--pantry`` forces the shelf spec into the named pantry."""

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

    def test_pantry_flag_writes_to_forced_pantry(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        default_pantry = tmp_path / "default-pantry"
        default_pantry.mkdir(exist_ok=True)
        forced_pantry = tmp_path / "forced-pantry"
        forced_pantry.mkdir(exist_ok=True)

        with (
            patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
            patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [default_pantry]),
            patch.object(EnvironmentManager, "create_environment", return_value=True),
            patch.object(EnvironmentManager, "register_environment", return_value=True),
        ):
            rc = main(
                [
                    "create",
                    "--from-empty",
                    "--name",
                    "demo",
                    "--pantry",
                    str(forced_pantry),
                ]
            )

        assert rc == 0
        forced_spec = forced_pantry / "shelves" / "demo" / "nbw-wrangler-spec.yaml"
        default_spec = default_pantry / "shelves" / "demo" / "nbw-wrangler-spec.yaml"
        assert forced_spec.exists()
        assert not default_spec.exists()

    def test_pantry_flag_ro_pantry_fails(self, tmp_path, capsys):
        import os

        from nb_wrangler.hubenv.cli import main

        default_pantry = tmp_path / "default-pantry"
        default_pantry.mkdir(exist_ok=True)
        ro_pantry = tmp_path / "ro-pantry"
        ro_pantry.mkdir(exist_ok=True)
        os.chmod(ro_pantry, 0o500)

        try:
            with (
                patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path),
                patch("nb_wrangler.hubenv.config.NBW_PANTRY_DIRS", [default_pantry]),
                patch.object(
                    EnvironmentManager, "create_environment", return_value=True
                ),
            ):
                rc = main(
                    [
                        "create",
                        "--from-empty",
                        "--name",
                        "demo",
                        "--pantry",
                        str(ro_pantry),
                    ]
                )

            assert rc == 1
            spec = default_pantry / "shelves" / "demo" / "nbw-wrangler-spec.yaml"
            assert not spec.exists()
        finally:
            os.chmod(ro_pantry, 0o700)


# ---------------------------------------------------------------------------
# Parser: --ephemeral flag
# ---------------------------------------------------------------------------


class TestEphemeralParser:
    """``--ephemeral`` parses correctly and defaults to False."""

    def test_ephemeral_flag_parses(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            [
                "create",
                "--from-empty",
                "--name",
                "demo",
                "--ephemeral",
            ]
        )
        assert args.ephemeral is True

    def test_ephemeral_defaults_false(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["create", "--from-empty", "--name", "demo"])
        assert args.ephemeral is False
