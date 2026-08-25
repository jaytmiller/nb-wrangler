"""Tests for --print-repo-tags using git ls-remote (no clone required)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.wrangler import NotebookWrangler


def _make_result(returncode=0, stdout=""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    return result


def _ls_remote_stdout(tags):
    """Build fake ``git ls-remote --tags`` output lines for the given tag names."""
    lines = []
    for tag in tags:
        lines.append(f"abc123def456789\trefs/tags/{tag}")
        # Annotated tags produce a second line with ^{}.
        lines.append(f"abc123def456789\trefs/tags/{tag}^{{}}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prod mode with ``main`` refs (tike-wrangler-k1.yaml)
# ---------------------------------------------------------------------------


def test_print_repo_tags_with_prod(tmp_path, capsys):
    spec_file = Path(__file__).parent.parent / "specs/samples/tike-wrangler-k1.yaml"
    config = WranglerConfig(
        workflows=[],
        spec_file=str(spec_file),
        repos_dir=tmp_path / "repos",
        output_dir=tmp_path / "output",
        print_repo_tags=True,
        prod=True,
    )
    set_args_config(config)
    wrangler = NotebookWrangler()

    # In prod mode both repos have ref "main"; no x.y.z tags match, so "main" is returned.
    fake_ls_output = _ls_remote_stdout(["main"])
    with patch.object(
        wrangler.env_manager,
        "wrangler_run",
        return_value=_make_result(stdout=fake_ls_output),
    ):
        assert wrangler._print_repo_tags() is True

    captured = capsys.readouterr()
    stdout = captured.out

    assert "https://github.com/spacetelescope/tike_content main" in stdout
    assert "https://github.com/spacetelescope/mast_notebooks main" in stdout


# ---------------------------------------------------------------------------
# Version-prefix ref (``2026.2``) resolved to highest patch tag
# ---------------------------------------------------------------------------


def test_print_repo_tags_version_prefix(tmp_path, capsys):
    """If the spec ref is ``2026.2``, the highest ``2026.2.z`` tag is returned."""
    spec_file = Path(__file__).parent.parent / "specs/samples/RomanNexus-2026.2.yaml"
    config = WranglerConfig(
        workflows=[],
        spec_file=str(spec_file),
        repos_dir=tmp_path / "repos",
        output_dir=tmp_path / "output",
        print_repo_tags=True,
        prod=True,
    )
    set_args_config(config)
    wrangler = NotebookWrangler()

    # The roman_notebooks repo has ref "2026.2" in prod mode.
    fake_ls_output = _ls_remote_stdout(["2026.2.0", "2026.2.1", "2026.2.2", "main"])
    with patch.object(
        wrangler.env_manager,
        "wrangler_run",
        return_value=_make_result(stdout=fake_ls_output),
    ):
        assert wrangler._print_repo_tags() is True

    captured = capsys.readouterr()
    stdout = captured.out

    assert "https://github.com/spacetelescope/roman_notebooks.git 2026.2.2" in stdout


# ---------------------------------------------------------------------------
# Numeric z with different digit counts → greatest z wins
# ---------------------------------------------------------------------------


def test_print_repo_tags_greatest_numeric_z(tmp_path, capsys):
    """``2026.2.10`` should be selected over ``2026.2.2`` (z=10 > z=2)."""
    spec_file = Path(__file__).parent.parent / "specs/samples/RomanNexus-2026.2.yaml"
    config = WranglerConfig(
        workflows=[],
        spec_file=str(spec_file),
        repos_dir=tmp_path / "repos",
        output_dir=tmp_path / "output",
        print_repo_tags=True,
        prod=True,
    )
    set_args_config(config)
    wrangler = NotebookWrangler()

    fake_ls_output = _ls_remote_stdout(["2026.2.2", "2026.2.10"])
    with patch.object(
        wrangler.env_manager,
        "wrangler_run",
        return_value=_make_result(stdout=fake_ls_output),
    ):
        assert wrangler._print_repo_tags() is True

    captured = capsys.readouterr()
    stdout = captured.out

    assert "https://github.com/spacetelescope/roman_notebooks.git 2026.2.10" in stdout


# ---------------------------------------------------------------------------
# No matching tags → ref returned as-is
# ---------------------------------------------------------------------------


def test_print_repo_tags_no_matching_tags(tmp_path, capsys):
    """When ls-remote returns only ``main``, the ref ``main`` is returned as-is."""
    spec_file = Path(__file__).parent.parent / "specs/samples/RomanNexus-2026.2.yaml"
    config = WranglerConfig(
        workflows=[],
        spec_file=str(spec_file),
        repos_dir=tmp_path / "repos",
        output_dir=tmp_path / "output",
        print_repo_tags=True,
        prod=True,
    )
    set_args_config(config)
    wrangler = NotebookWrangler()

    # Use a ref "main" in the spec — no x.y.z tags exist, so "main" is returned.
    fake_ls_output = _ls_remote_stdout(["main"])
    with patch.object(
        wrangler.env_manager,
        "wrangler_run",
        return_value=_make_result(stdout=fake_ls_output),
    ):
        assert wrangler._print_repo_tags() is True

    captured = capsys.readouterr()
    stdout = captured.out

    # roman_notebooks has ref "2026.2" in the spec; no x.y.z tags found, so "2026.2" is returned as-is.
    assert "https://github.com/spacetelescope/roman_notebooks.git 2026.2" in stdout
    # SPI repo has ref "main"; no x.z.y tags found, so "main" is returned as-is.
    assert (
        "https://github.com/spacetelescope/science-platform-images.git main" in stdout
    )
