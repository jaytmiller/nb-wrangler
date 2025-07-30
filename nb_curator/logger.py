"""Logging utilities for nb-curator."""

import sys
import logging
import pdb
import traceback
import datetime

from . import utils

ANSI_COLORS = {
    "black-foreground": "\033[0;30m",
    "black-background": "\033[0;40m",
    "red-foreground": "\033[0;31m",
    "red-background": "\033[0;41m",
    "green-foreground": "\033[0;32m",
    "green-background": "\033[0;42m",
    "yellow-foreground": "\033[0;33m",
    "yellow-background": "\033[0;43m",
    "blue-foreground": "\033[0;34m",
    "blue-background": "\033[0;44m",
    "magenta-foreground": "\033[0;35m",
    "magenta-background": "\033[0;45m",
    "cyan-foreground": "\033[0;36m",
    "cyan-background": "\033[0;46m",
    "white-foreground": "\033[0;37m",
    "white-background": "\033[0;47m",
    "bright-black-foreground": "\033[1;30m",
    "bright-black-background": "\033[1;40m",
    "bright-red-foreground": "\033[1;31m",
    "bright-red-background": "\033[1;41m",
    "bright-green-foreground": "\033[1;32m",
    "bright-green-background": "\033[1;42m",
    "bright-yellow-foreground": "\033[1;33m",
    "bright-yellow-background": "\033[1;43m",
    "bright-blue-foreground": "\033[1;34m",
    "bright-blue-background": "\033[1;44m",
    "bright-magenta-foreground": "\033[1;35m",
    "bright-magenta-background": "\033[1;45m",
    "bright-cyan-foreground": "\033[1;36m",
    "bright-cyan-background": "\033[1;46m",
    "bright-white-foreground": "\033[1;37m",
    "bright-white-background": "\033[1;47m",
    "gray-foreground": "\033[0;90m",
    "gray-background": "\033[0;100m",
    "bright-gray-foreground": "\033[1;90m",
    "bright-gray-background": "\033[1;100m",
    "light-red-foreground": "\033[0;91m",
    "light-red-background": "\033[0;101m",
    "light-green-foreground": "\033[0;92m",
    "light-green-background": "\033[0;102m",
    "reset": "\x1b[0m",
    "none": "",
}

LEVEL_COLORS = {
    logging.DEBUG: "magenta-foreground",
    logging.INFO: "green-foreground",
    logging.WARNING: "yellow-foreground",
    logging.ERROR: "red-foreground",
    logging.CRITICAL: "bright-red-foreground",
}

TIME_COLORS = {
    "normal": "blue-foreground",
    "elapsed": "cyan-foreground",
    "both": "light-green-foreground",
    "none": "none",
}

NORMAL_COLOR = ANSI_COLORS["blue-foreground"]
ELAPSED_COLOR = ANSI_COLORS["cyan-foreground"]
MESSAGE_COLOR = ANSI_COLORS["bright-black-background"]
RESET_COLOR = ANSI_COLORS["reset"]

VALID_LOG_TIME_MODES = ["none", "normal", "elapsed", "both"]
DEFAULT_LOG_TIMES_MODE = "elapsed"

VALID_COLOR_MODE = ["auto", "on", "off"]
DEFAULT_USE_COLOR_MODE = "auto"


