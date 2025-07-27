"""Configuration management for nb-curator."""

import os.path
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import argparse

HOME = Path(os.environ.get("HOME", "."))

NBC_ROOT = Path(os.environ.get("NBC_ROOT", HOME / ".nb-curator"))

NBC_MM = NBC_ROOT / "mm"

NBC_PANTRY = Path(os.environ.get("NBC_PANTRY", HOME / ".nb-pantry"))

REPOS_DIR = Path("./references")

DEFAULT_MICROMAMBA_PATH = NBC_MM / "bin" / "micromamba"

NOTEBOOK_TEST_MAX_SECS = 30 * 60
NOTEBOOK_TEST_JOBS = 4


@dataclass
class CuratorConfig:
    """Configuration class for NotebookCurator."""

    spec_file: str

    micromamba_path: str = DEFAULT_MICROMAMBA_PATH
    output_dir: Path = NBC_ROOT / "temps"
    verbose: bool = False
    debug: bool = False
    log_times: bool = False  # Add the new log_times parameter

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
        self.repos_dir = Path(self.repos_dir)
        if self.curate:
            self.compile_packages = True
            self.install_packages = True
            self.test_notebooks = ".*"

        # Validate log_times parameter
        if not isinstance(self.log_times, bool):
            raise ValueError("log_times must be a boolean value")

    @classmethod
    def from_args(cls, args: argparse.Namespace, spec_file: str) -> "CuratorConfig":
        """Create CuratorConfig from argparse Namespace and spec file."""
        return cls(
            spec_file=spec_file,
            micromamba_path=args.micromamba_path,
            verbose=args.verbose,
            debug=args.debug,
            log_times=args.log_times,
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
