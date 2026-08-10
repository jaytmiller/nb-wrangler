#!/usr/bin/env python3
"""Cleanup utility for GitHub Packages versions."""

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

GITHUB_BASE = "https://api.github.com"
DEFAULT_CLEANUP_FILE = Path("cleanup.versions")


def get_scope(owner: str) -> str:
    """Return the GitHub API scope for the given owner."""
    return "orgs" if owner == "spacetelescope" else "users"


def get_github_token() -> Optional[str]:
    """Retrieve GitHub token from environment variable or gh CLI.

    Priority 1: GITHUB_TOKEN environment variable.
    Priority 2: Output of 'gh auth token'.
    """
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token

    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def confirm_action(message: str, assume_yes: bool = False) -> bool:
    """Ask the user for a y/N confirmation.

    Returns True if --yes/-y was passed (assume_yes), otherwise prompts on
    stdin so that destructive batch operations don't proceed without an
    explicit go-ahead by default.
    """
    if assume_yes:
        return True
    answer = input(f"{message} [y/N] ").strip().lower()
    return answer in ("y", "yes")


@dataclass
class GitHubSession:
    """Configured requests.Session for GitHub API access."""

    session: requests.Session = field(default_factory=requests.Session, init=False)

    def __post_init__(self) -> None:
        token = get_github_token()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            print(
                "Warning: No GITHUB_TOKEN found and 'gh auth token' failed. "
                "Requests may fail if authentication is required.",
                file=sys.stderr,
            )
        self.session.headers["Accept"] = "application/vnd.github+json"
        self.session.headers["X-GitHub-Api-Version"] = "2026-03-10"

    def get(self, url: str) -> requests.Response:
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp


def fetch_paginated(session: GitHubSession, url: str) -> list:
    """Fetch all pages from a paginated GitHub API endpoint."""
    items = []
    while url:
        resp = session.get(url)
        items.extend(resp.json())
        if "next" in resp.links:
            url = resp.links["next"]["url"]
        else:
            url = ""
    return items


def fetch_packages(
    session: GitHubSession, owner: str, scope: str, package_type: str
) -> list:
    """Fetch all packages for an owner/scope."""
    url = f"{GITHUB_BASE}/{scope}/{owner}/packages?package_type={package_type}"
    return fetch_paginated(session, url)


def fetch_versions(
    session: GitHubSession, owner: str, scope: str, package_type: str, package_name: str
) -> list:
    """Fetch all versions for a package."""
    url = (
        f"{GITHUB_BASE}/{scope}/{owner}/packages/{package_type}/{package_name}/versions"
    )
    return fetch_paginated(session, url)


def write_cleanup_lines(versions: list, cleanup_file: Path) -> None:
    """Write version data to a JSONL cleanup file."""
    with cleanup_file.open("w") as f:
        for ver in versions:
            f.write(json.dumps(ver, ensure_ascii=False))
            f.write("\n")
    print(f"Wrote {len(versions)} versions to {cleanup_file}", file=sys.stderr)


def delete_version(
    session: GitHubSession,
    owner: str,
    scope: str,
    package_type: str,
    package_name: str,
    version_id: str,
) -> bool:
    """Delete a package version. Returns True on success."""
    url = (
        f"{GITHUB_BASE}/{scope}/{owner}/packages/{package_type}/{package_name}"
        f"/versions/{version_id}"
    )
    resp = session.session.delete(url)
    if resp.status_code in (204, 202):
        print(f"Successfully deleted version {version_id}", file=sys.stderr)
        return True
    print(
        f"Failed to delete version {version_id}: {resp.status_code}",
        file=sys.stderr,
    )
    return False


@dataclass
class ParsedVersion:
    """Parsed version data from a cleanup file line."""

    version_id: str
    created_at: datetime
    created_epoch: int
    tags: list


def parse_created_at(created_at_str: str) -> datetime:
    """Parse an ISO-8601 timestamp string into a timezone-aware datetime."""
    return datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))


def parse_line(line: str) -> Optional[ParsedVersion]:
    """Parse a JSONL line from a cleanup file into ParsedVersion."""
    try:
        obj = json.loads(line.strip())
        version_id = obj["id"]
        created_at_str = obj["created_at"]
        created_at = parse_created_at(created_at_str)
        created_epoch = int(created_at.timestamp())
        tags = obj.get("metadata", {}).get("container", {}).get("tags", [])
        return ParsedVersion(version_id, created_at, created_epoch, tags)
    except Exception as e:
        print(f"WARNING: failed to parse line: {line!r} -> {e}", file=sys.stderr)
        return None


def matches_tag_pattern(tags: list, tag_pattern: Optional[str]) -> bool:
    """Return True if no tag pattern is set or any tag matches the pattern."""
    if not tag_pattern:
        return True
    return any(fnmatch.fnmatch(t, tag_pattern) for t in tags)


def is_expired(created_epoch: int, cutoff_epoch: int) -> bool:
    """Return True if the version was created before the cutoff epoch."""
    return created_epoch < cutoff_epoch


