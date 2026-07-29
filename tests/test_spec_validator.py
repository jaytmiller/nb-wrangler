"""Tests for nb_wrangler/spec_validator.py."""

from unittest.mock import MagicMock

from nb_wrangler.config import WranglerConfig, set_args_config


def _make_validator(tmp_path):
    """Create a SpecValidator with a mock SpecManager that exposes required attributes."""
    from nb_wrangler.spec_manager import SpecManager
    from nb_wrangler.spec_validator import SpecValidator

    set_args_config(
        WranglerConfig(workflows=[], spec_file="", repos_dir=tmp_path / "repos")
    )

    # Build a minimal valid spec fixture
    valid_spec = {
        "image_spec_header": {
            "image_name": "test",
            "kernel_name": "test-env",
            "deployment_name": "wrangler",
            "python_version": "3.12",
        },
        "repositories": {},
        "extra_mamba_packages": [],
        "common_mamba_packages": [],
        "extra_pip_packages": [],
        "common_pip_packages": [],
        "apt_packages": [],
        "system": {
            "spec_version": 2.3,
            "spi": {"repo": "https://example.com/spi.git"},
            "nb-wrangler": {"repo": "https://example.com/nbw.git"},
            "date_updated": "2026-01-01T00:00:00",
        },
    }

    mock_sm = MagicMock()
    mock_sm._spec = valid_spec
    mock_sm.header = valid_spec["image_spec_header"]
    mock_sm.inline_mamba_spec = None
    mock_sm.environment_spec = None
    mock_sm.repositories = {}
    mock_sm.notebook_selections = {}
    mock_sm.system = valid_spec["system"]
    mock_sm.REQUIRED_KEYWORDS = {
        "image_spec_header": [
            "image_name",
            "kernel_name",
            "deployment_name",
            "python_version",
        ],
        "repositories": [],
        "system": {"spec_version": None, "spi": ["repo"], "nb-wrangler": ["repo"]},
    }
    mock_sm.ALLOWED_KEYWORDS = SpecManager.ALLOWED_KEYWORDS
    mock_sm.inline_mamba_spec is None
    mock_sm.config.dev = False

    validator = SpecValidator(mock_sm)
    return validator, mock_sm


def _make_bad_validator(tmp_path, invalid_spec, sm_kwargs=None):
    """Create a validator that reports errors."""
    from nb_wrangler.spec_manager import SpecManager
    from nb_wrangler.spec_validator import SpecValidator

    set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))

    mock_sm = MagicMock()
    mock_sm._spec = invalid_spec
    mock_sm.header = invalid_spec.get("image_spec_header", {})
    mock_sm.inline_mamba_spec = None
    mock_sm.environment_spec = None
    mock_sm.repositories = {}
    mock_sm.notebook_selections = invalid_spec.get("selected_notebooks", {})
    mock_sm.system = invalid_spec.get("system", {})
    mock_sm.REQUIRED_KEYWORDS = {
        "image_spec_header": [
            "image_name",
            "kernel_name",
            "deployment_name",
            "python_version",
        ],
        "repositories": [],
        "system": {"spec_version": None, "spi": ["repo"], "nb-wrangler": ["repo"]},
    }
    mock_sm.ALLOWED_KEYWORDS = SpecManager.ALLOWED_KEYWORDS
    mock_sm.config.dev = False

    if sm_kwargs:
        for k, v in sm_kwargs.items():
            setattr(mock_sm, k, v)

    validator = SpecValidator(mock_sm)
    return validator, mock_sm


class TestValidate:
    def test_valid_spec_returns_true(self, tmp_path):
        validator, _ = _make_validator(tmp_path)
        assert validator.validate() is True

    def test_empty_spec_returns_false(self, tmp_path):
        from nb_wrangler.spec_validator import SpecValidator

        mocker = MagicMock()
        mocker._spec = None
        log = MagicMock(error=MagicMock(return_value=False))
        mocker.logger = log
        v = SpecValidator(mocker)
        assert v.validate() is False


class TestMissingRequiredField:
    def test_missing_image_name_logged_error(self, tmp_path):
        spec = {
            "image_spec_header": {},
            "repositories": {},
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "r"},
                "nb-wrangler": {"repo": "r"},
            },
        }
        validator, mock_sm = _make_bad_validator(tmp_path, spec)

        assert validator.validate() is False


class TestUnknownTopLevelKeyword:
    def test_unknown_top_level_with_no_inline_mamba(self, tmp_path):
        spec = {
            "image_spec_header": {
                "image_name": "test",
                "kernel_name": "k",
                "deployment_name": "w",
                "python_version": "3.12",
            },
            "repositories": {},
            "extra_mamba_packages": [],
            "common_mamba_packages": [],
            "extra_pip_packages": [],
            "common_pip_packages": [],
            "apt_packages": [],
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "r"},
                "nb-wrangler": {"repo": "r"},
                "date_updated": "x",
            },
            "unknown_field": True,
        }
        validator, mock_sm = _make_bad_validator(tmp_path, spec)
        assert validator.validate() is False


