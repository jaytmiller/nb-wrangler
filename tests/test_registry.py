"""Tests for nb_wrangler/registry.py."""

from unittest.mock import MagicMock, patch

from nb_wrangler.config import WranglerConfig, set_args_config


def _make_manager_with_mocks(tmp_path):
    """Create a RegistryManager with a fake env_manager and logger."""
    from nb_wrangler.registry import RegistryManager

    set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
    rm = RegistryManager()
    rm.env_manager = MagicMock()
    rm.logger = MagicMock()
    return rm


class TestResolveImage:
    def test_empty_string(self):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[]))
        rm = RegistryManager()
        assert rm.resolve_image("") == ""

    def test_full_uri_passthrough_http(self):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[]))
        rm = RegistryManager()
        result = rm.resolve_image("http://localhost:5000/my/image:tag")
        assert result == "http://localhost:5000/my/image:tag"

    def test_full_uri_passthrough_https(self):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[]))
        rm = RegistryManager()
        result = rm.resolve_image("https://docker.io/myimg:v1")
        assert "docker.io/myimg" in result or result == "https://docker.io/myimg:v1"

    def test_hex_suffix_uses_default_project(self, tmp_path):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        rm = _make_manager_with_mocks(tmp_path)

        with patch.object(rm, "_list_tags", return_value=["nbs_test_v1", "nbw_v1"]):
            result = rm.resolve_image("_v1")

        assert "ghcr.io/spacetelescope/nb-wrangler" in result
        assert "nbw_v1" in result

    def test_with_colon_project_tag_split(self):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[]))
        rm = RegistryManager()
        result = rm.resolve_image("myproject:latest")
        assert ":" in result


class TestListSpecs:
    def test_empty_shortcut(self):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[]))
        rm = RegistryManager()
        assert rm.list_specs("") == []

    def test_shorthand_without_colon_adds_nbs_prefix(self, tmp_path):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        rm = _make_manager_with_mocks(tmp_path)
        rm._list_tags = MagicMock(return_value=["nbs_img1", "nbs_img2", "nbw_v1"])

        result = rm.list_specs("img")
        assert len(result) == 2
        for t in result:
            assert t.startswith("nbs_")

    def test_shorthand_with_colon(self, tmp_path):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        rm = _make_manager_with_mocks(tmp_path)
        rm._list_tags = MagicMock(return_value=["nbs_img1", "nbs_img2"])

        result = rm.list_specs("morgagn:img")
        assert len(result) == 2


class TestCatSpec:
    def test_happy_path(self, tmp_path):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        rm = _make_manager_with_mocks(tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "container123"
        rm.env_manager.wrangler_run.return_value = mock_result
        rm._extract_file = MagicMock(return_value="spec: content")

        result = rm.cat_spec("nbs_test")
        assert result == "spec: content"

        # Verify container is cleaned up (called with 'rm')
        calls = [c[0] for c in rm.env_manager.wrangler_run.call_args_list]
        assert any("rm" in str(c) for c in calls)

    def test_create_failure_returns_none(self, tmp_path):
        from nb_wrangler.registry import RegistryManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        rm = _make_manager_with_mocks(tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        rm.env_manager.wrangler_run.return_value = mock_result

        result = rm.cat_spec("nbs_test")
        assert result is None
