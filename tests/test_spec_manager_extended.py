"""Extended tests for nb_wrangler/spec_manager.py on load, assets, and normalization."""

from pathlib import Path

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
    """Tests that consolidate_environment returns non_mamba_pip_package_files as a list of
    dicts mapping file paths to expanded (sorted) package lists.

    After the no-notebook requirements.txt gathering refactor, pip requirement files are
    discovered through configured notebook selections (selected_notebooks -> repo -> on-disk
    cloned repo dir), not directly from the consolidate_environment `notebook_paths` arg. So
    these tests lay out a real selection whose repo directory lives under config.repos_dir and
    contains an actual requirements.txt, mirroring how production curations compile pip packages.
    """

    REPO_URL = "https://github.com/test-org/notebook_repo.git"
    # RepositoryManager clones to repos_dir/<basename-of-url>.git-stripped.
    REPO_DIR_NAME = "notebook_repo"

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
        # Configure a single repository and selection so get_requirements_files() has an
        # on-disk repo directory to glob under config.repos_dir/<REPO_DIR_NAME>.
        spec_dict["repositories"] = {
            "notebook_repo": {"url": self.REPO_URL},
        }
        spec_dict["selected_notebooks"] = {
            "sel_all": {
                "repo": "notebook_repo",
                "root_directory": ".",
                "include_subdirs": ["\\."],
            },
        }
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        # RepositoryManager would normally clone into this directory; for unit testing we only
        # need the on-disk path to exist so SpecManager's get_requirements_files() can glob it.
        repo_dir = tmp_path / "repos" / self.REPO_DIR_NAME
        repo_dir.mkdir(parents=True, exist_ok=True)

        sm = SpecManager()
        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        repo_manager = RepositoryManager(tmp_path / "repos")
        compiler = RequirementsCompiler(sm, repo_manager)
        return compiler

    def _output_dir(self, tmp_path):
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def test_pip_files_returned_as_list_of_dicts_with_packages(self, tmp_path):
        """consolidate_environment returns list[dict[path, [packages]]] for pip files."""
        compiler = self._make_compiler(tmp_path)
        self._output_dir(tmp_path)

        # Requirements are discovered via the configured selection -> repo dir on disk.
        repo_dir = tmp_path / "repos" / self.REPO_DIR_NAME
        req_file1 = repo_dir / "requirements.txt"
        _make_requirements_file(req_file1, ["numpy", "astropy"])

        pip_files = compiler.consolidate_packages(
            _FakeInjector(), self._output_dir(tmp_path)
        )
        #  is list[dict[selector_name, list[package_files]]]

        assert isinstance(pip_files, list)
        file_key = str(req_file1)
        for pkgd in pip_files:
            if file_key in pkgd:
                # _read_package_lines returns a sorted list of non-comment lines.
                assert pkgd[file_key] == ["astropy", "numpy"]
                break
        else:
            assert False, f"Bad package files output; expected {file_key}."

    def _make_compiler_with_pip_packages(self, tmp_path, extra=None, common=None):
        """Build a compiler whose spec declares configured extra/common pip packages."""
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
        spec_dict["repositories"] = {
            "notebook_repo": {"url": self.REPO_URL},
        }
        spec_dict["selected_notebooks"] = {
            "sel_all": {
                "repo": "notebook_repo",
                "root_directory": ".",
                "include_subdirs": ["\\."],
            },
        }
        spec_dict["extra_pip_packages"] = list(extra or [])
        spec_dict["common_pip_packages"] = list(common or [])
        spec_file = tmp_path / "spec_with_pip.yaml"
        spec_file.write_text(yaml.dump(spec_dict, default_flow_style=False))

        # Mirror the on-disk repo directory RepositoryManager would clone into.
        (tmp_path / "repos" / self.REPO_DIR_NAME).mkdir(parents=True, exist_ok=True)
        sm = SpecManager()
        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        repo_manager = RepositoryManager(tmp_path / "repos")
        return RequirementsCompiler(sm, repo_manager)

    def test_pip_files_include_extra_and_common_packages(self, tmp_path):
        """Non-empty extra/common pip packages appear as separate entries."""
        compiler = self._make_compiler_with_pip_packages(
            tmp_path, extra=["requests>=2.31,<3", "packaging"], common=["six"]
        )
        output_dir = self._output_dir(tmp_path)

        contributions = compiler.consolidate_packages(_FakeInjector(), output_dir)
        all_requirements = compiler.spec_manager.flatten_req_files(contributions)

        extra_key = str(output_dir / "extra_pip_packages.txt")
        common_key = str(output_dir / "common_pip_packages.txt")
        assert extra_key in iter(all_requirements.keys())
        assert common_key in iter(all_requirements.keys())

        # Validate package contents. _read_package_lines preserves version specs
        # (it only drops blank/comment lines) and returns a sorted list, so verify the
        # raw lines round-trip in sorted order rather than version-stripped names.

        for req_file in all_requirements:
            if req_file == extra_key:
                assert all_requirements[extra_key] == ["packaging", "requests>=2.31,<3"]
            elif req_file == common_key:
                assert all_requirements[common_key] == ["six"]


