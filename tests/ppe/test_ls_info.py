"""Tests for ppe env ls and ppe env info (Phase 4)."""

import json
from unittest.mock import patch

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


def _make_pantry(tmp_path, name="p1", with_shelves=None, writable=True):
    """Create a pantry with optional shelves."""
    pantry = tmp_path / name
    pantry.mkdir()
    for shelf_name in with_shelves or []:
        shelf = pantry / "shelves" / shelf_name
        archives = shelf / "archives"
        archives.mkdir(parents=True)
        (archives / f"env-{shelf_name}.tar").write_text("fake")
        (archives / "last-save.sha256").write_text("abc123\n")
    if not writable:
        import os

        os.chmod(pantry, 0o555)
    return pantry


def _make_live_env(tmp_path, name, nbw_root=None):
    """Create a fake live env directory."""
    root = nbw_root if nbw_root is not None else tmp_path
    env = root / "envs" / name
    env.mkdir(parents=True, exist_ok=True)
    return env


# ---------------------------------------------------------------------------
# ppe env ls
# ---------------------------------------------------------------------------


class TestLs:
    """Tests for ppe env ls."""

    def test_ls_lists_shelves(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            rc = main(["env", "ls"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "demo" in out
            assert "p1" in out

    def test_ls_marks_live_envs(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]),
            patch("nb_wrangler.ppe.config.NBW_ROOT", tmp_path),
        ):
            _make_live_env(tmp_path, "demo", nbw_root=tmp_path)
            rc = main(["env", "ls"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "demo" in out
            # The table should show a * marker for live envs
            assert "*" in out

    def test_ls_ro_column(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"], writable=False)

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            main(["env", "ls"])
            out = capsys.readouterr().out
            assert "r/o" in out

    def test_ls_all_shows_all_matches(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        p2 = _make_pantry(tmp_path, "p2", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1, p2]):
            rc = main(["env", "ls", "--all"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "p1" in out
            assert "p2" in out

    def test_ls_without_all_collapses(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        p2 = _make_pantry(tmp_path, "p2", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1, p2]):
            rc = main(["env", "ls"])
            assert rc == 0
            out = capsys.readouterr().out
            # Should show demo only once (first match)
            assert out.count("demo") <= 2  # once in table, once in header maybe

    def test_ls_shadowing_warning(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        p2 = _make_pantry(tmp_path, "p2", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1, p2]):
            rc = main(["env", "ls"])
            assert rc == 0
            err = capsys.readouterr().err
            assert "shadowed" in err.lower()

    def test_ls_json_format(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            rc = main(["env", "ls", "--format", "json"])
            assert rc == 0
            out = capsys.readouterr().out
            data = json.loads(out)
            assert "shelves" in data
            assert len(data["shelves"]) == 1
            assert data["shelves"][0]["name"] == "demo"

    def test_ls_pantry_filter(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        p2 = _make_pantry(tmp_path, "p2", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1, p2]):
            rc = main(["env", "ls", "--pantry", str(p2)])
            assert rc == 0
            out = capsys.readouterr().out
            assert "p2" in out
            # Should not show p1's shelf since we filtered to p2
            assert "p1" not in out

    def test_ls_pattern_filter(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo", "prod"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            rc = main(["env", "ls", "demo"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "demo" in out
            assert "prod" not in out

    def test_ls_glob_pattern(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo", "prod", "dev"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            rc = main(["env", "ls", "d*"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "demo" in out
            assert "dev" in out
            assert "prod" not in out


# ---------------------------------------------------------------------------
# ppe env info
# ---------------------------------------------------------------------------


class TestInfo:
    """Tests for ppe env info."""

    def test_info_table(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            rc = main(["env", "info", "demo"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "demo" in out
            assert "Pantry" in out
            assert "Save hash" in out

    def test_info_json(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            rc = main(["env", "info", "demo", "--format", "json"])
            assert rc == 0
            out = capsys.readouterr().out
            data = json.loads(out)
            assert data["name"] == "demo"
            assert len(data["shelves"]) == 1

    def test_info_no_match(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            rc = main(["env", "info", "nonexistent"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "no shelf" in err.lower()

    def test_info_multi_match_lists_all(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        p2 = _make_pantry(tmp_path, "p2", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1, p2]):
            rc = main(["env", "info", "demo"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "p1" in out
            assert "p2" in out

    def test_info_pantry_filter(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])
        p2 = _make_pantry(tmp_path, "p2", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1, p2]):
            rc = main(["env", "info", "demo", "--pantry", str(p2)])
            assert rc == 0
            out = capsys.readouterr().out
            assert "p2" in out
            assert "p1" not in out

    def test_info_live_env_detected(self, tmp_path, capsys):
        from nb_wrangler.ppe.cli import main

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]),
            patch("nb_wrangler.ppe.config.NBW_ROOT", tmp_path),
        ):
            _make_live_env(tmp_path, "demo", nbw_root=tmp_path)
            rc = main(["env", "info", "demo"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "Live env" in out


# ---------------------------------------------------------------------------
# Config methods
# ---------------------------------------------------------------------------


class TestConfigMethods:
    """Tests for list_shelves and list_live_envs config methods."""

    def test_list_shelves_returns_metadata(self, tmp_path, capsys):
        from nb_wrangler.ppe.config import PpeConfig

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            config = PpeConfig()
            shelves = config.list_shelves()
            assert len(shelves) == 1
            assert shelves[0]["name"] == "demo"
            assert shelves[0]["writable"] is True
            assert shelves[0]["save_hash"] == "abc123"

    def test_list_shelves_with_glob(self, tmp_path, capsys):
        from nb_wrangler.ppe.config import PpeConfig

        p1 = _make_pantry(tmp_path, "p1", with_shelves=["demo", "prod"])

        with patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", [p1]):
            config = PpeConfig()
            shelves = config.list_shelves(glob_expr="d*")
            assert len(shelves) == 1
            assert shelves[0]["name"] == "demo"

    def test_list_live_envs(self, tmp_path, capsys):
        from nb_wrangler.ppe.config import PpeConfig

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", []),
            patch("nb_wrangler.ppe.config.NBW_ROOT", tmp_path),
        ):
            _make_live_env(tmp_path, "demo", nbw_root=tmp_path)
            _make_live_env(tmp_path, "prod", nbw_root=tmp_path)
            config = PpeConfig()
            envs = config.list_live_envs()
            assert len(envs) == 2
            assert {e["name"] for e in envs} == {"demo", "prod"}

    def test_list_live_envs_no_dirs(self, tmp_path, capsys):
        from nb_wrangler.ppe.config import PpeConfig

        with (
            patch("nb_wrangler.ppe.config.NBW_PANTRY_DIRS", []),
            patch("nb_wrangler.ppe.config.NBW_ROOT", tmp_path),
        ):
            config = PpeConfig()
            envs = config.list_live_envs()
            assert len(envs) == 0
