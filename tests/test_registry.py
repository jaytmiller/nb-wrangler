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
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        rm = _make_manager_with_mocks(tmp_path)
        rm._list_tags = MagicMock(return_value=["nbs_img1", "nbs_img2", "nbw_v1"])

        result = rm.list_specs("img")
        assert len(result) == 2
        for t in result:
            assert t.startswith("nbs_")

    def test_shorthand_with_colon(self, tmp_path):
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        rm = _make_manager_with_mocks(tmp_path)
        rm._list_tags = MagicMock(return_value=["nbs_img1", "nbs_img2"])

        result = rm.list_specs("morgagn:img")
        assert len(result) == 2


class TestCatSpec:
    def test_happy_path(self, tmp_path):
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
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        rm = _make_manager_with_mocks(tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        rm.env_manager.wrangler_run.return_value = mock_result

        result = rm.cat_spec("nbs_test")
        assert result is None


class TestParseShorthand:
    def test_bare_shorthand(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        registry, project, tag = rm._parse_shorthand("_40")
        assert registry == "ghcr.io"
        assert project == "spacetelescope/nb-wrangler-images"
        assert tag == "_40"

    def test_project_colon_tag(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        registry, project, tag = rm._parse_shorthand("myproject:latest")
        assert registry == "ghcr.io"
        assert project == "spacetelescope/myproject"
        assert tag == "latest"

    def test_org_project_colon_tag(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        registry, project, tag = rm._parse_shorthand("myorg/myproj:tag")
        assert registry == "ghcr.io"
        assert project == "myorg/myproj"
        assert tag == "tag"

    def test_registry_org_project_colon_tag(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        registry, project, tag = rm._parse_shorthand("ghcr.io/myorg/myproj:tag")
        assert registry == "ghcr.io"
        assert project == "myorg/myproj"
        assert tag == "tag"

    def test_docker_registry(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        registry, project, tag = rm._parse_shorthand("docker.io/myimg:v1")
        assert registry == "docker.io"
        assert project == "myimg"
        assert tag == "v1"


class TestMatchTags:
    def test_prefixed_match(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        tags = ["nbw_v1", "nbw_v2", "nbs_v1"]
        matches = rm._match_tags(tags, "v1", preferred_prefix="nbw_")
        assert matches == ["nbw_v1"]

    def test_fallback_to_direct_match(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        tags = ["custom_v1", "nbw_v2"]
        matches = rm._match_tags(tags, "*v1", preferred_prefix="nbw_")
        assert matches == ["custom_v1"]

    def test_no_prefix_matching(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        tags = ["nbs_a1", "nbs_a2", "nbw_a1"]
        matches = rm._match_tags(tags, "*a1")
        assert matches == ["nbs_a1", "nbw_a1"]

    def test_auto_glob(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        tags = ["nbs_img1", "nbs_img2", "nbw_img1"]
        matches = rm._match_tags(tags, "img", preferred_prefix="nbs_", auto_glob=True)
        assert matches == ["nbs_img1", "nbs_img2"]

    def test_already_prefixed_pattern(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        tags = ["nbs_img1", "nbs_img2"]
        matches = rm._match_tags(tags, "nbs_img*", preferred_prefix="nbs_")
        assert matches == ["nbs_img1", "nbs_img2"]

    def test_sorted_result(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        tags = ["nbs_z", "nbs_a", "nbs_m"]
        matches = rm._match_tags(tags, "*")
        assert matches == ["nbs_a", "nbs_m", "nbs_z"]


class TestNeedsTagLookup:
    def test_glob_pattern(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        assert rm._needs_tag_lookup("Roman*40", "Roman*40", "") is True

    def test_question_mark(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        assert rm._needs_tag_lookup("v?", "v?", "") is True

    def test_underscore_prefix(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        assert rm._needs_tag_lookup("_40", "_40", "") is True

    def test_shorthand_with_preferred_prefix(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        assert rm._needs_tag_lookup("v1", "v1", "nbw_") is True

    def test_literal_with_colon_and_no_prefix(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        assert rm._needs_tag_lookup("latest", "myproj:latest", "") is False

    def test_literal_with_colon_and_prefix(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        assert rm._needs_tag_lookup("latest", "myproj:latest", "nbw_") is False


class TestResolveImageHelpers:
    def test_glob_with_preferred_prefix(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        with patch.object(
            rm, "_list_tags", return_value=["nbw_RomanNexus_40", "nbw_v1"]
        ):
            result = rm.resolve_image("Roman*40", preferred_prefix="nbw_")
        assert result == "ghcr.io/spacetelescope/nb-wrangler-images:nbw_RomanNexus_40"

    def test_tag_lookup_failure_falls_back_to_literal(self, tmp_path):
        rm = _make_manager_with_mocks(tmp_path)
        with patch.object(rm, "_list_tags", side_effect=ConnectionError("no net")):
            result = rm.resolve_image("_v1")
        assert ":_v1" in result
