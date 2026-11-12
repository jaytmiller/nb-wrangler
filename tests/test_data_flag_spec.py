"""Tests for the optional per-repository `data: on|off` spec flag.

Covers the constants normalization helper, the SpecValidator value check, and
the SpecManager accessor helpers (all-on / all-off / mixed / single-repo, plus
dev_overrides behavior in --dev and --prod).
"""

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from nb_wrangler.config import WranglerConfig, set_args_config

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _valid_spec(repositories=None, dev_repositories=None):
    spec = {
        "image_spec_header": {
            "image_name": "data-flag-test",
            "kernel_name": "dataflag",
            "deployment_name": "wrangler",
            "python_version": "3.12",
            "valid_on": "2026-01-01",
            "expires_on": "2027-01-01",
        },
        "repositories": repositories or {},
        "system": {
            "spec_version": 2.3,
            "spi": {"repo": "https://example.com/spi.git"},
            "nb-wrangler": {"repo": "https://example.com/nbw.git"},
            "date_updated": "2026-01-01T00:00:00",
        },
    }
    if dev_repositories is not None:
        spec["dev_overrides"] = {"repositories": dev_repositories}
    return spec


def _write_spec(tmp_path: Path, spec_dict: dict) -> Path:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(yaml.dump(spec_dict, sort_keys=False))
    return spec_file


def _load_manager(spec_file: Path, dev: bool = False):
    from nb_wrangler.spec_manager import SpecManager

    # config.dev is read from the config object captured at SpecManager
    # construction time, so set it before building the manager.
    set_args_config(
        WranglerConfig(
            workflows=[],
            repos_dir=spec_file.parent / "references",
            dev=dev,
            prod=not dev,
        )
    )
    sm = SpecManager()
    assert sm.load_spec(spec_file) is True, "spec failed to load"
    assert sm.validate() is True, "spec failed to validate"
    return sm


# ---------------------------------------------------------------------------
# constants.data_flag_enabled normalization
# ---------------------------------------------------------------------------


class TestDataFlagEnabled:
    def test_on_forms(self):
        from nb_wrangler.constants import data_flag_enabled

        for value in ["on", "yes", "true", "True", " ON "]:
            assert data_flag_enabled(value) is True, f"expected on for {value!r}"

    def test_off_forms(self):
        from nb_wrangler.constants import data_flag_enabled

        for value in ["off", "no", "false", "False", " OFF "]:
            assert data_flag_enabled(value) is False, f"expected off for {value!r}"

    def test_invalid_and_absent(self):
        from nb_wrangler.constants import data_flag_enabled

        assert data_flag_enabled("bogus") is None
        assert data_flag_enabled(3) is None
        assert data_flag_enabled(None) is None
        assert data_flag_enabled({"data": "on"}) is None


# ---------------------------------------------------------------------------
# SpecValidator value check
# ---------------------------------------------------------------------------


def _make_validator(tmp_path, spec: dict):
    from nb_wrangler.spec_manager import SpecManager
    from nb_wrangler.spec_validator import SpecValidator

    set_args_config(
        WranglerConfig(workflows=[], spec_file="", repos_dir=tmp_path / "repos")
    )
    mock_sm = MagicMock()
    mock_sm._spec = spec
    mock_sm.header = spec["image_spec_header"]
    mock_sm.inline_mamba_spec = None
    mock_sm.environment_spec = None
    mock_sm.repositories = spec.get("repositories") or {}
    mock_sm.notebook_selections = spec.get("selected_notebooks") or {}
    mock_sm.system = spec.get("system") or {}
    mock_sm.REQUIRED_KEYWORDS = SpecManager.REQUIRED_KEYWORDS
    mock_sm.ALLOWED_KEYWORDS = SpecManager.ALLOWED_KEYWORDS
    return SpecValidator(mock_sm)


class TestValidatorDataFlag:
    def _assert_repositories_validation(self, tmp_path, repositories, expected):
        validator = _make_validator(tmp_path, _valid_spec(repositories))
        assert validator._validate_repositories_section() is expected

    def test_omitted_data_is_fine(self, tmp_path):
        self._assert_repositories_validation(
            tmp_path, {"r1": {"url": "https://example.com/r1.git"}}, True
        )

    def test_on_forms_validate(self, tmp_path):
        for value in ["on", "yes", "true", "True"]:
            self._assert_repositories_validation(
                tmp_path,
                {"r1": {"url": "https://example.com/r1.git", "data": value}},
                True,
            )

    def test_off_forms_validate(self, tmp_path):
        for value in ["off", "no", "false", "False"]:
            self._assert_repositories_validation(
                tmp_path,
                {"r1": {"url": "https://example.com/r1.git", "data": value}},
                True,
            )

    def test_invalid_data_values_fail(self, tmp_path):
        for value in ["bogus", 3, None, "maybe"]:
            self._assert_repositories_validation(
                tmp_path,
                {"r1": {"url": "https://example.com/r1.git", "data": value}},
                False,
            )

    def test_unknown_repo_keyword_still_fails(self, tmp_path):
        self._assert_repositories_validation(
            tmp_path,
            {"r1": {"url": "https://example.com/r1.git", "wrong_key": "x"}},
            False,
        )

    def test_data_allowed_in_dev_overrides(self, tmp_path):
        validator = _make_validator(
            tmp_path,
            _valid_spec(
                {"r1": {"url": "https://example.com/r1.git"}},
                dev_repositories={"r1": {"data": "off"}},
            ),
        )
        assert validator._validate_dev_overrides_section() is True


