"""Tests for the --quiet-downloads setting which reduces download progress
output for robust_get based downloads while keeping failures debuggable.
"""

from pathlib import Path
from unittest.mock import patch

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.pantry import NbwShelf
from nb_wrangler.utils import DataDownloadError


def _setup_config(tmp_path: Path, **overrides) -> None:
    config = WranglerConfig(
        workflows=[],
        spec_file="",
        repos_dir=tmp_path / "repos",
        output_dir=tmp_path / "output",
        **overrides,
    )
    set_args_config(config)


def _shelf(tmp_path: Path) -> NbwShelf:
    return NbwShelf(tmp_path / "shelves" / "test-shelf")


ARCHIVE_TUPLE = ("a", "b", "https://example.com/data-f.tar.gz", "c", "d")


def test_download_data_reduced_output_when_enabled(tmp_path):
    _setup_config(tmp_path, quiet_downloads=True)
    shelf = _shelf(tmp_path)
    with patch("nb_wrangler.utils.robust_get") as mock_get:
        result = shelf.download_data(ARCHIVE_TUPLE)
    assert result is True
    assert mock_get.called
    assert mock_get.call_args.kwargs["reduced_output"] is True


def test_download_data_default_behavior_preserved(tmp_path):
    _setup_config(tmp_path)  # quiet_downloads defaults to False
    shelf = _shelf(tmp_path)
    with patch("nb_wrangler.utils.robust_get") as mock_get:
        result = shelf.download_data(ARCHIVE_TUPLE)
    assert result is True
    assert mock_get.call_args.kwargs["reduced_output"] is False


def test_download_data_failure_returns_false_and_records_error(tmp_path):
    _setup_config(tmp_path, quiet_downloads=True)
    shelf = _shelf(tmp_path)
    url = ARCHIVE_TUPLE[2]
    exc = DataDownloadError(f"Failed downloading '{url}'.\nERROR 404: Not Found")
    with patch("nb_wrangler.utils.robust_get", side_effect=exc):
        result = shelf.download_data(ARCHIVE_TUPLE)
    assert result is False
    assert any(url in msg for msg in shelf.logger.errors)