class _FakeInjector:
    """Minimal injector stub returning no SPI files."""

    def find_spi_mamba_files(self):
        return []

    def find_spi_pip_files(self):
        return []


class TestFlattenReqDataAndMultiSelection:
    """Regression tests for flatten_req_data and multi-selection requirements gathering.

    These cover the bug where ``flatten_req_data`` returned a leftover loop variable
    (``file_list``) instead of the accumulated ``combined_files``, causing requirements.txt
    files contributed by earlier notebook selections to be silently dropped — which is why
    nb-wrangler failed to discover req files in package-only directories (no notebooks).
    """

    def _get_sm(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(
            WranglerConfig(
                workflows=[], repos_dir=tmp_path / "repos", output_dir=tmp_path / "out"
            )
        )
        return SpecManager()

    def test_flatten_req_data_returns_all_files_across_selections(self, tmp_path):
        sm = self._get_sm(tmp_path)
        sample = [
            {"notebooks": ["/a/notebooks/sub/requirements.txt"]},
            {"activities": ["/b/activities/x/r1.txt", "/b/activities/y/r2.txt"]},
        ]
        result = sm.flatten_req_data(sample)
        assert sorted(result) == [
            "/a/notebooks/sub/requirements.txt",
            "/b/activities/x/r1.txt",
            "/b/activities/y/r2.txt",
        ]

    def test_flatten_req_data_empty_input_does_not_raise(self, tmp_path):
        sm = self._get_sm(tmp_path)
        assert sm.flatten_req_data([]) == []

    def test_get_requirements_files_discovers_orphan_dir_only_reqs(self, tmp_path):
        """End-to-end: a requirements.txt in a directory with NO notebook files must still be found when it appears under two selections.
        Reproduces the RST_commissioning scenario where `notebooks/.*` and `activities/.*` overlap package-only dirs.
        """
        from nb_wrangler.spec_manager import SpecManager

        set_args_config(
            WranglerConfig(
                workflows=[], repos_dir=tmp_path / "repos", output_dir=tmp_path / "out"
            )
        )
        repo_url = "https://github.com/test-org/RST_commissioning.git"
        spec_dict = _make_valid_spec_dict()
        spec_dict["repositories"] = {"repo_a": {"url": repo_url}}
        # Two selections spanning overlapping package-only dirs (no notebooks in the orphan dir).
        spec_dict["selected_notebooks"] = {
            "notebooks_sel": {
                "repo": "repo_a",
                "root_directory": ".",
                "include_subdirs": [r"notebooks/.*"],
            },
            "activities_sel": {
                "repo": "repo_a",
                "root_directory": ".",
                "include_subdirs": [r"activities/.*"],
            },
        }
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        repo_dir = tmp_path / "repos" / "RST_commissioning"
        (repo_dir / "activities/car-138/CAR138_goals5and6").mkdir(parents=True)
        # requirements.txt in a directory with NO notebook sibling under this exact path.
        req_file = repo_dir / "activities/car-138/CAR138_goals5and6/requirements.txt"
        _make_requirements_file(req_file, ["numpy", "astropy"])

        sm = SpecManager()
        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        req_data = sm.get_requirements_files()
        flat = sm.flatten_req_data(req_data)
        # The orphan (notebook-less) requirements file must be present exactly once.
        assert str(req_file) in flat, f"Orphan requirements.txt missing: {flat}"


class TestStripVersionsFromRequirements:
    """Tests for _strip_versions_from_requirements which strips version constraints
    from requirements files and writes them to flat temporary files in output_dir.

    Regression: the stripped filename previously embedded the full path of the original
    requirements file (e.g. stripped_/home/.../aperture_photometry/requirements.txt_abc123.txt).
    Because the path separators were interpreted as directory separators, the output file
    was never actually created at the expected flat location, causing a downstream
    FileNotFoundError during pip compilation.
    """

    REPO_URL = "https://github.com/test-org/notebook_repo.git"
    REPO_DIR_NAME = "notebook_repo"

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
        spec_dict["repositories"] = {
            "notebook_repo": {"url": self.REPO_URL},
        }
        spec_dict["selected_notebooks"] = {
            "sel_all": {
                "repo": "notebook_repo",
                "root_directory": ".",
                "include_subdirs": ["\\."],
            },
        }
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml.dump(spec_dict, default_flow_style=False))

        repo_dir = tmp_path / "repos" / self.REPO_DIR_NAME
        repo_dir.mkdir(parents=True, exist_ok=True)

        sm = SpecManager()
        assert sm.load_spec(spec_file) is True
        assert sm.validate() is True
        repo_manager = RepositoryManager(tmp_path / "repos")
        compiler = RequirementsCompiler(sm, repo_manager)
        return compiler

    def test_stripped_file_uses_basename_only(self, tmp_path):
        """The output stripped filename must contain only the basename of the
        original requirements file, not its full path."""
        compiler = self._make_compiler(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create a requirements file in a deeply nested directory.
        repo_dir = tmp_path / "repos" / self.REPO_DIR_NAME
        req_file = repo_dir / "notebooks" / "aperture_photometry" / "requirements.txt"
        req_file.parent.mkdir(parents=True, exist_ok=True)
        _make_requirements_file(req_file, ["numpy>=1.20", "astropy==5.3"])

        req_data = compiler.spec_manager.get_requirements_files()
        stripped_files = compiler._strip_versions_from_requirements(
            req_data, output_dir
        )

        assert len(stripped_files) == 1
        stripped_path = stripped_files[0]

        # The stripped file must live directly in output_dir, not in a nested
        # directory that mirrors the original path.
        assert Path(stripped_path).parent == output_dir

        # The filename should contain "requirements.txt" (the basename), not
        # any path separators from the original location.
        filename = Path(stripped_path).name
        assert "requirements.txt" in filename
        assert "/" not in filename

        # The stripped file should exist and contain version-less package names.
        assert Path(stripped_path).exists()
        content = Path(stripped_path).read_text().strip().splitlines()
        assert "numpy" in content
        assert "astropy" in content
        assert all("=" not in pkg for pkg in content)

    def test_stripped_file_for_duplicate_basenames_does_not_collide(self, tmp_path):
        """Two requirements files with the same basename in different directories
        must both produce distinct stripped files (disambiguated by the sha hash)."""
        compiler = self._make_compiler(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        repo_dir = tmp_path / "repos" / self.REPO_DIR_NAME
        req1 = repo_dir / "notebooks" / "aperture_photometry" / "requirements.txt"
        req2 = repo_dir / "notebooks" / "image_processing" / "requirements.txt"
        for req in [req1, req2]:
            req.parent.mkdir(parents=True, exist_ok=True)
            _make_requirements_file(req, ["numpy>=1.20"])

        req_data = compiler.spec_manager.get_requirements_files()
        stripped_files = compiler._strip_versions_from_requirements(
            req_data, output_dir
        )

        assert len(stripped_files) == 2
        # Both should be in the flat output_dir.
        for sf in stripped_files:
            assert Path(sf).parent == output_dir
        # They should be distinct files.
        assert len(set(stripped_files)) == 2
