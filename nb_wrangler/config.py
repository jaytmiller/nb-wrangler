# nb_wrangler/config.py
"""Configuration management for nb-wrangler."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import argparse

from . import utils
from .constants import (
    NBW_ROOT,
    DEFAULT_MAMBA_COMMAND,
    DEFAULT_PIP_COMMAND,
    NOTEBOOK_TEST_MAX_SECS,
    NOTEBOOK_TEST_JOBS,
    DEFAULT_LOG_TIMES_MODE,
    DEFAULT_COLOR_MODE,
    REPOS_DIR,
    DATA_DIR,
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

    spec_file: str = ""

    mamba_command: Path = DEFAULT_MAMBA_COMMAND
    pip_command: Path = DEFAULT_PIP_COMMAND
    output_dir: Path = NBW_ROOT / "temps"
    verbose: bool = False
    debug: bool = False
    log_times: str = DEFAULT_LOG_TIMES_MODE
    color: str = DEFAULT_COLOR_MODE

    repos_dir: Path = Path(REPOS_DIR)
    data_dir: Path(DATA_DIR)
    clone_repos: bool = False
    delete_repos: bool = False

    init_env: bool = False
    pack_env: bool = False
    unpack_env: bool = False
    delete_env: bool = False
    register_env: bool = False
    unregister_env: bool = False
    compact: bool = False
    archive_format: str = ""

    compile_packages: bool = False
    install_packages: bool = False
    uninstall_packages: bool = False

    test_notebooks: str | None = None
    test_imports: bool = False
    test_all: bool = False

    jobs: int = NOTEBOOK_TEST_JOBS
    timeout: int = NOTEBOOK_TEST_MAX_SECS

    omit_spi_packages: bool = False
    inject_spi: bool = False
    submit_for_build: bool = False

    reset_spec: bool = False
    validate_spec: bool = False
    ignore_spec_hash: bool = False
    add_pip_hashes: bool = False
    update_spec_hash: bool = False

    env_overrides: str = ""
    pantry_add_spec: bool = False
    data_collect: bool = False
    data_download: bool = False
    data_validate: bool = False
    data_update: bool = False
    data_unpack_pantry: bool = False
    data_pack_pantry: bool = False
    data_dir: str = DATA_DIR

    workflow: str = "explicit"

    def __post_init__(self):
        """Post-initialization processing."""
        if self.test_all:
            self.test_imports = True
            self.test_notebooks = ".*"

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "WranglerConfig":
        """Create WranglerConfig from argparse Namespace and spec file."""
        global args_config
        args_config = cls(
            spec_file=args.spec_uri,
            # mamba_command=args.mamba_command,   # controlled via env var only
            # pip_command=args.pip_command,   # controlled via env var only
            verbose=args.verbose,
            debug=args.debug,
            log_times=args.log_times,
            color=args.color,
            repos_dir=args.repos_dir,
            clone_repos=args.clone_repos,
            delete_repos=args.delete_repos,
            init_env=args.init_env,
            pack_env=args.pack_env,
            unpack_env=args.unpack_env,
            delete_env=args.delete_env,
            register_env=args.register_env,
            unregister_env=args.unregister_env,
            archive_format=args.archive_format,
            compile_packages=args.compile_packages,
            install_packages=args.install_packages,
            uninstall_packages=args.uninstall_packages,
            compact=args.compact,
            test_notebooks=args.test_notebooks,
            test_imports=args.test_imports,
            test_all=args.test_all,
            jobs=args.jobs,
            timeout=args.timeout,
            omit_spi_packages=args.omit_spi_packages,
            inject_spi=args.inject_spi,
            reset_spec=args.reset_spec,
            validate_spec=args.validate_spec,
            ignore_spec_hash=args.ignore_spec_hash,
            add_pip_hashes=args.add_pip_hashes,
            update_spec_hash=args.update_spec_hash,
            workflow=args.workflow,
            env_overrides=args.env_overrides,
            pantry_add_spec=args.pantry_add_spec,
            data_collect=args.data_collect,
            data_download=args.data_download,
            data_validate=args.data_validate,
            data_update=args.data_update,
            data_unpack_pantry=args.data_unpack_pantry,
            data_pack_pantry=args.data_pack_pantry,
        )
        return args_config

    @property
    def env_with_overrides(self):
        result = dict(os.environ)
        for keyval in self.env_overrides:
            key, val = keyval.split("=", 1)
            result[key] = val
        return result

    def resolve_overrides(self, var):
        return utils.resolve_vars(var, self.env_with_overrides)


class WranglerConfigurable:
    """Mixin which reslts in self.config being defined for subclasses."""

    def __init__(self, config: Optional[WranglerConfig] = None):
        self.config = config or get_args_config()
