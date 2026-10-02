"""Tests for the consolidated environment-name utility functions in spec_manager.

These tests verify that ``kernel_name_to_env_name`` and ``is_base_env_name``
are the single source of truth for the python3↔base convention, and that
all callers (SpecManager, WranglerWorkflowMixin, EnvironmentManager) route
through them.
"""

from nb_wrangler.spec_manager import (
    kernel_name_to_env_name,
    is_base_env_name,
)


class TestKernelNameToEnvName:
    """kernel_name_to_env_name is the canonical python3→base mapper."""

    def test_python3_maps_to_base(self):
        assert kernel_name_to_env_name("python3") == "base"

    def test_base_stays_base(self):
        assert kernel_name_to_env_name("base") == "base"

    def test_custom_kernel_passes_through(self):
        assert kernel_name_to_env_name("RomanNexus-2026.2") == "RomanNexus-2026.2"

    def test_none_passes_through(self):
        assert kernel_name_to_env_name(None) is None

    def test_empty_string_passes_through(self):
        assert kernel_name_to_env_name("") == ""


class TestIsBaseEnvName:
    """is_base_env_name is the canonical base-alias checker."""

    def test_base_is_alias(self):
        assert is_base_env_name("base") is True

    def test_python3_is_alias(self):
        assert is_base_env_name("python3") is True

    def test_custom_env_not_alias(self):
        assert is_base_env_name("RomanNexus-2026.2") is False

    def test_none_not_alias(self):
        assert is_base_env_name(None) is False

    def test_empty_string_not_alias(self):
        assert is_base_env_name("") is False


class TestSpecManagerUsesCanonicalMapper:
    """SpecManager.environment_name and get_resolved_environment_name
    both route through kernel_name_to_env_name."""

    def test_environment_name_uses_mapper(self, tmp_path):
        import yaml
        from nb_wrangler.spec_manager import SpecManager
        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()
        spec_dict = {
            "image_spec_header": {
                "image_name": "test-image",
                "kernel_name": "python3",
                "deployment_name": "wrangler",
                "python_version": "3.12",
                "valid_on": "2026-01-01",
                "expires_on": "2027-01-01",
            },
            "repositories": {},
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "https://example.com"},
                "nb-wrangler": {"repo": "https://example.com"},
                "date_updated": "2026-01-01T00:00:00",
            },
        }
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml.dump(spec_dict))
        sm.load_spec(spec_file)

        assert sm.environment_name == kernel_name_to_env_name("python3")
        assert sm.get_resolved_environment_name() == kernel_name_to_env_name(
            sm.get_resolved_kernel_name()
        )


class TestWranglerMixinUsesCanonicalMapper:
    """WranglerWorkflowMixin.resolved_environment_name routes through
    kernel_name_to_env_name."""

    def test_mixin_uses_mapper(self, tmp_path):
        import yaml
        from nb_wrangler.spec_manager import SpecManager
        from nb_wrangler.wrangler import NotebookWrangler
        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()
        spec_dict = {
            "image_spec_header": {
                "image_name": "test-image",
                "kernel_name": "python3",
                "deployment_name": "wrangler",
                "python_version": "3.12",
                "valid_on": "2026-01-01",
                "expires_on": "2027-01-01",
            },
            "repositories": {},
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "https://example.com"},
                "nb-wrangler": {"repo": "https://example.com"},
                "date_updated": "2026-01-01T00:00:00",
            },
        }
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml.dump(spec_dict))
        sm.load_spec(spec_file)

        wrangler = NotebookWrangler.__new__(NotebookWrangler)
        wrangler.spec_manager = sm
        wrangler.config = sm.config
        wrangler.compiled_kernel_name = None

        # resolved_kname is the raw kernel name (python3)
        assert wrangler.resolved_kname == "python3"
        # resolved_environment_name applies the canonical mapper
        assert wrangler.resolved_environment_name == kernel_name_to_env_name(
            wrangler.resolved_kname
        )
