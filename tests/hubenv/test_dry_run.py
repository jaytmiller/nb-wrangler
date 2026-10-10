"""Tests for hubenv env create --dry-run and seed building (Phase 1)."""

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


# ---------------------------------------------------------------------------
# create --dry-run
# ---------------------------------------------------------------------------


class TestDryRun:
    """Tests for hubenv env create --dry-run."""

    def test_dry_run_empty_prints_spec(self, capsys):
        from nb_wrangler.hubenv.cli import main

        rc = main(
            [
                "env",
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

    def test_dry_run_requirements_prints_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        req = tmp_path / "requirements.txt"
        req.write_text("numpy>=1.20\npandas\n  # comment\n\n")

        rc = main(
            [
                "env",
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
                "env",
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
                "env",
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

    def test_dry_run_notebooks_prints_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        nb = tmp_path / "test.ipynb"
        nb.write_text(
            '{"cells":[{"cell_type":"code","source":["import os\\n", "import pandas as pd\\n"]}]}'
        )

        rc = main(
            [
                "env",
                "create",
                "--from-notebooks",
                str(nb),
                "--name",
                "demo",
                "--dry-run",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "name: demo" in out
        assert "pandas" in out

    def test_dry_run_does_not_install(self, tmp_path, capsys):
        """Verify no environment is created during dry-run."""
        from nb_wrangler.hubenv.cli import main

        with patch(
            "nb_wrangler.environment.EnvironmentManager.create_environment"
        ) as mock_create:
            rc = main(["env", "create", "--from-empty", "--name", "demo", "--dry-run"])
            assert rc == 0
            mock_create.assert_not_called()


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

    def test_seed_from_empty_without_python(self):
        from nb_wrangler.hubenv.seeds import seed_from_empty

        spec = seed_from_empty("demo")
        assert "python=3.11" not in spec["dependencies"]
        assert "pip" in spec["dependencies"]

    def test_seed_from_requirements_strips_comments(self, tmp_path):
        from nb_wrangler.hubenv.seeds import seed_from_requirements

        req = tmp_path / "requirements.txt"
        req.write_text("numpy>=1.20\n# comment\n\npandas\n")
        spec = seed_from_requirements("demo", [str(req)])
        pip_deps = [d for d in spec["dependencies"] if isinstance(d, dict)]
        assert pip_deps == [{"pip": ["numpy>=1.20", "pandas"]}]

    def test_seed_from_mamba_spec_overrides_name(self, tmp_path):
        from nb_wrangler.hubenv.seeds import seed_from_mamba_spec

        spec_file = tmp_path / "env.yaml"
        spec_file.write_text("name: old-name\ndependencies:\n  - numpy\n")
        spec = seed_from_mamba_spec("new-name", str(spec_file))
        assert spec["name"] == "new-name"

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

    def test_seed_from_notebooks_extracts_imports(self, tmp_path):
        from nb_wrangler.hubenv.seeds import seed_from_notebooks

        nb = tmp_path / "test.ipynb"
        nb.write_text(
            '{"cells":[{"cell_type":"code","source":'
            '["import numpy as np\\n", "from pandas import DataFrame\\n"]},'
            '{"cell_type":"markdown","source":"# title"}]}'
        )
        spec = seed_from_notebooks("demo", [str(nb)])
        pip_deps = [d for d in spec["dependencies"] if isinstance(d, dict)]
        assert "numpy" in pip_deps[0]["pip"]
        assert "pandas" in pip_deps[0]["pip"]

    def test_seed_from_notebooks_filters_stdlib(self, tmp_path):
        """BUILTIN_PACKAGES (os, sys, ...) must not leak into the pip list."""
        from nb_wrangler.hubenv.seeds import seed_from_notebooks

        nb = tmp_path / "test.ipynb"
        nb.write_text(
            '{"cells":[{"cell_type":"code","source":'
            '["import os\\n", "import sys\\n", "import numpy as np\\n"]},'
            '{"cell_type":"markdown","source":"# title"}]}'
        )
        spec = seed_from_notebooks("demo", [str(nb)])
        pip_deps = [d for d in spec["dependencies"] if isinstance(d, dict)]
        assert "numpy" in pip_deps[0]["pip"]
        assert "os" not in pip_deps[0]["pip"]
        assert "sys" not in pip_deps[0]["pip"]
