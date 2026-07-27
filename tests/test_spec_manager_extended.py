"""Extended tests for nb_wrangler/spec_manager.py on load, assets, and normalization."""

import yaml
from pathlib import Path

from nb_wrangler.config import WranglerConfig, set_args_config


def _make_valid_spec_dict():
    """Create a minimal valid wrangler spec dict (in-memory)."""
    return {
        "image_spec_header": {
            "image_name": "test-image",
            "kernel_name": "test-kernel",
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


def _make_spec_manager_from_dict(tmp_path, spec_dict):
    """Create a SpecManager from an in-memory YAML dict."""
    from nb_wrangler.spec_manager import SpecManager

    set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
    sm = SpecManager()
    return sm


class TestFlattenAssetEntriesIndependence:
    def _get_flat_assets(self):
        from nb_wrangler.spec_manager import SpecManager
        return SpecManager.flatten_asset_entries

    def test_mutation_of_result_does_not_affect_input(self):
        get_flat = self._get_flat_assets()
        original = [{"repo": "r", "ref": "main", "source": "/a/", "destination": "/b/"}]
        result = get_flat(original)
        result[0]["source"] = "/mutated/"
        assert original[0]["source"] == "/a/"

    def test_shallow_copy_keys_preserved(self):
        get_flat = self._get_flat_assets()
        entry = {"repo": "r1", "ref": "v1", "source": "/x/", "destination": "/y/"}
        original = [entry]
        result = get_flat(original)
        assert len(result) == 1
        for k, v in entry.items():
            if isinstance(v, list):
                assert k in result[0]
            else:
                assert result[0][k] == v


class TestSpecManagerLoadRoundTrip:
    def test_load_and_save_preserves_keys(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True

        # Verify _spec was loaded
        assert "image_spec_header" in sm._spec
        assert sm.header["image_name"] == "test-image"

    def test_save_spec_creates_output(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()
        spec_dict = _make_valid_spec_dict()
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "src.yaml"
        spec_file.write_text(yaml_content)

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        assert sm.load_spec(spec_file) is True
        result = sm.save_spec(output_dir)
        assert result is True
        out_file = output_dir / "src.yaml"
        assert out_file.exists()


class TestInlineMambaSpecDetection:
    def test_second_document_sets_inline_mamba_spec(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()

        multi_doc = """image_name: test
python_version: "3.12"
---
name: inline-env
channels:
- conda-forge
"""
        spec_file = tmp_path / "multi.yaml"
        spec_file.write_text(multi_doc)

        assert sm.load_spec(spec_file) is True
        from nb_wrangler.config import WranglerConfig as WC
        set_args_config(WC(workflows=[], repos_dir=tmp_path / "repos"))
        assert sm.inline_mamba_spec is not None
        assert "name" in sm.inline_mamba_spec
