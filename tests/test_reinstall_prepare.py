"""Tests for the --reinstall workflow's spec-only preparation step.

Verifies that _reinstall_prepare_from_spec reads resolved repository states,
notebook paths, and notebook imports from the spec output section instead of
cloning source repositories.
"""

from pathlib import Path

import yaml

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.wrangler import NotebookWrangler


def _make_reinstall_spec(tmp_path: Path) -> Path:
    """Create a precompiled spec with output data for a --reinstall run."""
    spec_dict = {
        "image_spec_header": {
            "image_name": "test-reinstall",
            "kernel_name": "test-reinstall",
            "deployment_name": "wrangler",
            "python_version": "3.12",
            "valid_on": "2026-01-01",
            "expires_on": "2027-01-01",
        },
        "repositories": {
            "roman_notebooks": {
                "url": "https://github.com/spacetelescope/roman_notebooks.git",
                "ref": "2026.2",
            },
        },
        "extra_mamba_packages": [],
        "common_mamba_packages": [],
        "extra_pip_packages": [],
        "common_pip_packages": [],
        "apt_packages": [],
        "system": {
            "spec_version": 2.3,
            "spi": {
                "repo": "https://github.com/spacetelescope/science-platform-images.git",
                "ref": "main",
            },
            "nb-wrangler": {
                "repo": "https://github.com/spacetelescope/nb-wrangler.git",
                "ref": "main",
            },
            "date_updated": "2026-01-01T00:00:00",
        },
        "selected_notebooks": {
            "roman_all": {
                "repo": "roman_notebooks",
                "root_directory": "notebooks/",
                "include_subdirs": [".*"],
            },
        },
        "out": {
            "repositories": {
                "roman_notebooks": {
                    "url": "https://github.com/spacetelescope/roman_notebooks.git",
                    "ref": "9caddd9e6228acdb1ef5909c9fd7cad0f79d4fce",
                    "resolved_ref": "main",
                },
            },
            "spi": {
                "repo": "https://github.com/spacetelescope/science-platform-images.git",
                "ref": "2053bb31a779fb9b5a155066c250d8d03d7bc98a",
            },
            "test_notebooks": {
                "references/roman_notebooks/notebooks/pandeia/pandeia.ipynb": "roman_all",
                "references/roman_notebooks/notebooks/synphot/synphot.ipynb": "roman_all",
            },
            "nb_to_imports": {
                "references/roman_notebooks/notebooks/pandeia/pandeia.ipynb": [
                    "astropy",
                    "numpy",
                ],
                "references/roman_notebooks/notebooks/synphot/synphot.ipynb": [
                    "astropy",
                    "numpy",
                ],
            },
            "mamba_spec": "name: test-reinstall\nchannels:\n  - conda-forge\ndependencies:\n  - pip\n  - python=3.12\n",
            "pip_compiler_output": "numpy==2.0.0\nastropy==7.0.0\n",
        },
    }

    spec_file = tmp_path / "reinstall-spec.yaml"
    spec_file.write_text(yaml.dump(spec_dict, default_flow_style=False))
    return spec_file


