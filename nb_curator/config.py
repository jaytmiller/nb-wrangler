# nb_curator/config.py
"""Configuration management for nb-curator."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import argparse

from . import logger
from .constants import (
    NBC_ROOT,
    DEFAULT_MICROMAMBA_PATH,
    NOTEBOOK_TEST_MAX_SECS,
    NOTEBOOK_TEST_JOBS,
    DEFAULT_LOG_TIMES_MODE,
    DEFAULT_COLOR_MODE,
    VALID_LOG_TIME_MODES,
)


@dataclass
class CuratorConfig:
    """Configuration class for NotebookCurator."""

    spec_file: str

    logger: Optional["logger.CuratorLogger"] = None
    micromamba_path: Path = DEFAULT_MICROMAMBA_PATH
    output_dir: Path = NBC_ROOT / "temps"
    verbose: bool = False
    debug: bool = False
    log_times: str = DEFAULT_LOG_TIMES_MODE
    color: str = DEFAULT_COLOR_MODE

    repos_dir: Path = Path("./references")
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

    workflow: str = "explicit"

    def __post_init__(self):
        """Post-initialization processing."""
        self.logger = logger.CuratorLogger.from_config(self)
        self.repos_dir = Path(self.repos_dir)

        # Validate log_times parameter
        if self.log_times not in VALID_LOG_TIME_MODES:
            raise ValueError(f"log_times must be one of {VALID_LOG_TIME_MODES}")

        if self.test_all:
            self.test_imports = True
            self.test_notebooks = ".*"

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "CuratorConfig":
        """Create CuratorConfig from argparse Namespace and spec file."""
        return cls(
            spec_file=args.spec_uri,
            micromamba_path=args.micromamba_path,
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
            workflow=args.workflow,
        )
