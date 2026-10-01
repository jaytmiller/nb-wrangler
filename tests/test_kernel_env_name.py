"""Tests for kernel_name / environment_name separation in SpecManager and wranglers.

These tests verify:
- python3 kernel → base environment mapping
- resolved_kname returns kernel name (not env name)
- resolved_environment_name returns env name (with python3→base mapping)
- exact matching in environment_exists (no suffix matching)
- case-insensitive kernelspec lookup with preserved case
"""

import json
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import yaml

from nb_wrangler.config import WranglerConfig, set_args_config


def _make_valid_spec_dict(kernel_name="python3"):
    """Create a minimal valid wrangler spec dict."""
    return {
        "image_spec_header": {
            "image_name": "test-image",
            "kernel_name": kernel_name,
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
    }


def _make_spec_manager_from_spec(tmp_path, spec_dict):
    """Create a SpecManager from an in-memory YAML dict."""
    from nb_wrangler.spec_manager import SpecManager

    set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
    sm = SpecManager()
    yaml_content = yaml.dump(spec_dict, default_flow_style=False)
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(yaml_content)
    assert sm.load_spec(spec_file) is True
    return sm


class TestEnvironmentNameProperty:
    """Tests for SpecManager.environment_name (the python3→base mapping)."""

    def test_kernel_name_python3(self, tmp_path):
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="python3")
        )
        assert sm.kernel_name == "python3"

    def test_environment_name_python3_maps_to_base(self, tmp_path):
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="python3")
        )
        assert sm.environment_name == "base"

    def test_environment_name_custom_kernel(self, tmp_path):
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="RomanNexus-2026.2")
        )
        assert sm.environment_name == "RomanNexus-2026.2"


class TestGetResolvedNames:
    """Tests for SpecManager.get_resolved_kernel_name and get_resolved_environment_name."""

    def test_resolved_kernel_name_from_header(self, tmp_path):
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="mykernel")
        )
        assert sm.get_resolved_kernel_name() == "mykernel"

    def test_resolved_environment_name_python3(self, tmp_path):
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="python3")
        )
        assert sm.get_resolved_kernel_name() == "python3"
        assert sm.get_resolved_environment_name() == "base"

    def test_resolved_environment_name_custom(self, tmp_path):
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="RomanNexus-2026.2")
        )
        assert sm.get_resolved_kernel_name() == "RomanNexus-2026.2"
        assert sm.get_resolved_environment_name() == "RomanNexus-2026.2"


class TestNotebookWranglerEnvNameSeparation:
    """Tests for NotebookWrangler environment_name / resolved_kname / resolved_environment_name."""

    def test_python3_kernel(self, tmp_path):
        """For python3 kernel: resolved_kname='python3', resolved_environment_name='base'."""
        from nb_wrangler.wrangler import NotebookWrangler

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="python3")
        )
        wrangler = NotebookWrangler.__new__(NotebookWrangler)
        wrangler.spec_manager = sm
        wrangler.config = sm.config
        wrangler.compiled_kernel_name = None

        assert wrangler.resolved_kname == "python3"
        assert wrangler.resolved_environment_name == "base"

    def test_custom_kernel(self, tmp_path):
        """For a custom kernel, resolved_kname == resolved_environment_name."""
        from nb_wrangler.wrangler import NotebookWrangler

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="mykernel")
        )
        wrangler = NotebookWrangler.__new__(NotebookWrangler)
        wrangler.spec_manager = sm
        wrangler.config = sm.config
        wrangler.compiled_kernel_name = None

        assert wrangler.resolved_kname == "mykernel"
        assert wrangler.resolved_environment_name == "mykernel"

    def test_env_name_deprecated_but_works(self, tmp_path):
        """env_name still works but emits a DeprecationWarning."""
        from nb_wrangler.wrangler import NotebookWrangler

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="python3")
        )
        wrangler = NotebookWrangler.__new__(NotebookWrangler)
        wrangler.spec_manager = sm
        wrangler.config = sm.config
        wrangler.compiled_kernel_name = None

        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = wrangler.env_name
            assert result == "base"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)