class TestReinstallPrepareFromSpec:
    """Tests that _reinstall_prepare_from_spec avoids cloning repos."""

    def test_reinstall_uses_spec_output_not_repos(self, tmp_path):
        """Verify no repo cloning occurs and spec output is preserved."""
        spec_file = _make_reinstall_spec(tmp_path)

        config = WranglerConfig(
            workflows=["reinstall"],
            spec_file=str(spec_file),
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
            prod=True,
        )
        set_args_config(config)
        wrangler = NotebookWrangler()

        # Track whether repo_manager.prepare_repositories is called.
        clone_calls = []

        def fake_prepare_repositories(repos_to_prepare, floating_mode=True):
            clone_calls.append(repos_to_prepare)
            return {}, {}

        # Inject the spy onto the repo_manager.
        original = wrangler.repo_manager.prepare_repositories
        wrangler.repo_manager.prepare_repositories = fake_prepare_repositories

        try:
            result = wrangler._reinstall_prepare_from_spec()
        finally:
            wrangler.repo_manager.prepare_repositories = original

        assert result is True
        # The spy should never have been invoked: no cloning should occur.
        assert clone_calls == [], (
            "Expected no repo cloning during reinstall, "
            f"but prepare_repositories was called {len(clone_calls)} times."
        )

    def test_reinstall_preserves_repositories_in_spec(self, tmp_path):
        """Verify repository refs from spec output are preserved."""
        spec_file = _make_reinstall_spec(tmp_path)

        config = WranglerConfig(
            workflows=["reinstall"],
            spec_file=str(spec_file),
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
            prod=True,
        )
        set_args_config(config)
        wrangler = NotebookWrangler()

        wrangler._reinstall_prepare_from_spec()

        output_repos = wrangler.spec_manager.get_output_data("repositories", {})
        expected_sha = "9caddd9e6228acdb1ef5909c9fd7cad0f79d4fce"
        assert (
            output_repos["roman_notebooks"]["ref"] == expected_sha
        ), "Repository ref should be preserved from spec output"

    def test_reinstall_preserves_test_notebooks(self, tmp_path):
        """Verify test_notebooks from spec output are preserved."""
        spec_file = _make_reinstall_spec(tmp_path)

        config = WranglerConfig(
            workflows=["reinstall"],
            spec_file=str(spec_file),
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
            prod=True,
        )
        set_args_config(config)
        wrangler = NotebookWrangler()

        wrangler._reinstall_prepare_from_spec()

        test_notebooks = wrangler.spec_manager.get_output_data("test_notebooks", [])
        assert len(test_notebooks) == 2
        assert (
            "references/roman_notebooks/notebooks/pandeia/pandeia.ipynb"
            in test_notebooks
        )
        assert (
            "references/roman_notebooks/notebooks/synphot/synphot.ipynb"
            in test_notebooks
        )

    def test_reinstall_preserves_nb_to_imports(self, tmp_path):
        """Verify nb_to_imports from spec output are preserved."""
        spec_file = _make_reinstall_spec(tmp_path)

        config = WranglerConfig(
            workflows=["reinstall"],
            spec_file=str(spec_file),
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
            prod=True,
        )
        set_args_config(config)
        wrangler = NotebookWrangler()

        wrangler._reinstall_prepare_from_spec()

        nb_to_imports = wrangler.spec_manager.get_output_data("nb_to_imports", {})
        assert len(nb_to_imports) == 2
        for imports in nb_to_imports.values():
            assert "astropy" in imports
            assert "numpy" in imports

    def test_reinstall_fails_without_output_repos(self, tmp_path):
        """Verify error when spec has no output repository data."""
        spec_dict = {
            "image_spec_header": {
                "image_name": "test",
                "kernel_name": "test",
                "deployment_name": "wrangler",
                "python_version": "3.12",
                "valid_on": "2026-01-01",
                "expires_on": "2027-01-01",
            },
            "repositories": {},
            "extra_mamba_packages": [],
            "common_mamba_packages": [],
            "extra_pip_packages": [],
            "common_pip_packages": [],
            "apt_packages": [],
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "https://example.com/spi.git"},
                "nb-wrangler": {"repo": "https://example.com/nbw.git"},
                "date_updated": "2026-01-01T00:00:00",
            },
            "selected_notebooks": {},
            "out": {},
        }

        spec_file = tmp_path / "no-output-spec.yaml"
        spec_file.write_text(yaml.dump(spec_dict, default_flow_style=False))

        config = WranglerConfig(
            workflows=["reinstall"],
            spec_file=str(spec_file),
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
            prod=True,
        )
        set_args_config(config)
        wrangler = NotebookWrangler()

        result = wrangler._reinstall_prepare_from_spec()
        assert result is False, "Should fail when no output repository data exists"

    def test_reinstall_workflow_uses_new_step(self, tmp_path):
        """Verify the reinstall workflow is wired to _reinstall_prepare_from_spec."""
        spec_file = _make_reinstall_spec(tmp_path)

        config = WranglerConfig(
            workflows=["reinstall"],
            spec_file=str(spec_file),
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
            prod=True,
        )
        set_args_config(config)
        wrangler = NotebookWrangler()

        # The workflow steps should reference the spec-only preparation.
        assert wrangler._reinstall_prepare_from_spec is not None

        # Monkey-patch to capture the call within the workflow.
        called = []
        original_method = wrangler._reinstall_prepare_from_spec

        def tracking_method():
            called.append(True)
            return original_method()

        wrangler._reinstall_prepare_from_spec = tracking_method

        # Inspect the workflow registration to confirm wiring.
        # The workflow is registered via run_workflow with an explicit list;
        # we confirm the method identity used in the workflow definition.
        import inspect

        source = inspect.getsource(wrangler._run_reinstall_spec_workflow)
        assert (
            "_reinstall_prepare_from_spec" in source
        ), "Reinstall workflow must reference _reinstall_prepare_from_spec"