def process_versions(
    session: GitHubSession,
    owner: str,
    scope: str,
    package_type: str,
    package_name: str,
    cutoff_epoch: int,
    tag_pattern: Optional[str],
    dry_run: bool,
    interactive: bool,
    cleanup_file: Path,
    assume_yes: bool = False,
) -> tuple[int, int]:
    """Process versions for a single package, returning (deleted, kept) counts."""
    print(f"\n--- Processing package: {package_name} ---", file=sys.stderr)
    try:
        versions = fetch_versions(session, owner, scope, package_type, package_name)
        write_cleanup_lines(versions, cleanup_file)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching versions for {package_name}: {e}", file=sys.stderr)
        return 0, 0

    deleted = 0
    kept = 0

    if not cleanup_file.exists():
        return deleted, kept

    for line in cleanup_file.read_text().splitlines():
        parsed = parse_line(line)
        if not parsed:
            continue

        if not matches_tag_pattern(parsed.tags, tag_pattern):
            continue

        if is_expired(parsed.created_epoch, cutoff_epoch):
            print(
                f"Candidate for deletion: tags={parsed.tags} version id={parsed.version_id} "
                f"created_at={parsed.created_at}"
            )

            if dry_run:
                print(f"  [DRY RUN] Would delete version {parsed.version_id}")
                deleted += 1
                continue

            # --yes was confirmed up-front in main(); skip the per-version prompt.
            if interactive and not assume_yes:
                choice = input(
                    f"Delete version {parsed.version_id} (tags={parsed.tags})? [y/N] "
                ).lower()
                if choice not in ("y", "yes"):
                    print(f"Skipping version {parsed.version_id}")
                    kept += 1
                    print(f"Current package status: Deleted={deleted}, kept={kept}")
                    continue

            if delete_version(
                session, owner, scope, package_type, package_name, parsed.version_id
            ):
                deleted += 1
            else:
                kept += 1
        else:
            print(
                f"Keeping tags={parsed.tags} version id={parsed.version_id} "
                f"created_at={parsed.created_at} (within cutoff)"
            )
            kept += 1

        print(f"Current package status: Deleted={deleted}, kept={kept}")

    print(f"Finished package {package_name}. Deleted={deleted}, kept={kept}")
    return deleted, kept


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(description="Cleanup GitHub Packages versions.")
    parser.add_argument(
        "name",
        nargs="?",
        default="nb-wrangler",
        help="Package name or glob pattern (default: nb-wrangler).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Cutoff days for deletion (default: 14).",
    )
    parser.add_argument(
        "--owner",
        default="spacetelescope",
        help="GitHub owner (default: spacetelescope).",
    )
    parser.add_argument(
        "--type",
        default="container",
        help="Package type: 'container' or 'docker' (default: container).",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Confirm each deletion before doing it.",
    )
    parser.add_argument(
        "-l",
        "--list",
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="List versions that would be deleted without deleting them.",
    )
    parser.add_argument(
        "-t",
        "--tag",
        help="Tag pattern to match (glob).",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        dest="assume_yes",
        help="Skip the confirmation prompt before deleting versions. "
        "Intended for non-interactive/CI use; use with care.",
    )
    return parser


def main(cleanup_file: Optional[Path] = None) -> int:
    """Main entry point for the cleanup utility.

    Args:
        cleanup_file: Path to the cleanup versions file. Defaults to cleanup.versions.

    Returns:
        Exit code (0 for success).
    """
    if cleanup_file is None:
        cleanup_file = DEFAULT_CLEANUP_FILE

    args = build_parser().parse_args()
    owner = args.owner
    package_type = args.type
    pattern = args.name
    cutoff_days = args.days
    interactive = args.interactive
    dry_run = args.dry_run
    tag_pattern = args.tag

    scope = get_scope(owner)

    # Resolve target packages
    if any(c in pattern for c in "*?[]"):
        print(
            f"Searching for packages matching pattern '{pattern}' in {owner} ({scope})..."
        )
        session = GitHubSession()
        try:
            all_packages = fetch_packages(session, owner, scope, package_type)
            target_packages = [
                p["name"] for p in all_packages if fnmatch.fnmatch(p["name"], pattern)
            ]

            if not target_packages and not tag_pattern:
                print(
                    f"No packages match '{pattern}'. Searching tags in default package 'nb-wrangler'..."
                )
                target_packages = ["nb-wrangler"]
                tag_pattern = pattern
        except requests.exceptions.RequestException as e:
            print(f"Error fetching packages: {e}", file=sys.stderr)
            return 1
    else:
        target_packages = [pattern]

    if not target_packages:
        print(f"No packages found matching pattern: {pattern}")
        return 0

    print(f"Target packages: {', '.join(target_packages)}")
    if tag_pattern:
        print(f"Tag pattern: {tag_pattern}")

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=cutoff_days)
    cutoff_epoch = int(cutoff_dt.timestamp())

    # Require an explicit go-ahead before deleting old versions across all
    # target packages, so the default case can't silently wipe out a whole list.
    if not dry_run and target_packages:
        what = f"{len(target_packages)} package(s): {', '.join(target_packages)}"
        verb = "Listed" if interactive else "Will delete"
        summary = (
            f"This will delete GitHub Package versions older than {cutoff_days} day(s)"
            f" for the following target packages ({what})."
        )
        print(f"\n{verb} operation pending.", file=sys.stderr)
        print(summary, file=sys.stderr)
        if interactive:
            per_version_note = (
                "You will be asked to confirm each candidate deletion individually."
            )
            print(per_version_note, file=sys.stderr)
        else:
            print(
                "Run with -i/--interactive for per-version confirmation instead.",
                file=sys.stderr,
            )
        if not confirm_action("Proceed?", assume_yes=args.assume_yes):
            print("Aborted by user; no versions were deleted.", file=sys.stderr)
            return 1

    total_deleted = 0
    total_kept = 0

    for package_name in target_packages:
        session = GitHubSession()
        deleted, kept = process_versions(
            session,
            owner,
            scope,
            package_type,
            package_name,
            cutoff_epoch,
            tag_pattern,
            dry_run,
            interactive,
            cleanup_file,
            assume_yes=args.assume_yes,
        )
        total_deleted += deleted
        total_kept += kept

    print(f"\nAll done. Total Deleted={total_deleted}, Total Kept={total_kept}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
