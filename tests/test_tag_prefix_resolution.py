"""Tests for prefix-tag resolution during repository checkout."""

from unittest.mock import MagicMock, patch
from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.utils import select_highest_patch_tag


def _make_result(returncode=0, stdout=""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    return result


def fake_git_output(cmd):
    """Return fake git command output based on the command string."""
    if cmd == "git tag -l":
        return "main\nv1.2.3\n2026.2.0\n2026.2.1\n2026.2.2"
    if isinstance(cmd, str) and cmd.startswith("git rev-parse ") and "2026.2.2" in cmd:
        return "aabbccdd11223344556677889900aabbccddeeff"
    if cmd == "git symbolic-ref refs/remotes/origin/HEAD":
        return "refs/remotes/origin/main"
    if cmd in ("git fetch", "git fetch --tags"):
        return ""
    if isinstance(cmd, str) and cmd.startswith("git checkout"):
        return ""
    return ""


class MockLogger:

    def debug(self, *args):
        pass

    def info(self, *args):
        pass

    def warning(self, *args):
        pass

    def error(self, *args):
        pass

    def exception(self, exc, msg):
        return None


class MockConfig:

    overwrite_local_changes = False
    stash_local_changes = False
    use_dirty_repos = False


def _make_repo_manager(repos_dir):
    from nb_wrangler.repository import RepositoryManager

    rm = RepositoryManager(repos_dir=repos_dir)
    mock_env = MagicMock()
    mock_env.wrangler_run.side_effect = lambda *a, **k: _make_result(
        stdout=fake_git_output(a[0])
    )
    mock_env.handle_result.side_effect = lambda result, *args: True
    rm.env_manager = mock_env
    rm.logger = MockLogger()
    if not hasattr(rm, "_config") or rm._config is None:
        rm._config = MockConfig()
    return rm


class TestSetupRemoteRepoTagPrefixResolution:

    def test_existing_repo_floating_mode_resolves_tag_prefix(self, tmp_path):
        set_args_config(
            WranglerConfig(
                workflows=[],
                spec_file="",
                repos_dir=tmp_path / "repos",
                output_dir=tmp_path / "output",
            )
        )
        rm = _make_repo_manager(tmp_path / "repos")
        test_repo_dir = tmp_path / "repos" / "test_repo"
        test_repo_dir.mkdir(parents=True)
        (test_repo_dir / ".git").mkdir()
        checkout_count = [0]

        def fake_checkout(repo_name, ref):
            checkout_count[0] += 1
            # First call is direct checkout of '2026.2' => fail; second call is resolved SHA => success
            if checkout_count[0] == 1:
                return False
            return True

        with patch.object(rm, "git_checkout", side_effect=fake_checkout):
            result = rm._setup_remote_repo(
                "https://github.com/example/test_repo",
                floating_mode=True,
                ref="2026.2",
            )
        assert result is not None
        assert result.name == "test_repo"

    def test_existing_repo_locked_mode_skips_resolution(self, tmp_path):
        set_args_config(
            WranglerConfig(
                workflows=[],
                spec_file="",
                repos_dir=tmp_path / "repos",
                output_dir=tmp_path / "output",
            )
        )
        rm = _make_repo_manager(tmp_path / "repos")
        test_repo_dir = tmp_path / "repos" / "test_locked"
        test_repo_dir.mkdir(parents=True)
        (test_repo_dir / ".git").mkdir()
        with patch.object(
            rm,
            "run",
            side_effect=lambda *a, **k: _make_result(stdout=fake_git_output(a[0])),
        ):
            result = rm._setup_remote_repo(
                "https://github.com/example/test_repo2",
                floating_mode=False,
                ref="2026.2",
            )
        assert result is not None


class TestFetchSortedTagsOrdering:

    def test_tags_sorted_lexicographic_descending(self, tmp_path):
        set_args_config(
            WranglerConfig(
                workflows=[],
                spec_file="",
                repos_dir=tmp_path / "repos",
                output_dir=tmp_path / "output",
            )
        )
        rm = _make_repo_manager(tmp_path / "repos")
        test_repo_dir = tmp_path / "repos" / "order_test"
        test_repo_dir.mkdir(parents=True)
        (test_repo_dir / ".git").mkdir()

        def fake_run(*a, **k):
            # First call is git fetch --tags => empty; second is git tag -l => sorted list
            cmd = a[0] if a else ""
            if "fetch" in cmd:
                return _make_result(stdout="")
            return _make_result(stdout="2026.2.0\n2026.2.10\n2026.2.1\n2026.2.2\nmain")

        with patch.object(rm, "run", side_effect=fake_run):
            tags = rm.fetch_sorted_tags(test_repo_dir)

        # Lexicographic descending: 'm'(109) > '2'(50), so "main" is first among all;
        # among 2026.2.* strings, '2' < 'a' < 'b' etc lexicographically.
        assert tags == ["main", "2026.2.2", "2026.2.10", "2026.2.1", "2026.2.0"]

    def test_resolve_ref_to_sha_dot_boundary_and_numeric(self, tmp_path):
        """Ref '2026.2' must pick 2026.2.10 over 2026.2.9 numerically and
        must not capture 2026.3.0 (other release) or 2026.25.0 (no dot boundary)."""
        set_args_config(
            WranglerConfig(
                workflows=[],
                spec_file="",
                repos_dir=tmp_path / "repos",
                output_dir=tmp_path / "output",
            )
        )
        rm = _make_repo_manager(tmp_path / "repos")
        test_repo_dir = tmp_path / "repos" / "prefix_test"
        test_repo_dir.mkdir(parents=True)
        (test_repo_dir / ".git").mkdir()
        expected_sha = "aabbccdd11223344556677889900aabbccddeeff"

        def fake_run(*a, **k):
            cmd = a[0] if a else ""
            if "rev-parse" in cmd:
                if cmd.endswith("2026.2.10"):
                    return _make_result(stdout=expected_sha)
                return _make_result(returncode=1, stdout="")
            if "tag" in cmd:
                return _make_result(
                    stdout="2026.2.9\n2026.2.10\n2026.25.0\n2026.3.0\nmain"
                )
            return _make_result(stdout="")

        with patch.object(rm, "run", side_effect=fake_run):
            sha = rm.resolve_ref_to_sha("prefix_test", "2026.2")
        assert sha == expected_sha

    def test_resolve_ref_to_entry_dot_boundary(self, tmp_path):
        """resolve_ref_to_entry must reject 2026.3.0 and 2026.25.0 for ref 2026.2."""
        set_args_config(
            WranglerConfig(
                workflows=[],
                spec_file="",
                repos_dir=tmp_path / "repos",
                output_dir=tmp_path / "output",
            )
        )
        rm = _make_repo_manager(tmp_path / "repos")
        test_repo_dir = tmp_path / "repos" / "entry_test"
        test_repo_dir.mkdir(parents=True)
        (test_repo_dir / ".git").mkdir()

        def fake_run(*a, **k):
            cmd = a[0] if a else ""
            if "rev-parse" in cmd:
                if cmd.endswith("2026.2.1"):
                    return _make_result(stdout="cafe123")
                return _make_result(returncode=1, stdout="")
            if "tag" in cmd:
                return _make_result(stdout="2026.2.0\n2026.2.1\n2026.3.0\nmain")
            return _make_result(stdout="")

        with patch.object(rm, "run", side_effect=fake_run):
            entry = rm.resolve_ref_to_entry("entry_test", "2026.2")
        assert entry == ("2026.2.1", "cafe123")


class TestSelectHighestPatchTag:
    """Pure-function tests for nb_wrangler.utils.select_highest_patch_tag."""

    def test_dot_boundary_excludes_other_releases(self):
        tags = ["2026.2.0", "2026.2.2", "2026.3.0", "2026.25.0", "main"]
        assert select_highest_patch_tag(tags, "2026.2") == "2026.2.2"

    def test_numeric_patch_beats_lexicographic(self):
        tags = ["2026.2.9", "2026.2.10", "2026.3.0"]
        assert select_highest_patch_tag(tags, "2026.2") == "2026.2.10"

    def test_no_matching_tags_returns_none(self):
        assert select_highest_patch_tag(["main", "v1.2.3"], "2026.2") is None

    def test_exact_patch_selection(self):
        tags = ["2026.2.0", "2026.2.2", "2026.3.0"]
        assert select_highest_patch_tag(tags, "2026.3") == "2026.3.0"
