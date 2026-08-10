"""Tests for rmpkgs user-confirmation gating.

Covers:
  - confirm_action() yes/no/assume-yes behavior, including that --yes never reads stdin
  - main()'s default (non-dry-run) path: decline => abort with no deletions issued
  - process_versions(): per-version prompt bypassed under assume_yes even when interactive=True
"""

from argparse import Namespace
from datetime import datetime, timedelta, timezone

import pytest

from nb_wrangler import rmpkgs


def _expired_version(version_id="v-12345"):
    """A version record well past the default 14-day cutoff."""
    return {
        "id": version_id,
        "created_at": (datetime.now(timezone.utc) - timedelta(days=60)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "metadata": {"container": {"tags": ["latest"]}},
    }


def _stub_session():
    """Minimal stand-in for GitHubSession; fetch_versions is patched out in tests,
    so the session object itself need not be functional."""
    return Namespace()


# --------------------------------------------------------------------------- #
# confirm_action
# --------------------------------------------------------------------------- #


def test_confirm_action_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "y")
    assert rmpkgs.confirm_action("Proceed?") is True


def test_confirm_action_default_is_no(monkeypatch):
    """An empty/press-return input must NOT be treated as confirmation."""
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "")
    assert rmpkgs.confirm_action("Proceed?") is False


def test_confirm_action_assume_yes_never_prompts(monkeypatch):
    # --yes must short-circuit without reading stdin. A raising input() proves the
    # prompt path was never taken.

    def _explode(*_a, **_k) -> str:  # pragma: no cover - only if contract breaks
        raise AssertionError("input() should not be called under assume_yes")

    monkeypatch.setattr("builtins.input", _explode)
    assert rmpkgs.confirm_action("Proceed?", assume_yes=True) is True


# --------------------------------------------------------------------------- #
# process_versions: per-version prompt bypassed when assume_yes=True, even if interactive=True
# --------------------------------------------------------------------------- #


def test_process_versions_skips_per_version_prompt_under_assume_yes(
    monkeypatch, tmp_path
):
    cleanup_file = tmp_path / "cleanup.versions"
    version_record = _expired_version("v-abc")

    def fake_fetch_versions(
        session, owner, scope, package_type, package_name
    ):  # noqa: ARG001
        return [version_record]

    monkeypatch.setattr(rmpkgs, "fetch_versions", fake_fetch_versions)
    deleted = []

    def fake_delete_version(
        session, owner, scope, package_type, package_name, version_id
    ):  # noqa: ARG001
        deleted.append(version_id)
        return True

    monkeypatch.setattr(rmpkgs, "delete_version", fake_delete_version)

    cutoff_epoch = int(
        (datetime.now(timezone.utc) - timedelta(days=14)).timestamp()
    )  # candidate is older than this => expired

    deleted_count, kept_count = rmpkgs.process_versions(
        _stub_session(),
        owner="spacetelescope",
        scope="orgs",
        package_type="container",
        package_name="nb-wrangler",
        cutoff_epoch=cutoff_epoch,
        tag_pattern=None,
        dry_run=False,
        interactive=True,  # normally would prompt per version...
        cleanup_file=cleanup_file,
        assume_yes=True,  # ...but --yes suppresses it entirely.
    )

    assert deleted_count == 1 and kept_count == 0
    assert "v-abc" in deleted


def test_process_versions_still_asks_per_version_when_interactive_without_assume_yes(
    monkeypatch, tmp_path
):
    """Without assume_yes, interactive=True still asks to confirm each deletion."""
    cleanup_file = tmp_path / "cleanup.versions"

    def fake_fetch_versions(
        session, owner, scope, package_type, package_name
    ):  # noqa: ARG001
        return [_expired_version("v-abc")]

    monkeypatch.setattr(rmpkgs, "fetch_versions", fake_fetch_versions)

    # Simulate a user typing 'y' once (there is exactly one candidate).
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "y")

    deleted = []

    def fake_delete_version(
        session, owner, scope, package_type, package_name, version_id
    ):  # noqa: ARG001
        deleted.append(version_id)
        return True

    monkeypatch.setattr(rmpkgs, "delete_version", fake_delete_version)

    cutoff_epoch = int((datetime.now(timezone.utc) - timedelta(days=14)).timestamp())

    deleted_count, _kept = rmpkgs.process_versions(
        _stub_session(),
        owner="spacetelescope",
        scope="orgs",
        package_type="container",
        package_name="nb-wrangler",
        cutoff_epoch=cutoff_epoch,
        tag_pattern=None,
        dry_run=False,
        interactive=True,
        cleanup_file=cleanup_file,
        assume_yes=False,
    )

    assert deleted_count == 1 and "v-abc" in deleted


# --------------------------------------------------------------------------- #
# main(): default (non-dry-run) requires confirmation; decline => abort + no deletes
# --------------------------------------------------------------------------- #


def test_main_aborts_when_user_declines(monkeypatch, tmp_path):
    """Default (non-dry-run) must not delete anything without an explicit 'y'."""
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "n")  # 'Proceed?' -> N

    def _explode_fetch(*_a, **_k):  # pragma: no cover - only if contract breaks
        raise AssertionError("fetch_versions must not run when user declines up-front")

    monkeypatch.setattr(rmpkgs, "fetch_versions", _explode_fetch)

    def _explode_delete(*_a, **_k):  # pragma: no cover - only if contract breaks
        raise AssertionError("delete_version must not run when user declines")

    monkeypatch.setattr(rmpkgs, "delete_version", _explode_delete)

    # Drive main() with controlled args so pytest's own argv (e.g. -v/--...) isn't
    # parsed by rmpkgs' argparse -- we only want to exercise the confirmation gate.
    fake_args = Namespace(
        name="nb-wrangler",
        days=14,
        owner="spacetelescope",
        type="container",
        interactive=False,
        dry_run=False,
        tag=None,
        assume_yes=False,
    )

    class _FakeParser:
        def parse_args(self):
            return fake_args

    monkeypatch.setattr(rmpkgs, "build_parser", lambda: _FakeParser())

    code = rmpkgs.main(cleanup_file=tmp_path / "cleanup.versions")

    # The upfront confirmation declined before any package was queried or deleted,
    # so neither fetch_versions nor delete_version should have been called.
    assert code == 1  # aborted by user; no deletions issued


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
