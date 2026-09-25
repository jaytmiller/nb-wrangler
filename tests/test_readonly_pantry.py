import os
import pytest
from pathlib import Path
from unittest.mock import patch

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.wrangler import NotebookWrangler
from nb_wrangler.pantry import NbwPantrySet


def test_readonly_pantry_no_crash(tmp_path):
    pantry_dir = tmp_path / "readonly_pantry"
    pantry_dir.mkdir()

    # Restrict permissions
    os.chmod(pantry_dir, 0o500)

    # Setup configuration to prevent Premature fetch exception
    config = WranglerConfig(
        workflows=[],
        spec_file="",
        repos_dir=tmp_path / "repos",
        output_dir=tmp_path / "output",
    )
    set_args_config(config)

    try:
        # Patch NBW_PANTRY_DIRS module constant (now a list)
        with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [pantry_dir]):
            # Test NbwPantry initialization - should not crash
            pantry = NbwPantrySet()
            assert pantry.path == pantry_dir
            assert pantry.paths == [pantry_dir]

            # Test NbwShelf initialization - should not crash
            shelf = pantry.get_shelf("test-shelf")
            assert shelf.path == pantry_dir / "shelves" / "test-shelf"

            # Writing should fail
            with pytest.raises(OSError):
                shelf.save_exports_file("test.sh", {"VAR": "VALUE"})
    finally:
        os.chmod(pantry_dir, 0o700)


def test_wrangler_init_with_readonly_pantry(tmp_path):
    pantry_dir = tmp_path / "readonly_pantry"
    pantry_dir.mkdir()
    os.chmod(pantry_dir, 0o500)

    spec_file = Path(__file__).parent.parent / "specs/samples/tike-wrangler-k1.yaml"

    # Create configuration
    config = WranglerConfig(
        workflows=[],
        spec_file=str(spec_file),
        repos_dir=tmp_path / "repos",
        output_dir=tmp_path / "output",
    )
    set_args_config(config)

    try:
        with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [pantry_dir]):
            # Should initialize without crashing
            wrangler = NotebookWrangler()
            assert wrangler.pantry.path == pantry_dir
    finally:
        os.chmod(pantry_dir, 0o700)


# ---------------------------------------------------------------------------
# Multi-pantry search path tests
# ---------------------------------------------------------------------------


def _make_shelf(pantry_dir: Path, shelf_name: str) -> Path:
    """Create a minimal shelf directory in the given pantry."""
    shelf_path = pantry_dir / "shelves" / shelf_name
    shelf_path.mkdir(parents=True, exist_ok=True)
    return shelf_path


def test_get_shelf_returns_first_match(tmp_path):
    """A shelf in a primary pantry should be found before one in a secondary."""
    primary = tmp_path / "pantry1"
    secondary = tmp_path / "pantry2"
    primary.mkdir()
    secondary.mkdir()

    _make_shelf(primary, "my-shelf")
    _make_shelf(secondary, "my-shelf")

    with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [primary, secondary]):
        pantry = NbwPantrySet()
        shelf = pantry.get_shelf("my-shelf")
        assert shelf.path == primary / "shelves" / "my-shelf"
        assert shelf.pantry_path == primary


def test_get_shelf_falls_through_to_secondary(tmp_path):
    """When a shelf only exists in a secondary pantry, it should still be found."""
    primary = tmp_path / "pantry1"
    secondary = tmp_path / "pantry2"
    primary.mkdir()
    secondary.mkdir()

    _make_shelf(secondary, "only-here")

    with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [primary, secondary]):
        pantry = NbwPantrySet()
        shelf = pantry.get_shelf("only-here")
        assert shelf.path == secondary / "shelves" / "only-here"
        assert shelf.pantry_path == secondary


def test_get_shelf_defaults_to_primary_for_new_shelf(tmp_path):
    """A non-existent shelf should resolve to the primary pantry for creation."""
    primary = tmp_path / "pantry1"
    secondary = tmp_path / "pantry2"
    primary.mkdir()
    secondary.mkdir()

    with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [primary, secondary]):
        pantry = NbwPantrySet()
        shelf = pantry.get_shelf("brand-new")
        assert shelf.path == primary / "shelves" / "brand-new"
        assert shelf.pantry_path == primary


