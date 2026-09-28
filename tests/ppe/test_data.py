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


# ---------------------------------------------------------------------------
# data download (Phase 9b)
# ---------------------------------------------------------------------------


class TestDataDownload:
    """Tests for ppe data download — flag forwarding to data_manager."""

    def test_download_default(self, tmp_path, capsys):
        """Default download forwards name plus default select/validate."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.download_data") as mock_dl,
        ):
            mock_dl.return_value = True
            rc = main(["data", "download", "demo"])
        assert rc == 0
        mock_dl.assert_called_once_with("demo", select=".*", validate=True)

    def test_download_with_select(self, tmp_path, capsys):
        """--select REGEX is forwarded to data_manager.download_data."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.download_data") as mock_dl,
        ):
            mock_dl.return_value = True
            rc = main(["data", "download", "demo", "--select", "roman_.*"])
        assert rc == 0
        mock_dl.assert_called_once_with("demo", select="roman_.*", validate=True)

    def test_download_no_validate(self, tmp_path, capsys):
        """--no-validate flips validate to False when forwarded."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.download_data") as mock_dl,
        ):
            mock_dl.return_value = True
            rc = main(["data", "download", "demo", "--no-validate"])
        assert rc == 0
        mock_dl.assert_called_once_with("demo", select=".*", validate=False)

    def test_download_failure_exits_nonzero(self, tmp_path, capsys):
        """A failing download returns exit code 1 (not 2/not-implemented)."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.download_data") as mock_dl,
        ):
            mock_dl.return_value = False
            rc = main(["data", "download", "demo"])
        assert rc == 1


# ---------------------------------------------------------------------------
# data unpack (Phase 9b)
# ---------------------------------------------------------------------------


class TestDataUnpack:
    """Tests for ppe data unpack — flag forwarding to data_manager."""

    def test_unpack_default_symlinks(self, tmp_path, capsys):
        """Default unpack forwards default symlinks and no-unpack-existing."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.unpack_data") as mock_unp,
        ):
            mock_unp.return_value = True
            rc = main(["data", "unpack", "demo"])
        assert rc == 0
        mock_unp.assert_called_once_with(
            "demo", symlinks=True, no_unpack_existing=False
        )

    def test_unpack_no_symlinks(self, tmp_path, capsys):
        """--no-symlinks forwards symlinks=False."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.unpack_data") as mock_unp,
        ):
            mock_unp.return_value = True
            rc = main(["data", "unpack", "demo", "--no-symlinks"])
        assert rc == 0
        mock_unp.assert_called_once_with(
            "demo", symlinks=False, no_unpack_existing=False
        )

    def test_unpack_symlinks_explicit(self, tmp_path, capsys):
        """--symlinks forwards symlinks=True (explicit)."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.unpack_data") as mock_unp,
        ):
            mock_unp.return_value = True
            rc = main(["data", "unpack", "demo", "--symlinks"])
        assert rc == 0
        mock_unp.assert_called_once_with(
            "demo", symlinks=True, no_unpack_existing=False
        )

    def test_unpack_no_unpack_existing(self, tmp_path, capsys):
        """--no-unpack-existing forwards no_unpack_existing=True."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.unpack_data") as mock_unp,
        ):
            mock_unp.return_value = True
            rc = main(["data", "unpack", "demo", "--no-unpack-existing"])
        assert rc == 0
        mock_unp.assert_called_once_with("demo", symlinks=True, no_unpack_existing=True)

    def test_unpack_failure_exits_nonzero(self, tmp_path, capsys):
        """A failing unpack returns exit code 1 (not 2/not-implemented)."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.unpack_data") as mock_unp,
        ):
            mock_unp.return_value = False
            rc = main(["data", "unpack", "demo"])
        assert rc == 1


# ---------------------------------------------------------------------------
# data pack (Phase 9c)
# ---------------------------------------------------------------------------


class TestDataPack:
    """Tests for ppe data pack — flag forwarding to data_manager."""

    def test_pack_forwards_name(self, tmp_path):
        """ppe data pack forwards name to data_manager.pack_data."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.pack_data") as mock_pack,
        ):
            mock_pack.return_value = True
            rc = main(["data", "pack", "demo"])
        assert rc == 0
        mock_pack.assert_called_once_with("demo")

    def test_pack_failure_exits_nonzero(self, tmp_path):
        """A failing pack returns exit code 1 (not 2/not-implemented)."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.pack_data") as mock_pack,
        ):
            mock_pack.return_value = False
            rc = main(["data", "pack", "demo"])
        assert rc == 1


# ---------------------------------------------------------------------------
# data clean (Phase 9c)
# ---------------------------------------------------------------------------


class TestDataClean:
    """Tests for ppe data clean — mode forwarding to data_manager."""

    def test_clean_default_mode_both(self, tmp_path):
        """ppe data clean with no mode defaults to 'both'."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.delete_data") as mock_del,
        ):
            mock_del.return_value = True
            rc = main(["data", "clean", "demo"])
        assert rc == 0
        mock_del.assert_called_once_with("demo", mode="both")

    def test_clean_archived(self, tmp_path):
        """clean archived forwards mode='archived'."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.delete_data") as mock_del,
        ):
            mock_del.return_value = True
            rc = main(["data", "clean", "demo", "archived"])
        assert rc == 0
        mock_del.assert_called_once_with("demo", mode="archived")

    def test_clean_unpacked(self, tmp_path):
        """clean unpacked forwards mode='unpacked'."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.delete_data") as mock_del,
        ):
            mock_del.return_value = True
            rc = main(["data", "clean", "demo", "unpacked"])
        assert rc == 0
        mock_del.assert_called_once_with("demo", mode="unpacked")

    def test_clean_both_explicit(self, tmp_path):
        """clean both forwards mode='both' explicitly."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.delete_data") as mock_del,
        ):
            mock_del.return_value = True
            rc = main(["data", "clean", "demo", "both"])
        assert rc == 0
        mock_del.assert_called_once_with("demo", mode="both")

    def test_clean_failure_exits_nonzero(self, tmp_path):
        """A failing clean returns exit code 1 (not 2/not-implemented)."""
        from nb_wrangler.ppe.cli import main

        with (
            _patch_root_and_pantry(tmp_path),
            patch("nb_wrangler.ppe.cli.data_manager.delete_data") as mock_del,
        ):
            mock_del.return_value = False
            rc = main(["data", "clean", "demo"])
        assert rc == 1
