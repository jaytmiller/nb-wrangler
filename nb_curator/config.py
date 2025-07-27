"""Configuration management for nb-curator."""

import os.path
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

HOME = Path(os.environ.get("HOME", "."))

NBC_ROOT = Path(
    os.environ.get("NBC_ROOT",  HOME / ".nb-curator")
)

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

    micromamba_path: str = DEFAULT_MICRO_MAMBA_PATH
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

    omimt_spi_packages = False
    inject_spi: bool = False
    submit_for_build: bool = False

    reset_spec: bool = False

    curate: bool = False

    def __post_init__(self):
        """Post-initialization processing."""
        self.output_dir = Path(self.output_dir)
        self.repos_dir = (
            Path(self.repos_dir) if self.repos_dir else Path.cwd() / "repos"
        )
        if self.curate:
            self.compile_packages = True
            self.install_packages = True
            self.test_notebooks = ".*"

        # Validate log_times parameter
        if not isinstance(self.log_times, bool):
            raise ValueError("log_times must be a boolean value")

    @property
    def spec_file_out(self) -> Path:
        """Output path for the spec file."""
        return os.path.basename(self.spec_file)
