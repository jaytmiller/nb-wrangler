"""Tests for nb_wrangler/constants.py."""

import os
import platform
from pathlib import Path

from nb_wrangler.constants import (
    __version__,
    WRANGLER_SPEC_VERSION,
    HOME,
    NBW_ROOT,
    NBW_PANTRY,
    NBW_CACHE,
    NBW_MM,
    NBW_MAMBA_CMD,
    NBW_PIP_CMD,
    REPOS_DIR,
    DATA_DIR,
    NBW_URI,
    BUILTIN_PACKAGES,
    DEFAULT_ARCHIVE_FORMAT,
    VALID_ARCHIVE_FORMATS,
    DEFAULT_DATA_ENV_VARS_MODE,
    DEFAULT_REGISTRY,
    DEFAULT_PROJECT,
    NOTEBOOK_TEST_MAX_SECS,
    NOTEBOOK_TEST_JOBS,
    NOTEBOOK_TEST_EXCLUDE,
    DEFAULT_TIMEOUT,
    REPO_CLONE_TIMEOUT,
    DATA_GET_TIMEOUT,
    ENV_CREATE_TIMEOUT,
    INSTALL_PACKAGES_TIMEOUT,
    PIP_COMPILE_TIMEOUT,
    IMPORT_TEST_TIMEOUT,
    ARCHIVE_TIMEOUT,
    DOCKER_BUILD_TIMEOUT,
    TARGET_PACKAGES,
    CURATOR_PACKAGES,
    VALID_LOG_TIME_MODES,
    DEFAULT_LOG_TIMES_MODE,
    VALID_COLOR_MODES,
    DEFAULT_COLOR_MODE,
    DATA_SPEC_NAME,
    DEFAULT_CLEANUP_PATTERNS,
)


class TestVersionAndSpec:
    def test_version_is_string(self):
        assert isinstance(__version__, str)

    def test_spec_version_is_float(self):
        assert isinstance(WRANGLER_SPEC_VERSION, float)


class TestStructuralInvariants:
    """Collapse trivial constant assertions into parametrized structural invariants."""

    def test_archive_formats_valid_and_nonempty(self):
        assert isinstance(VALID_ARCHIVE_FORMATS, list)
        assert len(VALID_ARCHIVE_FORMATS) > 0
        assert DEFAULT_ARCHIVE_FORMAT in VALID_ARCHIVE_FORMATS
        assert ".tar.gz" in VALID_ARCHIVE_FORMATS

    def test_all_timeouts_are_positive_integers(self):
        timeouts = (
            ("DEFAULT_TIMEOUT", DEFAULT_TIMEOUT),
            ("REPO_CLONE_TIMEOUT", REPO_CLONE_TIMEOUT),
            ("DATA_GET_TIMEOUT", DATA_GET_TIMEOUT),
            ("ENV_CREATE_TIMEOUT", ENV_CREATE_TIMEOUT),
            ("INSTALL_PACKAGES_TIMEOUT", INSTALL_PACKAGES_TIMEOUT),
            ("PIP_COMPILE_TIMEOUT", PIP_COMPILE_TIMEOUT),
            ("IMPORT_TEST_TIMEOUT", IMPORT_TEST_TIMEOUT),
            ("ARCHIVE_TIMEOUT", ARCHIVE_TIMEOUT),
            ("DOCKER_BUILD_TIMEOUT", DOCKER_BUILD_TIMEOUT),
        )
        for name, value in timeouts:
            assert isinstance(value, int), f"{name} is not an int"
            assert value > 0, f"{name} should be positive"

    def test_notebook_test_max_secs_is_positive_int(self):
        assert isinstance(NOTEBOOK_TEST_MAX_SECS, int)
        assert NOTEBOOK_TEST_MAX_SECS > 0

    def test_jupyter_test_timeout_is_int(self):
        assert isinstance(NOTEBOOK_TEST_JOBS, int)
        assert isinstance(NOTEBOOK_TEST_EXCLUDE, str)

class TestPackageLists:
    def test_target_packages_non_empty(self):
        assert len(TARGET_PACKAGES) > 0

    def test_curator_packages_includes_papermill_and_target(self):
        assert "papermill" in CURATOR_PACKAGES
        for pkg in TARGET_PACKAGES:
            assert pkg in CURATOR_PACKAGES

class TestPathConstants:
    """Tests that are actually testable at import time."""
    def test_repos_dir_is_string(self):
        assert isinstance(REPOS_DIR, str)

    def test_data_spec_path_ends_with_yaml(self):
        assert DATA_SPEC_NAME.endswith(".yaml")


class TestOtherConstants:
    def test_wrangler_uri_prefix(self):
        assert NBW_URI.startswith("nbw://")

    def test_builtin_packages_includes_sys_and_os(self):
        assert "sys" in BUILTIN_PACKAGES
        assert "os" in BUILTIN_PACKAGES

    def test_valid_log_time_modes_contains_elapsed(self):
        assert "elapsed" in VALID_LOG_TIME_MODES

    def test_default_log_times_is_elapsed(self):
        assert DEFAULT_LOG_TIMES_MODE == "elapsed"

    def test_valid_color_modes_contains_auto(self):
        assert "auto" in VALID_COLOR_MODES

    def test_default_color_mode_is_auto(self):
        assert DEFAULT_COLOR_MODE == "auto"

class TestCleanupPatterns:
    def test_default_cleanup_patterns_non_empty(self):
        assert len(DEFAULT_CLEANUP_PATTERNS) > 0

    def test_pattern_contains_pycache(self):
        assert "__pycache__" in DEFAULT_CLEANUP_PATTERNS

class TestTypingInvariants:
    """Verify that mutable defaults are lists and not ints/strings."""
    def test_collections_are_lists(self):
        assert isinstance(TARGET_PACKAGES, list)
        assert isinstance(CURATOR_PACKAGES, list)
        assert isinstance(DEFAULT_CLEANUP_PATTERNS, list)

    def test_defaults_are_expected_types(self):
        assert isinstance(DEFAULT_ARCHIVE_FORMAT, str)
        assert isinstance(DEFAULT_DATA_ENV_VARS_MODE, str)
        assert isinstance(DEFAULT_REGISTRY, str)
        assert isinstance(DEFAULT_PROJECT, str)