# ---------------------------------------------------------------------------
# SpecManager accessors
# ---------------------------------------------------------------------------


class TestRepoDataAccessors:
    def test_omitted_defaults_enabled(self, tmp_path):
        sm = _load_manager(
            _write_spec(
                tmp_path,
                _valid_spec({"r1": {"url": "https://example.com/r1.git"}}),
            )
        )
        assert sm.repo_data_enabled("r1") is True
        assert sm.data_enabled_repo_names() == ["r1"]
        assert sm.data_disabled_repo_names() == []
        assert sm.all_data_disabled() is False

    def test_on_and_off_values(self, tmp_path):
        sm = _load_manager(
            _write_spec(
                tmp_path,
                _valid_spec(
                    {
                        "on_repo": {"url": "https://example.com/on.git", "data": "on"},
                        "yes_repo": {
                            "url": "https://example.com/yes.git",
                            "data": "yes",
                        },
                        "off_repo": {
                            "url": "https://example.com/off.git",
                            "data": "off",
                        },
                        "no_repo": {"url": "https://example.com/no.git", "data": "no"},
                    }
                ),
            )
        )
        assert sm.data_enabled_repo_names() == ["on_repo", "yes_repo"]
        assert sm.data_disabled_repo_names() == ["off_repo", "no_repo"]
        assert sm.all_data_disabled() is False

    def test_normalized_yaml_bool_forms(self, tmp_path):
        # YAML `data: true/false` parse as bools and normalize to 'True'/'False'.
        sm = _load_manager(
            _write_spec(
                tmp_path,
                _valid_spec(
                    {
                        "bool_on": {"url": "https://example.com/a.git", "data": True},
                        "bool_off": {"url": "https://example.com/b.git", "data": False},
                    }
                ),
            )
        )
        assert sm.repo_data_enabled("bool_on") is True
        assert sm.repo_data_enabled("bool_off") is False

    def test_all_off(self, tmp_path):
        sm = _load_manager(
            _write_spec(
                tmp_path,
                _valid_spec(
                    {
                        "r1": {
                            "url": "https://example.com/r1.git",
                            "data": "off",
                        },
                        "r2": {
                            "url": "https://example.com/r2.git",
                            "data": "false",
                        },
                    }
                ),
            )
        )
        assert sm.all_data_disabled() is True
        assert sm.data_enabled_repo_names() == []
        assert sorted(sm.data_disabled_repo_names()) == ["r1", "r2"]

    def test_single_repo_spec(self, tmp_path):
        sm = _load_manager(
            _write_spec(
                tmp_path,
                _valid_spec(
                    {"r1": {"url": "https://example.com/r1.git", "data": "off"}}
                ),
            )
        )
        assert sm.all_data_disabled() is True
        assert sm.data_disabled_repo_names() == ["r1"]

    def test_invalid_value_defaults_to_enabled_in_accessor(self, tmp_path):
        # A spec with an invalid data value fails validation, but the accessor
        # must not hard-fail data collection in the meantime.
        set_args_config(
            WranglerConfig(
                workflows=[], repos_dir=tmp_path / "repos", spec_file=str(tmp_path)
            )
        )
        from nb_wrangler.spec_manager import SpecManager

        sm = SpecManager()
        sm._spec = _valid_spec(
            {"r1": {"url": "https://example.com/r1.git", "data": "bogus"}}
        )
        assert sm.repo_data_enabled("r1") is True

    def test_dev_override_off_respected_in_dev_ignored_in_prod(self, tmp_path):
        spec_file = _write_spec(
            tmp_path,
            _valid_spec(
                {"r1": {"url": "https://example.com/r1.git", "data": "on"}},
                dev_repositories={"r1": {"data": "off"}},
            ),
        )
        sm = _load_manager(spec_file, dev=True)
        assert sm.repo_data_enabled("r1") is False
        assert sm.all_data_disabled() is True
        # Switch to --prod: the base value (on) governs again.
        sm.config.dev = False
        assert sm.repo_data_enabled("r1") is True
        assert sm.all_data_disabled() is False
