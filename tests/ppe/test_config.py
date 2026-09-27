"""Tests for ppe config and read-only pantry detection (Phase 1)."""

import os
import pytest

from nb_wrangler.config import WranglerConfig, set_args_config


@pytest.fixture(autouse=True)
def _set_config(tmp_path):
    """Ensure a WranglerConfig is set for all tests."""
    set_args_config(
        WranglerConfig(
            workflows=[],
            spec_file="",
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
        )
    )


class TestIsWritable:
    """Tests for PpeConfig.is_writable()."""

    def test_writable_dir(self, tmp_path):
        from nb_wrangler.ppe.config import PpeConfig

        config = PpeConfig()
        d = tmp_path / "writable"
        d.mkdir()
        assert config.is_writable(d) is True

    def test_readonly_dir(self, tmp_path):
        from nb_wrangler.ppe.config import PpeConfig

        config = PpeConfig()
        d = tmp_path / "readonly"
        d.mkdir()
        os.chmod(d, 0o500)
        try:
            assert config.is_writable(d) is False
        finally:
            os.chmod(d, 0o700)

    def test_nonexistent_dir(self, tmp_path):
        from nb_wrangler.ppe.config import PpeConfig

        config = PpeConfig()
        assert config.is_writable(tmp_path / "does-not-exist") is False


class TestWritablePantries:
    """Tests for PpeConfig.writable_pantries()."""

    def test_returns_only_writable(self, tmp_path):
        from unittest.mock import patch
        from nb_wrangler.ppe.config import PpeConfig

        ro = tmp_path / "ro"
        rw = tmp_path / "rw"
        ro.mkdir()
        rw.mkdir()
        os.chmod(ro, 0o500)
        try:
            with patch(
                "nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [ro, rw, tmp_path / "gone"]
            ):
                config = PpeConfig()
                writable = config.writable_pantries()
                assert rw in writable
                assert ro not in writable
        finally:
            os.chmod(ro, 0o700)

    def test_first_writable(self, tmp_path):
        from unittest.mock import patch
        from nb_wrangler.ppe.config import PpeConfig

        ro = tmp_path / "ro"
        rw = tmp_path / "rw"
        ro.mkdir()
        rw.mkdir()
        os.chmod(ro, 0o500)
        try:
            with patch(
                "nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [ro, rw]
            ):
                config = PpeConfig()
                first = config.first_writable_pantry()
                assert first == rw
        finally:
            os.chmod(ro, 0o700)

    def test_all_readonly_returns_none(self, tmp_path):
        from unittest.mock import patch
        from nb_wrangler.ppe.config import PpeConfig

        ro = tmp_path / "ro"
        ro.mkdir()
        os.chmod(ro, 0o500)
        try:
            with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [ro]):
                config = PpeConfig()
                assert config.first_writable_pantry() is None
                assert config.writable_pantries() == []
        finally:
            os.chmod(ro, 0o700)


class TestTargetPantry:
    """Tests for PpeConfig.target_pantry()."""

    def test_forced_writable_path(self, tmp_path):
        from unittest.mock import patch
        from nb_wrangler.ppe.config import PpeConfig

        rw = tmp_path / "rw"
        rw.mkdir()
        with patch(
            "nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [rw]
        ):
            config = PpeConfig()
            assert config.target_pantry(rw) == rw

    def test_forced_readonly_path_returns_none(self, tmp_path, capsys):
        from unittest.mock import patch
        from nb_wrangler.ppe.config import PpeConfig

        ro = tmp_path / "ro"
        ro.mkdir()
        os.chmod(ro, 0o500)
        try:
            with patch(
                "nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [ro]
            ):
                config = PpeConfig()
                result = config.target_pantry(ro)
                assert result is None
        finally:
            os.chmod(ro, 0o700)

    def test_no_forced_uses_first_writable(self, tmp_path):
        from unittest.mock import patch
        from nb_wrangler.ppe.config import PpeConfig

        rw = tmp_path / "rw"
        rw.mkdir()
        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [rw]):
            config = PpeConfig()
            assert config.target_pantry() == rw

    def test_no_forced_all_readonly_returns_none(self, tmp_path):
        from unittest.mock import patch
        from nb_wrangler.ppe.config import PpeConfig

        ro = tmp_path / "ro"
        ro.mkdir()
        os.chmod(ro, 0o500)
        try:
            with patch(
                "nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [ro]
            ):
                config = PpeConfig()
                assert config.target_pantry() is None
        finally:
            os.chmod(ro, 0o700)