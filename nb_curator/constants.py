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

# Logger constants
ANSI_COLORS = {
    "black-foreground": "\033[30m",
    "red-foreground": "\033[31m",
    "green-foreground": "\033[32m",
    "yellow-foreground": "\033[33m",
    "blue-foreground": "\033[34m",
    "magenta-foreground": "\033[35m",
    "cyan-foreground": "\033[36m",
    "white-foreground": "\033[37m",
    "bright-black-foreground": "\033[90m",
    "bright-red-foreground": "\033[91m",
    "bright-green-foreground": "\033[92m",
    "bright-yellow-foreground": "\033[93m",
    "bright-blue-foreground": "\033[94m",
    "bright-magenta-foreground": "\033[95m",
    "bright-cyan-foreground": "\033[96m",
    "bright-white-foreground": "\033[97m",
    "black-background": "\033[40m",
    "red-background": "\033[41m",
    "green-background": "\033[42m",
    "yellow-background": "\033[43m",
    "blue-background": "\033[44m",
    "magenta-background": "\033[45m",
    "cyan-background": "\033[46m",
    "white-background": "\033[47m",
    "bright-black-background": "\033[100m",
    "bright-red-background": "\033[101m",
    "bright-green-background": "\033[102m",
    "bright-yellow-background": "\033[103m",
    "bright-blue-background": "\033[104m",
    "bright-magenta-background": "\033[105m",
    "bright-cyan-background": "\033[106m",
    "bright-white-background": "\033[107m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "underline": "\033[4m",
    "blink": "\033[5m",
    "reverse": "\033[7m",
    "strikethrough": "\033[9m",
    "reset": "\033[0m",
}

LEVEL_COLORS = {
    logging.DEBUG: "magenta-foreground",
    logging.INFO: "green-foreground",
    logging.WARNING: "yellow-foreground",
    logging.ERROR: "red-foreground",
    logging.CRITICAL: "bright-red-foreground",
}

TIME_COLORS = {
    "normal": ANSI_COLORS["blue-foreground"],
    "elapsed": ANSI_COLORS["cyan-foreground"],
}

NORMAL_COLOR = ANSI_COLORS["blue-foreground"]
ELAPSED_COLOR = ANSI_COLORS["cyan-foreground"]
MESSAGE_COLOR = ANSI_COLORS["bright-black-background"]
RESET_COLOR = ANSI_COLORS["reset"]

# Logger configuration constants
VALID_LOG_TIME_MODES = ["none", "normal", "elapsed", "both"]
DEFAULT_LOG_TIMES_MODE = "elapsed"
VALID_COLOR_MODE = ["auto", "on", "off"]
DEFAULT_USE_COLOR_MODE = "auto"
