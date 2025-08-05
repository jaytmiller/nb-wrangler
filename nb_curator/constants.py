"""Global constants for nb-curator package."""

import os
import logging
from pathlib import Path

# Version
__version__ = "0.2.0"

# Path constants
HOME = Path(os.environ.get("HOME", "."))
NBC_ROOT = Path(os.environ.get("NBC_ROOT", HOME / ".nbc-live"))
NBC_MM = NBC_ROOT / "mm"
NBC_PANTRY = Path(os.environ.get("NBC_PANTRY", HOME / ".nbc-pantry"))
REPOS_DIR = Path("./references")
DEFAULT_MICROMAMBA_PATH = NBC_MM / "bin" / "micromamba"

# Notebook testing constants
NOTEBOOK_TEST_MAX_SECS = 30 * 60  # 1800 seconds
NOTEBOOK_TEST_JOBS = 4

# Timeout constants (in seconds)
DEFAULT_TIMEOUT = 300
REPO_CLONE_TIMEOUT = 300
ENV_INSTALL__TIMEOUT = 600
ENV_CREATE_TIMEOUT = 600
INSTALL_PACKAGES_TIMEOUT = 1200
PIP_COMPILE_TIMEOUT = 600
IMPORT_TEST_TIMEOUT = 300

# Package lists
TARGET_PACKAGES = ["uv", "pip", "ipykernel", "jupyter", "cython", "setuptools", "wheel"]
CURATOR_PACKAGES = ["papermill"] + TARGET_PACKAGES

# Logger configuration constants
VALID_LOG_TIME_MODES = ["none", "normal", "elapsed", "both"]
DEFAULT_LOG_TIMES_MODE = "elapsed"
VALID_COLOR_MODES = ["auto", "on", "off"]
DEFAULT_COLOR_MODE = "off"
