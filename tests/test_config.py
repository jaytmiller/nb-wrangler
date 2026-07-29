"""Tests for nb_wrangler/config.py."""

import argparse
from pathlib import Path

import pytest

from nb_wrangler.config import WranglerConfig, set_args_config, get_args_config


class TestGetArgsConfigBeforeSet:
    def test_raises_assertion_before_set(self):
        # Save the global config and reset it to None for this test
        from nb_wrangler import config as config_mod
        saved = getattr(config_mod, 'args_config', None)
        try:
            config_mod.args_config = None
            with pytest.raises(AssertionError, match="Premature fetch"):
                get_args_config()
        finally:
            config_mod.args_config = saved


class TestSetGetRoundTrip:
    def test_round_trip(self, tmp_path):
        config = WranglerConfig(
            workflows=["test"],
            spec_file="/dev/null",
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
            prod=True,
        )
        set_args_config(config)
        result = get_args_config()
        assert result is config
        assert id(result) == id(get_args_config())


class TestDefaults:
    def test_repos_dir_default(self):
        config = WranglerConfig(workflows=[])
        assert isinstance(config.repos_dir, Path)

    def test_jobs_default(self):
        config = WranglerConfig(workflows=[])
        assert isinstance(config.jobs, int)

    def test_timeout_default(self):
        config = WranglerConfig(workflows=[])
        assert isinstance(config.timeout, int)

    def test_data_env_vars_mode_default(self):
        config = WranglerConfig(workflows=[])
        assert config.data_env_vars_mode == "pantry"


class TestFromArgs:
    """Test that common argparse fields map correctly to config attributes."""

    def _make_args(self):
        return argparse.Namespace(
            spec_uri="/test/spec.yaml",
            workflows=["workflow1"],
            repos_dir="/tmp/repos",
            clone_repos=False,
            delete_repos=False,
            repos_clean=None,
            overwrite_local_changes=False,
            stash_local_changes=False,
            use_dirty_repos=False,
            finalize_dev_overrides=False,
            env_init=False,
            env_pack=False,
            env_unpack=False,
            env_delete=False,
            env_archive_delete=False,
            env_register=False,
            env_unregister=False,
            env_archive_format="",
            env_compact=False,
            packages_ignore_versions=False,
            env_print_name=False,
            env_kernel_cleanup=False,
            packages_compile=False,
            packages_install=False,
            packages_uninstall=False,
            packages_omit_spi=False,
            test_notebooks=None,
            test_notebooks_exclude="$^",
            test_imports=None,
            test_all=None,
            test_copy_shared="",
            jobs=4,
            timeout=14400,
            inject_spi=False,
            dev=False,
            prod=True,
            spec_reset=False,
            spec_validate=False,
            spec_ignore_hash=False,
            spec_update_hash=False,
            data_reset_spec=False,
            data_collect=False,
            data_list=False,
            data_download=False,
            data_validate=False,
            data_update=False,
            data_unpack=False,
            data_pack=False,
            data_delete="",
            data_env_vars_mode="pantry",
            data_print_exports=False,
            data_env_vars_no_auto_add=False,
            data_select=".*",
            data_no_validation=False,
            data_no_unpack_existing=False,
            data_no_symlinks=False,
            data_symlinks=False,
            spec_select=None,
            spec_name=False,
            print_wrangler_repo=False,
            print_wrangler_ref=False,
            print_repo_tags=False,
            spec_list=False,
            spec_add=False,
            spi_branch="",
            spi_commit_message=[""],
            spi_inject_reqs=False,
            spi_build_image=False,
            spi_prune_docker=False,
            spi_push_branch=False,
            spi_pr=False,
            spi_image_name=False,
            docker_pull=None,
            docker_cat=None,
            docker_list=None,
            verbose=False,
            quiet=False,
            debug=False,
            log_times="elapsed",
            reset_log=False,
            color="auto",
        )

    def test_spec_file_is_stored(self):
        args = self._make_args()
        result = WranglerConfig.from_args(args)
        assert result.spec_file == "/test/spec.yaml"
        assert result.workflows == ["workflow1"]
        assert result.repos_dir == "/tmp/repos"
        assert result.prod is True

    def test_jobs_and_timeout_map(self):
        args = self._make_args()
        result = WranglerConfig.from_args(args)
        assert result.jobs == 4
        assert result.timeout == 14400

    def test_data_env_vars_mode_maps(self):
        args = self._make_args()
        result = WranglerConfig.from_args(args)
        assert result.data_env_vars_mode == "pantry"

    def test_dev_flag_is_set(self):
        args = self._make_args()
        args.dev = True
        result = WranglerConfig.from_args(args)
        assert result.prod is True
