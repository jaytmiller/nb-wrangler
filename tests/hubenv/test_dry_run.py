"""Tests for hubenv create --dry-run and seed building (Phase 1)."""

from unittest.mock import patch

import pytest

from nb_wrangler.config import WranglerConfig, set_args_config

# Hybrid inline spec: header kernel_name/python_version differ from the
# second document's name/python pin — exercises the header > inline
# delegation (permitted by the relaxed wrangler spec format).
_HYBRID_SRC = """\
image_spec_header:
  image_name: hybrid
  kernel_name: hybrid-header
  display_name: hybrid
  deployment_name: wrangler
  valid_on: 1970-01-01
  expires_on: 2099-12-31
  python_version: "3.11"
repositories: {}
extra_mamba_packages:
  - scipy
extra_pip_packages:
  - pandas
---
name: hybrid-inline
channels:
  - conda-forge
dependencies:
  - python=3.10
  - numpy
  - pip
  - pip:
      - scikit-learn
"""


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


# ---------------------------------------------------------------------------
# create --dry-run
# ---------------------------------------------------------------------------


class TestDryRun:
    """Tests for hubenv create --dry-run."""

    def test_dry_run_empty_prints_spec(self, capsys):
        from nb_wrangler.hubenv.cli import main

        rc = main(
            [
                "create",
                "--from-empty",
                "--name",
                "demo",
                "--python",
                "3.11",
                "--dry-run",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "name: demo" in out
        assert "python=3.11" in out
        assert "conda-forge" in out
        # The empty env installs at least the hubenv support packages.
        assert "ipykernel" in out
        # No hubenv-internal flags (e.g. _hubenv_display_name) leak to stdout.
        assert "_hubenv_" not in out

    def test_dry_run_requirements_prints_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        req = tmp_path / "requirements.txt"
        req.write_text("numpy>=1.20\npandas\n  # comment\n\n")

        rc = main(
            [
                "create",
                "--from-requirements",
                str(req),
                "--name",
                "demo",
                "--dry-run",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "name: demo" in out
        assert "numpy>=1.20" in out
        assert "pandas" in out

    def test_dry_run_mamba_spec_prints_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        spec_file = tmp_path / "env.yaml"
        spec_file.write_text(
            "name: old-name\nchannels:\n  - conda-forge\ndependencies:\n  - numpy\n"
        )
        rc = main(
            [
                "create",
                "--from-mamba-spec",
                str(spec_file),
                "--name",
                "demo",
                "--dry-run",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "name: demo" in out
        assert "numpy" in out

    def test_dry_run_wrangler_spec_prints_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        spec_file = tmp_path / "wrangler.yaml"
        spec_file.write_text(
            "image_spec_header:\n"
            "  kernel_name: astro-py\n"
            "  python_version: 3.11\n"
            "extra_mamba_packages:\n  - numpy\n"
            "  - pip\n"
            "extra_pip_packages:\n  - requests\n"
        )
        rc = main(
            [
                "create",
                "--from-wrangler-spec",
                str(spec_file),
                "--name",
                "demo",
                "--dry-run",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "name: demo" in out
        assert "python=3.11" in out
        assert "numpy" in out
        assert "requests" in out
        # No hubenv-internal flags (e.g. _hubenv_inline, _hubenv_display_name).
        assert "_hubenv_" not in out

    def test_dry_run_does_not_install(self, tmp_path, capsys):
        """Verify no environment is created during dry-run."""
        from nb_wrangler.hubenv.cli import main

        with patch(
            "nb_wrangler.environment.EnvironmentManager.create_environment"
        ) as mock_create:
            rc = main(["create", "--from-empty", "--name", "demo", "--dry-run"])
            assert rc == 0
            mock_create.assert_not_called()

    def test_dry_run_without_name_derives_it(self, tmp_path, capsys):
        """No ``--name``: name is derived from the wrangler spec header."""
        from nb_wrangler.hubenv.cli import main

        spec_file = tmp_path / "wrangler.yaml"
        spec_file.write_text(
            "image_spec_header:\n"
            "  kernel_name: astro-py\n"
            "  python_version: 3.11\n"
        )
        rc = main(["create", "--from-wrangler-spec", str(spec_file), "--dry-run"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "name: astro-py" in out
        assert "python=3.11" in out


# ---------------------------------------------------------------------------
# Seed builders
# ---------------------------------------------------------------------------


class TestSeedBuilders:
    """Tests for seed builder functions."""

    def test_seed_from_empty_with_python(self):
        from nb_wrangler.hubenv.seeds import seed_from_empty

        spec = seed_from_empty("demo", "3.11")
        assert spec["name"] == "demo"
        assert "python=3.11" in spec["dependencies"]
        assert "pip" in spec["dependencies"]
        assert self._has_target_packages(spec)

    def test_seed_from_empty_without_python(self):
        from nb_wrangler.hubenv.seeds import seed_from_empty

        spec = seed_from_empty("demo")
        assert "python=3.11" not in spec["dependencies"]
        assert "pip" in spec["dependencies"]
        assert self._has_target_packages(spec)

    @staticmethod
    def _has_target_packages(spec) -> bool:
        from nb_wrangler.constants import TARGET_PACKAGES

        pip_deps = [d for d in spec["dependencies"] if isinstance(d, dict)]
        assert pip_deps == [{"pip": list(TARGET_PACKAGES)}]
        assert "ipykernel" in pip_deps[0]["pip"]
        return True

    @staticmethod
    def _pip_packages(spec) -> list[str]:
        """Return the single pip sub-dict's package list from a mamba view."""
        pip_deps = [
            d for d in spec["dependencies"] if isinstance(d, dict) and "pip" in d
        ]
        assert len(pip_deps) == 1, f"expected one pip section, got {pip_deps}"
        return pip_deps[0]["pip"]

    def test_seed_from_requirements_strips_comments(self, tmp_path):
        from nb_wrangler.constants import TARGET_PACKAGES
        from nb_wrangler.hubenv.seeds import seed_from_requirements

        req = tmp_path / "requirements.txt"
        req.write_text("numpy>=1.20\n# comment\n\npandas\n")
        spec = seed_from_requirements("demo", [str(req)])
        pip_list = self._pip_packages(spec)
        # Requested packages are present and comment/blank lines are dropped.
        assert "numpy>=1.20" in pip_list
        assert "pandas" in pip_list
        assert all(p for p in pip_list)
        # The baseline TARGET_PACKAGES are always installed alongside them.
        for pkg in TARGET_PACKAGES:
            assert pkg in pip_list

    def test_seed_from_mamba_spec_overrides_name(self, tmp_path):
        from nb_wrangler.hubenv.seeds import seed_from_mamba_spec

        spec_file = tmp_path / "env.yaml"
        spec_file.write_text("name: old-name\ndependencies:\n  - numpy\n")
        spec = seed_from_mamba_spec("new-name", str(spec_file))
        assert spec["name"] == "new-name"

    def test_seed_from_mamba_spec_defaults_name_to_spec_name(self, tmp_path):
        """No explicit name: defaults to the spec file's own ``name``."""
        from nb_wrangler.hubenv.seeds import seed_from_mamba_spec

        spec_file = tmp_path / "env.yaml"
        spec_file.write_text("name: old-name\ndependencies:\n  - numpy\n")
        spec = seed_from_mamba_spec(None, str(spec_file))
        assert spec["name"] == "old-name"

    def test_seed_from_mamba_spec_no_name_raises(self, tmp_path):
        """No explicit name and no spec ``name``: a clean error, no stem."""
        from nb_wrangler.hubenv.seeds import seed_from_mamba_spec

        spec_file = tmp_path / "my-spec.yaml"
        spec_file.write_text("channels:\n  - conda-forge\ndependencies:\n  - numpy\n")
        with pytest.raises(ValueError, match="has no 'name' field"):
            seed_from_mamba_spec(None, str(spec_file))

    def test_seed_from_wrangler_spec_extracts_packages(self, tmp_path):
        from nb_wrangler.hubenv.seeds import seed_from_wrangler_spec

        spec_file = tmp_path / "wrangler.yaml"
        spec_file.write_text(
            "image_spec_header:\n"
            "  kernel_name: astro-py\n"
            "  python_version: 3.11\n"
            "extra_mamba_packages:\n  - numpy\n"
            "  - pip\n"
            "extra_pip_packages:\n  - requests\n"
            "  - matplotlib\n"
        )
        spec = seed_from_wrangler_spec("demo", str(spec_file))
        assert spec["name"] == "demo"
        assert "python=3.11" in spec["dependencies"]
        assert "numpy" in spec["dependencies"]
        # pip should not be duplicated
        assert spec["dependencies"].count("pip") == 1
        pip_deps = [d for d in spec["dependencies"] if isinstance(d, dict)]
        assert "requests" in pip_deps[0]["pip"]
        assert "matplotlib" in pip_deps[0]["pip"]

    def test_seed_from_wrangler_spec_defaults_name_to_kernel_name(self, tmp_path):
        """No explicit name: defaults to the header's ``kernel_name``."""
        from nb_wrangler.hubenv.seeds import seed_from_wrangler_spec

        spec_file = tmp_path / "wrangler.yaml"
        spec_file.write_text(
            "image_spec_header:\n"
            "  kernel_name: astro-py\n"
            "  python_version: 3.11\n"
        )
        spec = seed_from_wrangler_spec(None, str(spec_file))
        assert spec["name"] == "astro-py"

    def test_seed_from_wrangler_spec_falls_back_to_image_name(self, tmp_path):
        """No ``kernel_name``: falls back to the header's ``image_name``."""
        from nb_wrangler.hubenv.seeds import seed_from_wrangler_spec

        spec_file = tmp_path / "wrangler.yaml"
        spec_file.write_text(
            "image_spec_header:\n" "  image_name: img-x\n" "  python_version: 3.11\n"
        )
        spec = seed_from_wrangler_spec(None, str(spec_file))
        assert spec["name"] == "img-x"

    def test_seed_from_wrangler_spec_no_name_raises(self, tmp_path):
        """No ``kernel_name``/``image_name`` and no inline ``name``: clean error."""
        from nb_wrangler.hubenv.seeds import seed_from_wrangler_spec

        spec_file = tmp_path / "my-wrangler.yaml"
        spec_file.write_text("image_spec_header:\n" "  python_version: 3.11\n")
        with pytest.raises(ValueError, match="defines no environment name"):
            seed_from_wrangler_spec(None, str(spec_file))

    def test_seed_from_wrangler_spec_python_override(self, tmp_path):
        """An explicit *python* overrides the header's ``python_version``."""
        from nb_wrangler.hubenv.seeds import seed_from_wrangler_spec

        spec_file = tmp_path / "wrangler.yaml"
        spec_file.write_text(
            "image_spec_header:\n"
            "  kernel_name: astro-py\n"
            "  python_version: 3.11\n"
            "extra_pip_packages:\n  - requests\n"
        )
        spec = seed_from_wrangler_spec("demo", str(spec_file), "3.10")
        assert spec["name"] == "demo"
        assert "python=3.10" in spec["dependencies"]
        assert not any(d == "python=3.11" for d in spec["dependencies"])

    def _hybrid_seed(self, tmp_path, name=None, python=None):
        from nb_wrangler.hubenv.seeds import seed_from_wrangler_spec

        src = tmp_path / "hybrid.yaml"
        src.write_text(_HYBRID_SRC)
        return seed_from_wrangler_spec(name, str(src), python)

    def test_seed_from_wrangler_spec_header_wins_over_inline_name(
        self, tmp_path, caplog
    ):
        """Header name != inline name (no CLI): header wins, override logged."""
        import logging

        caplog.set_level(logging.INFO)
        spec = self._hybrid_seed(tmp_path)
        assert spec["name"] == "hybrid-header"
        assert (
            "Using wrangler header name 'hybrid-header' instead of "
            "inline mamba spec name 'hybrid-inline'."
        ) in caplog.text

    def test_seed_from_wrangler_spec_header_wins_over_inline_python(
        self, tmp_path, caplog
    ):
        """Header python != inline pin (no CLI): header wins, override logged."""
        import logging

        caplog.set_level(logging.INFO)
        spec = self._hybrid_seed(tmp_path)
        assert "python=3.11" in spec["dependencies"]
        assert not any(d == "python=3.10" for d in spec["dependencies"])
        assert (
            "Using wrangler header python_version '3.11' instead of "
            "inline mamba spec python '3.10'."
        ) in caplog.text

    def test_seed_from_wrangler_spec_cli_overrides_logged(self, tmp_path, caplog):
        """CLI values differ from header: both overrides logged (CLI)."""
        import logging

        caplog.set_level(logging.INFO)
        spec = self._hybrid_seed(tmp_path, name="cli-env", python="3.12")
        assert spec["name"] == "cli-env"
        assert "python=3.12" in spec["dependencies"]
        out = caplog.text
        assert "Overriding name from 'hybrid-header' to 'cli-env' (CLI)." in out
        assert "Overriding python from '3.11' to '3.12' (CLI)." in out

    def test_seed_from_mamba_spec_includes_target_packages(self, tmp_path):
        from nb_wrangler.constants import TARGET_PACKAGES
        from nb_wrangler.hubenv.seeds import seed_from_mamba_spec

        spec_file = tmp_path / "env.yaml"
        spec_file.write_text("name: old-name\ndependencies:\n  - numpy\n")
        spec = seed_from_mamba_spec("new-name", str(spec_file))
        # The source spec's own conda dependency is preserved.
        assert "numpy" in spec["dependencies"]
        # Baseline TARGET_PACKAGES are guaranteed as pip packages.
        pip_list = self._pip_packages(spec)
        for pkg in TARGET_PACKAGES:
            assert pkg in pip_list

    def test_seed_from_wrangler_spec_includes_target_packages(self, tmp_path):
        from nb_wrangler.constants import TARGET_PACKAGES
        from nb_wrangler.hubenv.seeds import seed_from_wrangler_spec

        spec_file = tmp_path / "wrangler.yaml"
        spec_file.write_text(
            "image_spec_header:\n"
            "  python_version: 3.11\n"
            "extra_pip_packages:\n  - requests\n"
        )
        spec = seed_from_wrangler_spec("demo", str(spec_file))
        pip_list = self._pip_packages(spec)
        assert "requests" in pip_list
        for pkg in TARGET_PACKAGES:
            assert pkg in pip_list

    def test_seed_from_existing_env_includes_target_packages(self):
        from unittest.mock import patch

        from nb_wrangler.constants import TARGET_PACKAGES
        from nb_wrangler.hubenv.seeds import seed_from_existing_env

        export = "name: src\nchannels:\n  - conda-forge\ndependencies:\n  - numpy\n"
        with (
            patch(
                "nb_wrangler.hubenv.seeds._run_mamba_export",
                return_value=export,
            ),
            patch("nb_wrangler.hubenv.seeds._run_pip_freeze", return_value=[]),
        ):
            spec = seed_from_existing_env("target", "src")
        # Even with no pip packages in the source, the baseline is guaranteed.
        pip_list = self._pip_packages(spec)
        for pkg in TARGET_PACKAGES:
            assert pkg in pip_list

    def test_seed_from_mamba_spec_python_override_and_preserve(self, tmp_path, caplog):
        """CLI *python* replaces the spec's own pin (logged); no CLI preserves it."""
        import logging

        caplog.set_level(logging.INFO)
        from nb_wrangler.hubenv.seeds import seed_from_mamba_spec

        spec_file = tmp_path / "env.yaml"
        spec_file.write_text(
            "name: old-name\nchannels:\n  - conda-forge\ndependencies:\n"
            "  - python=3.11\n  - numpy\n"
        )
        spec = seed_from_mamba_spec("new-name", str(spec_file), python="3.12")
        assert "python=3.12" in spec["dependencies"]
        assert not any(
            d == "python=3.11" for d in spec["dependencies"] if isinstance(d, str)
        )
        assert "numpy" in spec["dependencies"]  # other deps preserved
        assert "Overriding python from '3.11' to '3.12' (CLI)." in caplog.text

        spec = seed_from_mamba_spec("new-name", str(spec_file))
        assert "python=3.11" in spec["dependencies"]  # source pin kept

    def test_seed_from_mamba_spec_python_change_clears_compiled_lock(
        self, tmp_path, caplog
    ):
        """A python bump drops stale compiled pip lock entries (logged)."""
        import logging

        caplog.set_level(logging.INFO)
        from nb_wrangler.hubenv.seeds import seed_from_mamba_spec

        spec_file = tmp_path / "env.yaml"
        spec_file.write_text(
            "name: old-name\nchannels:\n  - conda-forge\ndependencies:\n"
            "  - python=3.11\n  - pip\n"
            "  - pip:\n"
            '    - "scikit-learn==1.0.0-cp311-cp311-manylinux_2_17"\n'
            "    - plain-pkg\n"
        )
        spec = seed_from_mamba_spec(None, str(spec_file), python="3.12")
        assert "python=3.12" in spec["dependencies"]
        pip_list = self._pip_packages(spec)
        assert not any("cp311" in p for p in pip_list)
        assert "plain-pkg" in pip_list
        assert (
            "Cleared 1 stale compiled pip lock entries for python '3.11'; "
            "seed now targets python '3.12'."
        ) in caplog.text

    def test_seed_display_name_flags_and_defaults(self, tmp_path):
        """Every seed builder stores the resolved display name in the seed."""
        import nb_wrangler.hubenv.seeds as seeds

        assert seeds.seed_from_empty("a")["name"] == "a"
        assert seeds.seed_from_empty("a")[seeds.DISPLAY_NAME_FLAG] == "a"
        assert (
            seeds.seed_from_empty("a", display_name="D A")[seeds.DISPLAY_NAME_FLAG]
            == "D A"
        )

        req = tmp_path / "requirements.txt"
        req.write_text("numpy\n")
        assert (
            seeds.seed_from_requirements("b", [str(req)], display_name="D B")[
                seeds.DISPLAY_NAME_FLAG
            ]
            == "D B"
        )
        assert (
            seeds.seed_from_requirements("b", [str(req)])[seeds.DISPLAY_NAME_FLAG]
            == "b"
        )

        mspec = tmp_path / "m.yaml"
        mspec.write_text(
            "name: m\nchannels:\n  - conda-forge\ndependencies:\n  - numpy\n"
        )
        assert (
            seeds.seed_from_mamba_spec(None, str(mspec))[seeds.DISPLAY_NAME_FLAG] == "m"
        )
        assert (
            seeds.seed_from_mamba_spec(None, str(mspec), display_name="D M")[
                seeds.DISPLAY_NAME_FLAG
            ]
            == "D M"
        )
