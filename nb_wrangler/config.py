# nb_wrangler/config.py
"""Configuration management for nb-wrangler."""

# import os
from dataclasses import dataclass
from pathlib import Path

from typing import Optional
import argparse

# from . import utils

from .constants import (
    NBW_ROOT,
    NBW_MAMBA_CMD,
    NBW_PIP_CMD,
    NOTEBOOK_TEST_MAX_SECS,
    NOTEBOOK_TEST_JOBS,
    NOTEBOOK_TEST_EXCLUDE,
    DEFAULT_LOG_TIMES_MODE,
    DEFAULT_COLOR_MODE,
    REPOS_DIR,
    DEFAULT_DATA_ENV_VARS_MODE,
)

args_config = None  # Singleton instance of WranglerConfig


def set_args_config(config: "WranglerConfig"):
    """Set the global args_config variable to a singleton."""
    assert isinstance(
        config, WranglerConfig
    ), "config should only be an instance of WranglerConfig."
    global args_config
    args_config = config


def get_args_config():
    """Return the singleton config object based on WranglerConfig.from_args()
    instantiated from a CLI / argparse object.
    """
    assert args_config is not None, "Premature fetch of global args_config variable."
    return args_config


@dataclass
class WranglerConfig:
    """Configuration class for NotebookWrangler."""

    workflows: list[str]

    spec_file: str = ""

    mamba_command: str = NBW_MAMBA_CMD
    pip_command: str = NBW_PIP_CMD

    output_dir: Path = NBW_ROOT / "temps"
    verbose: bool = False
    debug: bool = False
    log_times: str = DEFAULT_LOG_TIMES_MODE
    reset_log: bool = False
    color: str = DEFAULT_COLOR_MODE

    repos_dir: Path = Path(REPOS_DIR)
    clone_repos: bool = False
    delete_repos: bool = False
    repos_clean: Optional[list[str]] = None
    overwrite_local_changes: bool = False
    stash_local_changes: bool = False

    env_init: bool = False
    env_pack: bool = False
    env_unpack: bool = False
    env_delete: bool = False
    env_archive_delete: bool = False
    env_register: bool = False
    env_unregister: bool = False
    env_compact: bool = False
    env_archive_format: str = ""
    env_print_name: bool = False
    env_kernel_cleanup: bool = False

    packages_compile: bool = False
    packages_install: bool = False
    packages_uninstall: bool = False

    packages_omit_spi: bool = False

    test_notebooks: str | None = None
    test_notebooks_exclude: str = NOTEBOOK_TEST_EXCLUDE
    test_imports: str | None = None
    test_all: str | None = None

    jobs: int = NOTEBOOK_TEST_JOBS
    timeout: int = NOTEBOOK_TEST_MAX_SECS

    inject_spi: bool = False
    dev: bool = False
    _dev_explicitly_set: bool = False
    submit_for_build: bool = False

    spec_reset: bool = False
    spec_validate: bool = False
    spec_ignore_hash: bool = False
    spec_update_hash: bool = False
    finalize_dev_overrides: bool = False

    data_env_vars_mode: str = DEFAULT_DATA_ENV_VARS_MODE
    data_print_exports: bool = False
    data_env_vars_no_auto_add: bool = False
    data_reset_spec: bool = False
    data_collect: bool = False
    data_list: bool = False
    data_download: bool = False
    data_validate: bool = False
    data_update: bool = False
    data_unpack: bool = False
    data_pack: bool = False
    data_delete: str = ""
    data_select: str = ".*"
    data_no_validation: bool = False
    data_no_unpack_existing: bool = False
    data_no_symlinks: bool = False
    data_symlinks: bool = False

    spec_select: str | None = None
    spec_name: bool = False
    print_wrangler_repo: bool = False
    print_wrangler_ref: bool = False
    spec_list: bool = False
    spec_add: bool = False

    spi_branch: str = ""
    spi_commit_message: str = ""
    spi_inject_reqs: bool = False
    spi_build_image: bool = False
    spi_prune_docker: bool = False
    spi_push_branch: bool = False
    spi_pr: bool = False
    spi_image_name: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "WranglerConfig":
        """Create WranglerConfig from argparse Namespace and spec file."""
        global args_config
        args_config = cls(
            spec_file=args.spec_uri,
            workflows=args.workflows,
            repos_dir=args.repos_dir,
            clone_repos=args.clone_repos,
            delete_repos=args.delete_repos,
            repos_clean=args.repos_clean,
            overwrite_local_changes=args.overwrite_local_changes,
            stash_local_changes=args.stash_local_changes,
            finalize_dev_overrides=args.finalize_dev_overrides,
            env_init=args.env_init,
            env_pack=args.env_pack,
            env_unpack=args.env_unpack,
            env_delete=args.env_delete,
            env_archive_delete=args.env_archive_delete,
            env_register=args.env_register,
            env_unregister=args.env_unregister,
            env_archive_format=args.env_archive_format,
            env_compact=args.env_compact,
            env_print_name=args.env_print_name,
            env_kernel_cleanup=args.env_kernel_cleanup,
            packages_compile=args.packages_compile,
            packages_install=args.packages_install,
            packages_uninstall=args.packages_uninstall,
            packages_omit_spi=args.packages_omit_spi,
            test_notebooks=args.test_notebooks,
            test_notebooks_exclude=args.test_notebooks_exclude,
            test_imports=args.test_imports,
            test_all=args.test_all,
            jobs=args.jobs,
            timeout=args.timeout,
            inject_spi=args.inject_spi,
            dev=args.dev,
            _dev_explicitly_set=args.dev,
            spec_reset=args.spec_reset,
            spec_validate=args.spec_validate,
            spec_ignore_hash=args.spec_ignore_hash,
            spec_update_hash=args.spec_update_hash,
            data_reset_spec=args.data_reset_spec,
            data_collect=args.data_collect,
            data_list=args.data_list,
            data_download=args.data_download,
            data_validate=args.data_validate,
            data_update=args.data_update,
            data_unpack=args.data_unpack,
            data_pack=args.data_pack,
            data_delete=args.data_delete,
            data_env_vars_mode=args.data_env_vars_mode,
            data_print_exports=args.data_print_exports,
            data_env_vars_no_auto_add=args.data_env_vars_no_auto_add,
            data_select=args.data_select,
            data_no_validation=args.data_no_validation,
            data_no_unpack_existing=args.data_no_unpack_existing,
            data_no_symlinks=args.data_no_symlinks,
            data_symlinks=args.data_symlinks,
            spec_select=args.spec_select,
            spec_name=args.spec_name,
            print_wrangler_repo=args.print_wrangler_repo,
            print_wrangler_ref=args.print_wrangler_ref,
            spec_list=args.spec_list,
            spec_add=args.spec_add,
            spi_branch=args.spi_branch,
            spi_commit_message=" ".join(args.spi_commit_message),
            spi_inject_reqs=args.spi_inject_reqs,
            spi_build_image=args.spi_build_image,
            spi_prune_docker=args.spi_prune_docker,
            spi_push_branch=args.spi_push_branch,
            spi_pr=args.spi_pr,
            spi_image_name=args.spi_image_name,
            verbose=args.verbose,
            debug=args.debug,
            log_times=args.log_times,
            reset_log=args.reset_log,
            color=args.color,
        )
        return args_config


class WranglerConfigurable:
    """Mixin which reslts in self.config being defined for subclasses."""

    def __init__(self):
        # print("WranglerConfigurable")
        super().__init__()
        self.config = get_args_config()