class TestDataWranglerResolvedKname:
    """Tests that DataWrangler.resolved_kname uses SpecManager.get_resolved_kernel_name."""

    def test_data_wrangler_resolved_kname_from_spec(self, tmp_path):
        from nb_wrangler.data_wrangler import DataWrangler
        from nb_wrangler.repository import RepositoryManager
        from nb_wrangler.pantry import NbwPantry
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = _make_spec_manager_from_spec(
            tmp_path, _make_valid_spec_dict(kernel_name="mykernel")
        )
        pantry = NbwPantry()
        repo_manager = RepositoryManager(tmp_path / "repos")
        env_manager = EnvironmentManager()
        dw = DataWrangler(sm, pantry, repo_manager, env_manager)

        assert dw.resolved_kname == "mykernel"


class TestEnvironmentExistsExactMatch:
    """Tests that environment_exists uses exact matching (no suffix matching)."""

    def _make_manager(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = EnvironmentManager()
        em.logger = MagicMock()
        return em

    def test_base_env_exists(self, tmp_path):
        em = self._make_manager(tmp_path)
        assert em.environment_exists("base") is True

    def test_python3_env_exists(self, tmp_path):
        em = self._make_manager(tmp_path)
        assert em.environment_exists("python3") is True

    def test_exact_match_found(self, tmp_path):
        """An env whose name exactly matches should be found."""
        em = self._make_manager(tmp_path)
        # get_existing_envs returns full paths; environment_exists takes the name
        em.get_existing_envs = MagicMock(
            return_value=["/path/to/nbw_mm/envs/roman-nexus"]
        )
        assert em.environment_exists("roman-nexus") is True

    def test_suffix_no_longer_matches(self, tmp_path):
        """A suffix-only match should NOT be found with exact matching.

        Previously, 'nexus' would match env '/path/to/nbw_mm/envs/romannexus'
        via endswith. With exact matching, this must return False.
        """
        em = self._make_manager(tmp_path)
        em.get_existing_envs = MagicMock(
            return_value=["/path/to/nbw_mm/envs/romannexus"]
        )
        assert em.environment_exists("nexus") is False

    def test_case_sensitive_exact_match(self, tmp_path):
        """Env names are case-sensitive."""
        em = self._make_manager(tmp_path)
        em.get_existing_envs = MagicMock(
            return_value=["/path/to/nbw_mm/envs/RomanNexus-2026.2"]
        )
        assert em.environment_exists("RomanNexus-2026.2") is True
        assert em.environment_exists("romannexus-2026.2") is False


class TestLookupJupyterKernelName:
    """Tests for EnvironmentManager._lookup_jupyter_kernel_name."""

    def _make_manager(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = EnvironmentManager()
        em.logger = MagicMock()
        return em

    def test_exact_case_lookup(self, tmp_path):
        """When the kernel name is exact-case registered, return it as-is."""
        em = self._make_manager(tmp_path)
        listing = json.dumps({"kernelspecs": {"RomanNexus-2026.2": {}}})
        em.wrangler_run = MagicMock(
            return_value=CompletedProcess(["jupyter"], 0, stdout=listing)
        )
        assert (
            em._lookup_jupyter_kernel_name("RomanNexus-2026.2") == "RomanNexus-2026.2"
        )

    def test_case_insensitive_lookup_preserves_registered_case(self, tmp_path):
        """When searching with different case, return the registered case."""
        em = self._make_manager(tmp_path)
        listing = json.dumps({"kernelspecs": {"RomanNexus-2026.2": {}}})
        em.wrangler_run = MagicMock(
            return_value=CompletedProcess(["jupyter"], 0, stdout=listing)
        )
        # Search with lowercase, should return the registered case
        assert (
            em._lookup_jupyter_kernel_name("romannexus-2026.2") == "RomanNexus-2026.2"
        )

    def test_no_match_returns_input(self, tmp_path):
        """When no match is found, return the input name as fallback."""
        em = self._make_manager(tmp_path)
        listing = json.dumps({"kernelspecs": {"other-env": {}}})
        em.wrangler_run = MagicMock(
            return_value=CompletedProcess(["jupyter"], 0, stdout=listing)
        )
        assert em._lookup_jupyter_kernel_name("MyEnv") == "MyEnv"
