"""Logging utilities for nb-curator."""

import logging
import pdb
import traceback
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from nb_curator.config import CuratorConfig


class CuratorLogger:
    """Enhanced logging with error tracking and debug support."""

    def __init__(
        self, verbose: bool = False, debug_mode: bool = False, log_times: bool = False
    ):
        self.verbose = verbose
        self.debug_mode = debug_mode
        self.log_times = log_times
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.exceptions: List[str] = []

        # Configure logging with the current settings
        self._configure_logging()

    def _configure_logging(self):
        """Configure logging based on current settings."""
        # Configure log format based on log_times setting
        log_format = "%(levelname)s - %(message)s"
        if self.log_times:
            log_format = "%(asctime)s " + log_format

        # Set up logging
        logging.basicConfig(
            level=logging.DEBUG if self.verbose else logging.INFO,
            format=log_format,
            datefmt="%Y-%m-%dT%H:%M:%S",  # ISO 8601 format
            force=True,  # Override any existing configuration
        )
        self.logger = logging.getLogger("curator")

    def reconfigure_logging(
        self, verbose: bool = None, debug_mode: bool = None, log_times: bool = None
    ):
        """Reconfigure logging settings dynamically.

        Args:
            verbose: If provided, update verbose setting
            debug_mode: If provided, update debug_mode setting
            log_times: If provided, update log_times setting
        """
        if verbose is not None:
            self.verbose = verbose
        if debug_mode is not None:
            self.debug_mode = debug_mode
        if log_times is not None:
            self.log_times = log_times

        # Reconfigure with new settings
        self._configure_logging()

    def update_from_config(self, config: "CuratorConfig"):
        """Update logger settings from CuratorConfig.

        Args:
            config: CuratorConfig instance with logging settings
        """
        self.reconfigure_logging(
            verbose=config.verbose, debug_mode=config.debug, log_times=config.log_times
        )

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

    def print_log_counters(self):
        """Print summary of logged messages."""
        print(f"Exceptions: {len(self.exceptions)}")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")

    @classmethod
    def from_config(cls, config: "CuratorConfig") -> "CuratorLogger":
        """Create a CuratorLogger from a CuratorConfig.

        Args:
            config: CuratorConfig instance

        Returns:
            CuratorLogger instance configured from the config
        """
        return cls(
            verbose=config.verbose, debug_mode=config.debug, log_times=config.log_times
        )
