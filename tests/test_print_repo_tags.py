from pathlib import Path
from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.wrangler import NotebookWrangler


def test_print_repo_tags_without_prod(tmp_path):
    spec_file = Path(__file__).parent.parent / "specs/samples/tike-wrangler-k1.yaml"
    config = WranglerConfig(
        workflows=[],
        spec_file=str(spec_file),
        repos_dir=tmp_path / "repos",
        output_dir=tmp_path / "output",
        print_repo_tags=True,
        prod=False,
    )
    set_args_config(config)
    wrangler = NotebookWrangler()

    # Running without prod should return False
    assert wrangler._print_repo_tags() is False


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

    assert wrangler._print_repo_tags() is True

    captured = capsys.readouterr()
    stdout = captured.out

    assert "https://github.com/spacetelescope/tike_content main" in stdout
    assert "https://github.com/spacetelescope/mast_notebooks main" in stdout
