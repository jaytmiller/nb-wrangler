"""Logging utilities for nb-curator."""

import sys
import logging
import pdb
import traceback
import datetime
from pprint import pformat


from . import utils
from .constants import (
    ANSI_COLORS,
    LEVEL_COLORS,
    NORMAL_COLOR,
    ELAPSED_COLOR,
    MESSAGE_COLOR,
    RESET_COLOR,
    VALID_LOG_TIME_MODES,
    DEFAULT_LOG_TIMES_MODE,
    DEFAULT_USE_COLOR_MODE,
)


class ColorAndTimeFormatter(logging.Formatter):
    def __init__(self, log_times: str = "none", color: str = "auto", *args, **keys):
        assert (
            log_times in VALID_LOG_TIME_MODES
        ), f"Invalid log_times value {log_times}."
        self.log_times = log_times
        self.color = color

    @property
    def use_color(self):
        if self.color == "auto" or sys.stderr.isatty():
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
            normal_color = elapsed_color = message_color = level_color = ""
        else:
            normal_color = NORMAL_COLOR
            elapsed_color = ELAPSED_COLOR
            message_color = MESSAGE_COLOR
        log_fmt = level_color + "%(levelname)s: "
        if self.log_times in ["normal", "both"]:
            log_fmt += normal_color + "%(asctime)s%(msecs)03d "
        if self.log_times in ["elapsed", "both"]:
            log_fmt += elapsed_color + elapsed + " "
        log_fmt += RESET_COLOR + message_color + "%(message)s"
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
    def pformat(cls, *args, **keys):
        return pformat(*args, **keys)

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