class ColorAndTimeFormatter(logging.Formatter):
    def __init__(self, log_times: str = "none", color: str = "auto", *args, **keys):
        assert (
            log_times in VALID_LOG_TIME_MODES
        ), f"Invalid log_times value {log_times}."
        self.log_times = log_times
        self.color = color

    @property
    def use_color(self):
        if self.color == "auto" and not sys.stderr.isatty() and not sys.stdout.isatty():
            return True
        elif self.color == "on":
            return True
        else:
            return False

    def format(self, record):
        elapsed = utils.elapsed_time(
            getattr(self, "_start_time", datetime.datetime.now())
        )
        self._start_time = datetime.datetime.now()
        level_color = ANSI_COLORS[LEVEL_COLORS.get(record.levelno, "reset")]
        if not self.use_color:
            NORMAL_COLOR = ELAPSED_COLOR = MESSAGE_COLOR = level_color = ""
        log_fmt = level_color + "%(levelname)s: "
        if self.log_times in ["normal", "both"]:
            log_fmt += NORMAL_COLOR + "%(asctime)s%(msecs)03d "
        if self.log_times in ["elapsed", "both"]:
            log_fmt += ELAPSED_COLOR + elapsed + " "
        log_fmt += RESET_COLOR + MESSAGE_COLOR + "%(message)s"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d-%H:%M:%S")
        return formatter.format(record)


class CuratorLogger:
    """Enhanced logger with error tracking and debug support."""

    def __init__(
        self,
        verbose: bool = False,
        debug_mode: bool = False,
        log_times: str = DEFAULT_LOG_TIMES_MODE,
        use_color: str = DEFAULT_USE_COLOR_MODE,
    ):
        self.verbose = verbose
        self.debug_mode = debug_mode
        self.log_times = log_times
        self.use_color = use_color
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.exceptions: list[str] = []
        self.start_time = datetime.datetime.now()
        self._configure_logger()

    def _configure_logger(self):
        """Configure logger based on current settings."""
        color_and_time_formatter = ColorAndTimeFormatter(self.log_times)
        color_and_time_handler = logging.StreamHandler()
        color_and_time_handler.setFormatter(color_and_time_formatter)
        logging.basicConfig(
            level=logging.DEBUG if self.verbose else logging.INFO,
            handlers=[color_and_time_handler],
            force=True,  # Override any existing configuration
            # format="%(levelname)s - %(message)s",
            # datefmt="%Y-%m-%dT%H:%M:%S",  # ISO 8601 format
        )
        self.logger = logging.getLogger("curator")

    def _lformat(self, *args) -> str:
        return " ".join(map(str, args))

    def error(self, *args) -> bool:
        """Log an error message and return False."""
        msg = self._lformat(*args)
        self.errors.append(msg)
        self.logger.error(msg)
        return False

    def info(self, *args) -> bool:
        """Log an info message and return True."""
        self.logger.info(self._lformat(*args))
        return True

    def warning(self, *args) -> bool:
        """Log a warning message and return True."""
        msg = self._lformat(*args)
        self.warnings.append(msg)
        self.logger.warning(msg)
        return True

    def debug(self, *args) -> None:
        """Log a debug message."""
        self.logger.debug(self._lformat(*args))
        return None  # falsy,  but neither True nor False

    def exception(self, e: Exception, *args) -> bool:
        """Handle an exception with optional debugging."""
        msg = self._lformat(*args)
        self.exceptions.append(msg)
        self.error("EXCEPTION: ", msg)
        if self.debug_mode:
            print(f"\n*** DEBUG MODE: Exception caught: {msg} ***")
            print("*** Dropping into debugger. Type 'c' to continue, 'q' to quit. ***")
            print(f"*** Exception type: {type(e).__name__} ***")
            print(f"*** Exception message: {str(e)} ***")
            print("*** Traceback (most recent call last): ***")
            traceback.print_tb(e.__traceback__)
            pdb.post_mortem(e.__traceback__)
            raise e
        return False

    @property
    def elapsed_time(self):
        return utils.elapsed_time(self.start_time)

    def print_log_counters(self):
        """Print summary of logged messages."""
        print(f"Exceptions: {len(self.exceptions)}")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"Elapsed: {self.elapsed_time[:-4]}")

    @classmethod
    def from_config(cls, config) -> "CuratorLogger":
        """Create a CuratorLogger from a CuratorConfig.

        Args:
            config: CuratorConfig instance

        Returns:
            CuratorLogger instance configured from the config
        """
        return cls(
            verbose=config.verbose, debug_mode=config.debug, log_times=config.log_times
        )
