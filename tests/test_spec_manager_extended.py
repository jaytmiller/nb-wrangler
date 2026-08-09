"""Extended tests for nb_wrangler/spec_manager.py on load, assets, and normalization."""

import yaml

from nb_wrangler.config import WranglerConfig, set_args_config


def _make_requirements_file(path, packages):
    """Write a requirements file with the given package lines."""
    path.write_text("\n".join(packages) + "\n")


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


class TestEnvironmentVarsField:
    def test_environment_vars_in_allowed_keywords(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        spec_dict["environment_vars"] = {"FOO": "bar", "BAZ": "${HOME}/x"}
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        assert sm.environment_vars == {"FOO": "bar", "BAZ": "${HOME}/x"}

    def test_environment_vars_default_empty(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        assert sm.environment_vars == {}

    def test_environment_vars_property_no_env_field(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        result = sm.environment_vars
        assert isinstance(result, dict)

    def test_environment_vars_dev_override_merges(self, tmp_path):
        from nb_wrangler.config import WranglerConfig
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(
            WranglerConfig(workflows=[], repos_dir=tmp_path / "repos", dev=True)
        )
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        spec_dict["environment_vars"] = {"FOO": "base_value", "KEEP": "unchanged"}
        spec_dict["dev_overrides"] = {
            "environment_vars": {"FOO": "dev_value", "NEW": "new_var"}
        }
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        env_vars = sm.environment_vars
        assert env_vars["FOO"] == "dev_value"
        assert env_vars["KEEP"] == "unchanged"
        assert env_vars["NEW"] == "new_var"

    def test_environment_vars_no_dev_when_dev_disabled(self, tmp_path):
        from nb_wrangler.config import WranglerConfig
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(
            WranglerConfig(workflows=[], repos_dir=tmp_path / "repos", dev=False)
        )
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        spec_dict["environment_vars"] = {"FOO": "base_value"}
        spec_dict["dev_overrides"] = {"environment_vars": {"FOO": "dev_value"}}
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        env_vars = sm.environment_vars
        assert env_vars["FOO"] == "base_value"


class TestPackageListDevOverrides:
    """Verify the five package-list properties honor dev_overrides as full replacements."""

    _PROPS = (
        "extra_mamba_packages",
        "common_mamba_packages",
        "extra_pip_packages",
        "common_pip_packages",
        "apt_packages",
    )

    def test_override_replaces_base_in_dev_mode(self, tmp_path):
        # base [a] + dev_override [b] -> property yields [b]; base dropped.
        for prop in self._PROPS:
            sm = self._build_sm(
                tmp_path,
                spec_overrides={prop: ["base_pkg"]},
                dev=True,
                dev_overrides={prop: ["dev_pkg"]},
            )
            result = getattr(sm, prop)
            assert result == ["dev_pkg"], f"{prop}: expected override-only list"

    def test_no_override_resolves_to_base(self, tmp_path):
        # Without a same-named dev override the base value is returned verbatim.
        for prop in self._PROPS:
            sm = self._build_sm(
                tmp_path,
                spec_overrides={prop: ["base_pkg"]},
                dev=True,
                dev_overrides={"environment_vars": {"FOO": "bar"}},
            )
            result = getattr(sm, prop)
            assert result == ["base_pkg"], f"{prop}: expected base list"

    def test_prod_mode_ignores_override(self, tmp_path):
        # In prod mode the override is never consulted, even when present.
        for prop in self._PROPS:
            sm = self._build_sm(
                tmp_path,
                spec_overrides={prop: ["base_pkg"]},
                dev=False,
                dev_overrides={prop: ["dev_pkg"]},
            )
            result = getattr(sm, prop)
            assert result == ["base_pkg"], f"{prop}: prod must use base list"

    def test_override_empty_list_replaces_base(self, tmp_path):
        # A full override semantics means an empty dev list clears the base.
        for prop in self._PROPS:
            sm = self._build_sm(
                tmp_path,
                spec_overrides={prop: ["base_pkg"]},
                dev=True,
                dev_overrides={prop: []},
            )
            result = getattr(sm, prop)
            assert result == [], f"{prop}: empty override should clear base"

    def _build_sm(self, tmp_path, spec_overrides=None, dev=False, dev_overrides=None):
        spec_dict = _make_valid_spec_dict()
        if spec_overrides:
            for k, v in spec_overrides.items():
                # Ensure the key sits at top level where properties read it.
                spec_dict[k] = v
        if dev_overrides is not None:
            spec_dict["dev_overrides"] = dev_overrides

        from nb_wrangler.spec_manager import SpecManager

        set_args_config(
            WranglerConfig(workflows=[], repos_dir=tmp_path / "repos", dev=dev)
        )
        sm = SpecManager()

        spec_file = tmp_path / f"spec-{id(spec_dict)}.yaml"
        spec_file.write_text(yaml.dump(spec_dict, default_flow_style=False))
        assert sm.load_spec(spec_file) is True
        return sm


class TestTestEnvVarsField:
    def test_test_env_vars_in_allowed_keywords(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        spec_dict["test_environment_vars"] = {
            "TEST_API_KEY": "mock_secret",
            "CRDS_PATH": "${HOME}/crds_mock/",
        }
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        assert sm.test_env_vars == {
            "TEST_API_KEY": "mock_secret",
            "CRDS_PATH": "${HOME}/crds_mock/",
        }

    def test_test_env_vars_default_empty(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        assert sm.test_env_vars == {}

    def test_test_env_vars_property_no_field(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        result = sm.test_env_vars
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_test_env_vars_dev_override_merges(self, tmp_path):
        from nb_wrangler.config import WranglerConfig
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(
            WranglerConfig(workflows=[], repos_dir=tmp_path / "repos", dev=True)
        )
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        spec_dict["test_environment_vars"] = {"FOO": "base_value", "KEEP": "unchanged"}
        spec_dict["dev_overrides"] = {
            "test_environment_vars": {"FOO": "dev_value", "NEW": "new_var"}
        }
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        env_vars = sm.test_env_vars
        assert env_vars["FOO"] == "dev_value"
        assert env_vars["KEEP"] == "unchanged"
        assert env_vars["NEW"] == "new_var"

    def test_test_env_vars_no_dev_when_prod_mode(self, tmp_path):
        from nb_wrangler.config import WranglerConfig
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(
            WranglerConfig(workflows=[], repos_dir=tmp_path / "repos", dev=False)
        )
        sm = SpecManager()

        spec_dict = _make_valid_spec_dict()
        spec_dict["test_environment_vars"] = {"FOO": "base_value"}
        spec_dict["dev_overrides"] = {"test_environment_vars": {"FOO": "dev_value"}}
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        env_vars = sm.test_env_vars
        assert env_vars["FOO"] == "base_value"


class TestConsolidateEnvironmentPipFiles:
    """Tests that consolidate_environment returns non_mamba_pip_package_files as a dict
    mapping file paths to expanded package lists."""

    def _make_compiler(self, tmp_path):
        from nb_wrangler.config import WranglerConfig
        from nb_wrangler.spec_manager import SpecManager
        from nb_wrangler.repository import RepositoryManager
        from nb_wrangler.compiler import RequirementsCompiler

        set_args_config(
            WranglerConfig(
                workflows=[],
                repos_dir=tmp_path / "repos",
                output_dir=tmp_path / "output",
            )
        )
        spec_dict = _make_valid_spec_dict()
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        sm = SpecManager()
        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        repo_manager = RepositoryManager(tmp_path / "repos")
        compiler = RequirementsCompiler(sm, repo_manager)
        return compiler

    def test_pip_files_returned_as_dict_with_packages(self, tmp_path):
        """consolidate_environment returns dict[str, list[str]] for pip files."""
        compiler = self._make_compiler(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        req_file1 = output_dir / "requirements.txt"
        _make_requirements_file(req_file1, ["numpy", "astropy"])

        result = compiler.consolidate_environment(
            [str(req_file1)], _FakeInjector(), output_dir
        )
        # result is (kernel_name, mamba_spec, pkg_map, pip_dict)
        _, _, _, pip_files = result

        assert isinstance(pip_files, dict)
        file_key = str(req_file1)
        assert file_key in pip_files
        assert sorted(pip_files[file_key]) == ["astropy", "numpy"]

    def test_pip_files_include_extra_and_common_packages(self, tmp_path):
        """Extra and common pip packages appear as separate entries with their packages."""
        compiler = self._make_compiler(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Put extra_pip_packages in the spec manager via config dev_overrides-like approach
        result = compiler.consolidate_environment([], _FakeInjector(), output_dir)
        _, _, _, pip_files = result

        assert isinstance(pip_files, dict)
        extra_key = str(output_dir / "extra_pip_packages.txt")
        common_key = str(output_dir / "common_pip_packages.txt")
        assert extra_key in pip_files
        assert common_key in pip_files
        # The packages should be sorted lists (from _read_package_lines).


class _FakeInjector:
    """Minimal injector stub returning no SPI files."""

    def find_spi_mamba_files(self):
        return []

    def find_spi_pip_files(self):
        return []