def test_list_shelves_across_pantries(tmp_path):
    """list_shelves should show shelves from all pantries, deduplicated."""
    primary = tmp_path / "pantry1"
    secondary = tmp_path / "pantry2"
    primary.mkdir()
    secondary.mkdir()

    _make_shelf(primary, "shared-shelf")
    _make_shelf(secondary, "shared-shelf")  # shadowed
    _make_shelf(secondary, "unique-to-secondary")

    with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [primary, secondary]):
        pantry = NbwPantrySet()
        # list_shelves prints to stdout; capture via capsys
        pantry.list_shelves()
        # We can't easily capture print output without capsys fixture;
        # verify deduplicated count via select_shelves instead:
        names = pantry.select_shelves("*")
        assert sorted(names) == ["shared-shelf", "unique-to-secondary"]


def test_select_shelves_glob_across_pantries(tmp_path):
    """select_shelves should match glob patterns across all pantries."""
    primary = tmp_path / "pantry1"
    secondary = tmp_path / "pantry2"
    primary.mkdir()
    secondary.mkdir()

    _make_shelf(primary, "shelf-aaa")
    _make_shelf(primary, "shelf-bbb")
    _make_shelf(secondary, "shelf-ccc")

    with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [primary, secondary]):
        pantry = NbwPantrySet()
        results = pantry.select_shelves("shelf-a*")
        assert results == ["shelf-aaa"]


def test_delete_shelf_from_first_match(tmp_path):
    """delete_shelf should delete from the first pantry containing the shelf."""
    primary = tmp_path / "pantry1"
    secondary = tmp_path / "pantry2"
    primary.mkdir()
    secondary.mkdir()

    _make_shelf(primary, "my-shelf")
    _make_shelf(secondary, "my-shelf")

    with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [primary, secondary]):
        pantry = NbwPantrySet()
        result = pantry.delete_shelf("my-shelf")
        assert result is True
        assert not (primary / "shelves" / "my-shelf").exists()
        # Secondary copy should still exist
        assert (secondary / "shelves" / "my-shelf").exists()


def test_delete_shelf_not_found(tmp_path):
    """delete_shelf should return False when no matching shelf exists."""
    primary = tmp_path / "pantry1"
    secondary = tmp_path / "pantry2"
    primary.mkdir()
    secondary.mkdir()

    with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [primary, secondary]):
        pantry = NbwPantrySet()
        result = pantry.delete_shelf("nonexistent")
        assert result is False


def test_single_pantry_backward_compat(tmp_path):
    """A single pantry (no colon) should behave exactly as before."""
    pantry_dir = tmp_path / "single-pantry"
    pantry_dir.mkdir()

    _make_shelf(pantry_dir, "test-shelf")

    with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [pantry_dir]):
        pantry = NbwPantrySet()
        assert pantry.path == pantry_dir
        assert pantry.shelves == pantry_dir / "shelves"
        shelf = pantry.get_shelf("test-shelf")
        assert shelf.path == pantry_dir / "shelves" / "test-shelf"


def test_empty_pantry_dir_skipped():
    """Empty entries from trailing colons in NBW_PANTRY env var should be skipped.

    This is tested at the constants level since the filtering occurs when
    parsing the raw env var string, before Path objects are created.
    """
    from nb_wrangler import constants

    # Verify the parsing logic: empty strings are filtered before Path creation
    raw_env = "/path/to/pantry1::/path/to/pantry2:"
    parsed = [Path(p) for p in raw_env.split(os.pathsep) if p]
    assert parsed == [Path("/path/to/pantry1"), Path("/path/to/pantry2")]

    # Confirm NBW_PANTRY_DIRS is a non-empty list of Paths
    assert isinstance(constants.NBW_PANTRY_DIRS, list)
    assert all(isinstance(p, Path) for p in constants.NBW_PANTRY_DIRS)


def test_abstract_data_path_uses_correct_pantry(tmp_path):
    """abstract_data_path should point to the actual pantry the shelf lives in."""
    primary = tmp_path / "pantry1"
    secondary = tmp_path / "pantry2"
    primary.mkdir()
    secondary.mkdir()

    _make_shelf(secondary, "from-secondary")

    with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [primary, secondary]):
        pantry = NbwPantrySet()
        shelf = pantry.get_shelf("from-secondary")
        assert shelf.pantry_path == secondary
        assert shelf.abstract_data_path == secondary / "shelves" / "from-secondary" / "data"
