import os
import pytest
from pathlib import Path
from unittest.mock import patch

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.wrangler import NotebookWrangler
from nb_wrangler.pantry import NbwPantry, NbwShelf

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
        # Patch NBW_PANTRY module constant
        with patch("nb_wrangler.pantry.NBW_PANTRY", pantry_dir):
            # Test NbwPantry initialization - should not crash
            pantry = NbwPantry()
            assert pantry.path == pantry_dir
            
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
        with patch("nb_wrangler.pantry.NBW_PANTRY", pantry_dir):
            # Should initialize without crashing
            wrangler = NotebookWrangler()
            assert wrangler.pantry.path == pantry_dir
    finally:
        os.chmod(pantry_dir, 0o700)
