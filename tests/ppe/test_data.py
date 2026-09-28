"""Tests for ppe data ls (Phase 9a)."""

import contextlib
from unittest.mock import patch

import pytest

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.utils import yaml_dumps


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


def _specs_dir(tmp_path, name):
    """Return the .ppe-spec.yaml path for *name* and ensure parent exists."""
    spec_path = tmp_path / "envs" / name / ".ppe-spec.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    return spec_path


def _write_spec(tmp_path, name, extra=None):
    """Write a minimal ppe spec for *name*."""
    spec_path = _specs_dir(tmp_path, name)
    spec = {"name": name, "channels": ["conda-forge"], "dependencies": []}
    if extra:
        spec.update(extra)
    spec_path.write_text(yaml_dumps(spec))
    return spec_path


def _shelf_archives_dir(tmp_path, name):
    """Return the shelf archives/ dir for *name* and ensure it exists."""
    archive_dir = tmp_path / "pantry" / "shelves" / name / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir


def _make_archive(archive_dir, name, size=1024):
    """Create a data-* archive file with *size* bytes of placeholder content."""
    fpath = archive_dir / name
    fpath.write_bytes(b"x" * size)
    return fpath


@contextlib.contextmanager
def _patch_root_and_pantry(tmp_path):
    """Patch NBW_ROOT and NBW_PANTRY_DIRS so PpeConfig points at tmp_path."""
    with (
        patch("nb_wrangler.ppe.config.NBW_ROOT", tmp_path),
        patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [tmp_path / "pantry"]),
    ):
        yield


# ---------------------------------------------------------------------------
# data ls
# ---------------------------------------------------------------------------


class TestDataLs:
    """Tests for ppe data ls."""

    def test_ls_table_default(self, tmp_path, capsys):
        """Default output is a two-column ARCHIVE/SIZE table."""
        from nb_wrangler.ppe.cli import main

        _write_spec(tmp_path, "demo")
        archive_dir = _shelf_archives_dir(tmp_path, "demo")
        _make_archive(archive_dir, "data-roman.tar.gz", 2048)
        _make_archive(archive_dir, "data-stips.tar.gz", 512)

        with _patch_root_and_pantry(tmp_path):
            rc = main(["data", "ls", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "ARCHIVE" in out and "SIZE" in out
        assert "data-roman.tar.gz" in out
        assert "data-stips.tar.gz" in out
        assert "2048" in out and "512" in out

    def test_ls_table_sorted(self, tmp_path, capsys):
        """Archives are listed in sorted order."""
        from nb_wrangler.ppe.cli import main

        _write_spec(tmp_path, "demo")
        archive_dir = _shelf_archives_dir(tmp_path, "demo")
        _make_archive(archive_dir, "data-zeta.tar.gz")
        _make_archive(archive_dir, "data-alpha.tar.gz")

        with _patch_root_and_pantry(tmp_path):
            rc = main(["data", "ls", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        lines = out.splitlines()
        alpha_pos = next(i for i, l in enumerate(lines) if "data-alpha" in l)
        zeta_pos = next(i for i, l in enumerate(lines) if "data-zeta" in l)
        assert alpha_pos < zeta_pos

    def test_ls_json(self, tmp_path, capsys):
        """--format json prints a JSON object with name + archives list."""
        from nb_wrangler.ppe.cli import main

        _write_spec(tmp_path, "demo")
        archive_dir = _shelf_archives_dir(tmp_path, "demo")
        _make_archive(archive_dir, "data-alpha.tar.gz")

        with _patch_root_and_pantry(tmp_path):
            rc = main(["data", "ls", "demo", "--format", "json"])
        assert rc == 0
        out = capsys.readouterr().out
        assert '"name": "demo"' in out
        assert '"archives"' in out
        assert "data-alpha.tar.gz" in out

    def test_ls_empty_no_message(self, tmp_path, capsys):
        """ls with no archives prints a helpful message and exits 0."""
        from nb_wrangler.ppe.cli import main

        _write_spec(tmp_path, "demo")
        _shelf_archives_dir(tmp_path, "demo")  # empty archives/ dir

        with _patch_root_and_pantry(tmp_path):
            rc = main(["data", "ls", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "no data archives defined for 'demo'" in out

    def test_ls_no_shelf_no_crash(self, tmp_path, capsys):
        """ls on a name with no shelf does not crash."""
        from nb_wrangler.ppe.cli import main

        _write_spec(tmp_path, "ghost")
        # no shelf created

        with _patch_root_and_pantry(tmp_path):
            rc = main(["data", "ls", "ghost"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "no data archives defined for 'ghost'" in out

    def test_ls_missing_spec_no_crash(self, tmp_path, capsys):
        """ls on a name with no spec file does not crash."""
        from nb_wrangler.ppe.cli import main

        with _patch_root_and_pantry(tmp_path):
            rc = main(["data", "ls", "ghost"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "no data archives defined for 'ghost'" in out

    def test_ls_excludes_non_data_files(self, tmp_path, capsys):
        """Only data-* files appear in the listing; last-save.sha256 is excluded."""
        from nb_wrangler.ppe.cli import main

        _write_spec(tmp_path, "demo")
        archive_dir = _shelf_archives_dir(tmp_path, "demo")
        _make_archive(archive_dir, "data-alpha.tar.gz")
        (archive_dir / "last-save.sha256").write_text("abc123")
        (archive_dir / "env-demo.tar.gz").write_bytes(b"y" * 100)

        with _patch_root_and_pantry(tmp_path):
            rc = main(["data", "ls", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "data-alpha.tar.gz" in out
        assert "last-save.sha256" not in out
        assert "env-demo.tar.gz" not in out