class TestEnvironmentSpecValidation:
    def test_zero_methods_defined_error(self, tmp_path):
        spec = {
            "image_spec_header": {},
            "repositories": {},
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "r"},
                "nb-wrangler": {"repo": "r"},
            },
        }
        validator, mock_sm = _make_bad_validator(tmp_path, spec)
        assert validator.validate() is False

    def test_multiple_methods_defined_error(self, tmp_path):
        """Test that having both inline_mamba_spec and environment_spec triggers a validation error."""
        spec = {
            "image_spec_header": {"python_version": "3.12"},
            "repositories": {},
            "extra_mamba_packages": [{"name": "pkg"}],
            "common_mamba_packages": [],
            "extra_pip_packages": [],
            "common_pip_packages": [],
            "apt_packages": [],
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "r"},
                "nb-wrangler": {"repo": "r"},
                "date_updated": "x",
            },
        }

        class MockInline:
            pass

        from nb_wrangler.spec_validator import SpecValidator

        mocker = MagicMock()
        mocker._spec = spec
        mocker.header = spec["image_spec_header"]
        mocker.inline_mamba_spec = MockInline()
        mocker.environment_spec = {"channels": []}  # also defined
        mocker.repositories = {}
        mocker.notebook_selections = {}
        mocker.system = spec["system"]
        mocker.REQUIRED_KEYWORDS = {
            "image_spec_header": [],
            "repositories": [],
            "system": {},
        }
        mocker.ALLOWED_KEYWORDS = {}
        mocker.config.dev = False

        v = SpecValidator(mocker)
        result = v.validate()
        assert result is False


class TestSimpleDefinitionValidation:
    def test_missing_kernel_name(self, tmp_path):
        spec = {
            "image_spec_header": {"python_version": "3.12"},
            "repositories": {},
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "r"},
                "nb-wrangler": {"repo": "r"},
            },
        }
        validator, mock_sm = _make_bad_validator(tmp_path, spec)
        assert validator.validate() is False


class TestExternalSpecValidation:
    def test_missing_uri_and_repo(self, tmp_path):
        from nb_wrangler.spec_validator import SpecValidator

        spec = {
            "image_spec_header": {},
            "repositories": {"myrepo": {"url": "https://example.com/repo.git"}},
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "r"},
                "nb-wrangler": {"repo": "r"},
            },
        }

        mocker = MagicMock()
        mocker._spec = spec
        mocker.header = {}
        mocker.inline_mamba_spec = None
        mocker.environment_spec = {}
        mocker.repositories = spec["repositories"]

        v = SpecValidator(mocker)
        result = v.validate()
        assert result is False

    def test_uri_cannot_mix_with_repo(self, tmp_path):
        from nb_wrangler.spec_validator import SpecValidator

        spec = {
            "image_spec_header": {},
            "repositories": {"myrepo": {"url": "https://example.com/r.git"}},
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "r"},
                "nb-wrangler": {"repo": "r"},
            },
        }

        mocker = MagicMock()
        mocker._spec = spec
        mocker.header = {}
        mocker.inline_mamba_spec = None
        mocker.environment_spec = {
            "uri": "http://example.com/env.yaml",
            "repo": "myrepo",
        }
        mocker.repositories = spec["repositories"]
        mocker.allowed_keywords = {}
        mocker.logger = MagicMock(error=MagicMock(return_value=False))
        mocker.config.dev = False

        v = SpecValidator(mocker)
        assert v.validate() is False


class TestNotebookSelectionsValidation:
    def test_missing_repo_in_selection(self, tmp_path):
        spec = {
            "image_spec_header": {
                "image_name": "t",
                "kernel_name": "k",
                "deployment_name": "w",
                "python_version": "3.12",
            },
            "repositories": {},
            "selected_notebooks": {
                "nb1": {"root_directory": ".", "include_subdirs": ["."]}
            },
            "system": {
                "spec_version": 2.3,
                "spi": {"repo": "r"},
                "nb-wrangler": {"repo": "r"},
                "date_updated": "x",
            },
        }

        validator, mock_sm = _make_bad_validator(tmp_path, spec)
        assert validator.validate() is False


class TestSystemValidation:
    def test_missing_spec_version(self, tmp_path):
        spec = {
            "image_spec_header": {
                "image_name": "t",
                "kernel_name": "k",
                "deployment_name": "w",
                "python_version": "3.12",
            },
            "repositories": {},
            "system": {"spi": {"repo": "r"}, "nb-wrangler": {"repo": "r"}},
        }

        validator, mock_sm = _make_bad_validator(tmp_path, spec)
        assert validator.validate() is False

    def test_invalid_spec_version(self, tmp_path):
        spec = {
            "image_spec_header": {
                "image_name": "t",
                "kernel_name": "k",
                "deployment_name": "w",
                "python_version": "3.12",
            },
            "repositories": {},
            "system": {
                "spec_version": "not-a-number",
                "spi": {"repo": "r"},
                "nb-wrangler": {"repo": "r"},
            },
        }

        validator, mock_sm = _make_bad_validator(tmp_path, spec)
        assert validator.validate() is False


class TestSpiSectionValidation:
    def test_missing_spi_section(self, tmp_path):
        spec = {
            "image_spec_header": {
                "image_name": "t",
                "kernel_name": "k",
                "deployment_name": "w",
                "python_version": "3.12",
            },
            "repositories": {},
            "system": {
                "spec_version": 2.3,
                "nb-wrangler": {"repo": "r"},
                "date_updated": "x",
            },
        }

        validator, mock_sm = _make_bad_validator(tmp_path, spec)
        assert validator.validate() is False
