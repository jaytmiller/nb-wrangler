"""Logging utilities for nb-wrangler."""

import sys
import logging
import pdb
import traceback
import datetime
from pprint import pformat


from . import utils
from .constants import (
    VALID_LOG_TIME_MODES,
    DEFAULT_LOG_TIMES_MODE,
    DEFAULT_COLOR_MODE,
)


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

NORMAL_COLOR = ANSI_COLORS["blue-foreground"]
ELAPSED_COLOR = ANSI_COLORS["cyan-foreground"]
MESSAGE_COLOR = ANSI_COLORS["bold"]
RESET_COLOR = ANSI_COLORS["reset"]


class ColorAndTimeFormatter(logging.Formatter):
    def __init__(self, log_times: str = "none", color: str = "auto", *args, **keys):
        assert (
            log_times in VALID_LOG_TIME_MODES
        ), f"Invalid log_times value {log_times}."
        self.log_times = log_times
        self.color = color
        self.start_time = datetime.datetime.now()  # message-to-message init

    @property
    def use_color(self):
        if self.color == "auto" and sys.stderr.isatty():
            return True
        elif self.color == "on":
            return True
        else:
            return False

    def _build_format_string(self, record, elapsed):
        """Build the log format string with appropriate colors."""
        level_color = ANSI_COLORS[LEVEL_COLORS.get(record.levelno, "reset")]
        if not self.use_color:
            reset_color = normal_color = elapsed_color = message_color = level_color = (
                ""
            )
        else:
            normal_color = NORMAL_COLOR
            elapsed_color = ELAPSED_COLOR
            message_color = MESSAGE_COLOR
            reset_color = RESET_COLOR
        log_fmt = level_color + "%(levelname)s: "
        if self.log_times in ["normal", "both"]:
            log_fmt += normal_color + "%(asctime)s%(msecs)03d "
        if self.log_times in ["elapsed", "both"]:
            log_fmt += elapsed_color + elapsed + " "
        log_fmt += reset_color + message_color + "%(message)s"
        return log_fmt

    def format(self, record):
        self.start_time, elapsed_str = utils.elapsed_time(self.start_time)
        log_fmt = self._build_format_string(record, elapsed_str)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d-%H:%M:%S")
        return formatter.format(record)


class WranglerLogger:
    """Enhanced logger with error tracking and debug support."""

    def __init__(
        self,
        verbose: bool = False,
        debug_mode: bool = False,
        log_times: str = DEFAULT_LOG_TIMES_MODE,
        color: str = DEFAULT_COLOR_MODE,
    ):
        self.verbose = verbose
        self.debug_mode = debug_mode
        self.log_times = log_times
        self.color = color
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.exceptions: list[str] = []
        self.start_time = datetime.datetime.now()
        self._configure_logger()

    def _configure_logger(self):
        """Configure logger based on current settings."""
        color_and_time_formatter = ColorAndTimeFormatter(
            log_times=self.log_times, color=self.color
        )
        color_and_time_handler = logging.StreamHandler()
        color_and_time_handler.setFormatter(color_and_time_formatter)
        logging.basicConfig(
            level=logging.DEBUG if self.verbose else logging.INFO,
            handlers=[color_and_time_handler],
            force=True,  # Override any existing configuration
            # format="%(levelname)s - %(message)s",
            # datefmt="%Y-%m-%dT%H:%M:%S",  # ISO 8601 format
        )
        self.logger = logging.getLogger("wrangler")

    def _lformat(self, *args) -> str:
        return " ".join(map(str, args))

    def error(self, *args) -> bool:
        """Log an error message and return False."""
        msg = self._lformat(*args)
        self.errors.append(msg)
        self.logger.error(msg)
        if self.debug_mode:
            pdb.set_trace()
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
        return utils.elapsed_time(self.start_time)[1]

    def print_log_counters(self):
        """Print summary of logged messages."""
        self.info(f"Exceptions: {len(self.exceptions)}")
        self.info(f"Errors: {len(self.errors)}")
        self.info(f"Warnings: {len(self.warnings)}")
        self.info(f"Elapsed: {self.elapsed_time[:-4]}")

    @classmethod
    def pformat(cls, *args, **keys):
        return pformat(*args, **keys)

    @classmethod
    def from_config(cls, config) -> "WranglerLogger":
        """Create a WranglerLogger from a WranglerConfig.

        Args:
            config: WranglerConfig instance

        Returns:
            WranglerLogger instance configured from the config
        """
        return cls(
            verbose=config.verbose,
            debug_mode=config.debug,
            log_times=config.log_times,
            color=config.color,
        )
