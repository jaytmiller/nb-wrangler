"""Configuration management for nb-curator."""


from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import argparse

from . import logger
from .constants import (
    NBC_ROOT, 
    DEFAULT_MICROMAMBA_PATH, NOTEBOOK_TEST_MAX_SECS, NOTEBOOK_TEST_JOBS,
    DEFAULT_LOG_TIMES_MODE, DEFAULT_USE_COLOR_MODE, VALID_LOG_TIME_MODES
)


@dataclass
class CuratorConfig:
    """Configuration class for NotebookCurator."""

    spec_file: str

    logger = None
    micromamba_path: Path = DEFAULT_MICROMAMBA_PATH
    output_dir: Path = NBC_ROOT / "temps"
    verbose: bool = False
    debug: bool = False
    log_times: str = DEFAULT_LOG_TIMES_MODE
    use_color: str = DEFAULT_USE_COLOR_MODE

    repos_dir: Optional[Path] = Path("./references")
    clone_repos: bool = False
    delete_repos: bool = False

    init_env: bool = False
    pack_env: bool = False
    unpack_env: bool = False
    delete_env: bool = False

    compile_packages: bool = False
    install_packages: bool = False
    uninstall_packages: bool = False

    compact_curator: bool = False

    test_notebooks: str | None = None
    jobs: int = NOTEBOOK_TEST_JOBS
    timeout: int = NOTEBOOK_TEST_MAX_SECS

    omit_spi_packages: bool = False
    inject_spi: bool = False
    submit_for_build: bool = False

    reset_spec: bool = False

    curate: bool = False

    def __post_init__(self):
        """Post-initialization processing."""
        self.logger = logger.CuratorLogger(self.verbose, self.debug, self.log_times)
        self.repos_dir = Path(self.repos_dir)
        if self.curate:
            self.compile_packages = True
            self.install_packages = True
            self.test_notebooks = ".*"

        # Validate log_times parameter
        if self.log_times not in VALID_LOG_TIME_MODES:
            raise ValueError(f"log_times must be one of {VALID_LOG_TIME_MODES}")

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "CuratorConfig":
        """Create CuratorConfig from argparse Namespace and spec file."""
        return cls(
            spec_file=args.spec_uri,
            micromamba_path=args.micromamba_path,
            verbose=args.verbose,
            debug=args.debug,
            log_times=args.log_times,
            use_color=args.use_color,
            repos_dir=args.repos_dir,
            clone_repos=args.clone_repos,
            delete_repos=args.delete_repos,
            init_env=args.init_env,
            pack_env=args.pack_env,
            unpack_env=args.unpack_env,
            delete_env=args.delete_env,
            compile_packages=args.compile_packages,
            install_packages=args.install_packages,
            uninstall_packages=args.uninstall_packages,
            compact_curator=getattr(args, "compact_curator", False),
            test_notebooks=args.test_notebooks,
            jobs=args.jobs,
            timeout=args.timeout,
            omit_spi_packages=args.omit_spi_packages,
            inject_spi=args.inject_spi,
            submit_for_build=args.submit_for_build,
            reset_spec=args.reset_spec,
            curate=args.curate,
        )
