"""Tests for nb_wrangler/logger.py."""

import logging
import sys
from unittest.mock import patch, PropertyMock

import pytest

from nb_wrangler.logger import (
    ANSI_COLORS,
    LEVEL_COLORS,
    ColorAndTimeFormatter,
    WranglerLogger,
)


class TestColorConstants:
    def test_ansi_colors_has_foreground_keys(self):
        assert "red-foreground" in ANSI_COLORS
        assert "\033[31m" in ANSI_COLORS.values()

    def test_level_colors_all_levels_present(self):
        for level in [
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ]:
            assert level in LEVEL_COLORS


class TestColorAndTimeFormatter:
    def test_invalid_log_time_raises_value_error(self):
        with pytest.raises(AssertionError):
            ColorAndTimeFormatter(log_times="invalid")

    def test_use_color_auto_true_when_tty(self):
        with patch("sys.stderr.isatty", return_value=True):
            fmt = ColorAndTimeFormatter(color="auto")
            assert fmt.use_color is True

    def test_use_color_auto_false_when_not_tty(self):
        with patch("sys.stderr.isatty", return_value=False):
            fmt = ColorAndTimeFormatter(color="auto")
            assert fmt.use_color is False

    def test_use_color_on_forces_true(self):
        with patch("sys.stderr.isatty", return_value=False):
            fmt = ColorAndTimeFormatter(color="on")
            assert fmt.use_color is True

    def test_use_color_off_forces_false(self):
        with patch.object(sys.stderr, "isatty", return_value=True):
            fmt = ColorAndTimeFormatter(color="off")
            assert fmt.use_color is False


class TestWranglerLogger:
    def test_errors_list_stops_error_messages(self):
        logger = WranglerLogger(quiet=True)
        result = logger.error("err msg")
        assert result is False
        assert "err msg" in logger.errors

    def test_writes_warning_to_warnings(self):
        logger = WranglerLogger(quiet=True)
        result = logger.warning("warn msg")
        assert result is True
        assert "warn msg" in logger.warnings

    def test_exception_logs_and_returns_false(self):
        logger = WranglerLogger(quiet=True, debug_mode=False)
        e = ValueError("boom")
        result = logger.exception(e, "prefix")
        assert result is False
        assert len(logger.exceptions) >= 1
        assert len(logger.errors) >= 1  # exception logs to errors internally

    def test_info_returns_true(self):
        logger = WranglerLogger(quiet=True)
        result = logger.info("info msg")
        assert result is True

    def test_elapsed_time_returns_string(self):
        import datetime

        logger = WranglerLogger(quiet=True, debug_mode=False)
        elapsed = str(logger.elapsed_time)
        # Should contain colon-based time format
        assert ":" in elapsed


class TestWranglerLoggerFromConfig:
    def test_from_config_creates_logger(self):
        mock_config = type(
            "MockConfig",
            (),
            {
                "verbose": False,
                "quiet": True,
                "debug": False,
                "log_times": "elapsed",
                "color": "auto",
            },
        )()
        log = WranglerLogger.from_config(mock_config)
        assert isinstance(log, WranglerLogger)
        assert log.quiet is True
