"""Global constants for nb-wrangler package."""

import os
from pathlib import Path

# Version
__version__ = "0.2.0"

# Path constants
HOME = Path(os.environ.get("HOME", "."))
NBW_ROOT = Path(os.environ.get("NBW_ROOT", HOME / ".nbw-live"))
NBW_CACHE = Path(os.environ.get("NBW_CACHE", NBW_ROOT / "cache"))
NBW_MM = Path(os.environ.get("NBW_MM", NBW_ROOT / "mm"))
NBW_PANTRY = Path(os.environ.get("NBW_PANTRY", NBW_ROOT / "pantry"))
REPOS_DIR = Path("./references")
DEFAULT_MAMBA_COMMAND = Path(
    os.environ.get("NBW_MAMBA_CMD", NBW_MM / "bin" / "micromamba")
)
DEFAULT_PIP_COMMAND = Path(os.environ.get("NBW_PIP_CMD", "uv pip"))

BUILTIN_PACKAGES = ["__future__", "builtins", "sys", "os", "copy"]

DEFAULT_ARCHIVE_FORMAT = ".tar"
VALID_ARCHIVE_FORMATS = [
    ".tar.gz",
    ".tar.xz",
    ".tar",
    ".tar.bz2",
    ".tar.zst",
    ".tar.lzma",
    ".tar.lzo",
    ".tar.lz",
]

# Notebook testing constants
NOTEBOOK_TEST_MAX_SECS = 30 * 60  # 1800 seconds
NOTEBOOK_TEST_JOBS = 4

# Timeout constants (in seconds)
DEFAULT_TIMEOUT = 300
REPO_CLONE_TIMEOUT = 300
ENV_CREATE_TIMEOUT = 600
INSTALL_PACKAGES_TIMEOUT = 1200
PIP_COMPILE_TIMEOUT = 600
IMPORT_TEST_TIMEOUT = 60

# Package lists
TARGET_PACKAGES = ["uv", "pip", "ipykernel", "jupyter", "cython", "setuptools", "wheel"]
CURATOR_PACKAGES = ["papermill"] + TARGET_PACKAGES

# Logger configuration constants
VALID_LOG_TIME_MODES = ["none", "normal", "elapsed", "both"]
DEFAULT_LOG_TIMES_MODE = "elapsed"
VALID_COLOR_MODES = ["auto", "on", "off"]
DEFAULT_COLOR_MODE = "auto"
