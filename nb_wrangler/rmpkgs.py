#!/usr/bin/env python3
import argparse
import fnmatch
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth


# --- Config & Session Setup ---------------------------

# GitHub API v2026-03-10 style (omit trailing slash)
GITHUB_BASE = "https://api.github.com"

# Output file for your cleanup logic
CLEANUP_FILE = Path("cleanup.versions")

def get_auth_token():
    """Retrieve GitHub token from environment or gh CLI."""
    # Priority 1: Environment Variable
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token

    # Priority 2: GitHub CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

session = requests.Session()
# Either use:
#   - Personal Access Token (recommended)
#   - or basic auth: OWNER + password (less secure)
AUTH_TOKEN = get_auth_token()
if AUTH_TOKEN:
    session.headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
else:
    print("Warning: No GITHUB_TOKEN found and 'gh auth token' failed. "
          "Requests may fail if authentication is required.", file=sys.stderr)

session.headers["Accept"] = "application/vnd.github+json"
session.headers["X-GitHub-Api-Version"] = "2026-03-10"


def fetch_packages(owner, scope, package_type):
    packages = []
    url = f"{GITHUB_BASE}/{scope}/{owner}/packages?package_type={package_type}"
    while url:
        resp = session.get(url)
        resp.raise_for_status()
        packages.extend(resp.json())
        if "next" in resp.links:
            url = resp.links["next"]["url"]
        else:
            url = None
    return packages


def fetch_versions(owner, scope, package_type, package_name):
    versions = []
    url = f"{GITHUB_BASE}/{scope}/{owner}/packages/{package_type}/{package_name}/versions"
    while url:
        resp = session.get(url)
        resp.raise_for_status()
        versions.extend(resp.json())
        if "next" in resp.links:
            url = resp.links["next"]["url"]
        else:
            url = None
    return versions


def write_cleanup_lines(versions):
    with CLEANUP_FILE.open("w") as f:
        for ver in versions:
            # No extra escaping; just one JSON object per line
            f.write(json.dumps(ver, ensure_ascii=False))
            f.write("\n")
    print(f"Wrote {len(versions)} versions to {CLEANUP_FILE}", file=sys.stderr)


def delete_version(owner, scope, package_type, package_name, version_id):
    # Example: delete single version
    url = (
        f"{GITHUB_BASE}/{scope}/{owner}/packages/{package_type}/{package_name}"
        f"/versions/{version_id}"
    )
    resp = session.delete(url)
    if resp.status_code in (204, 202):
        print(f"Successfully deleted version {version_id}", file=sys.stderr)
    else:
        print(f"Failed to delete version {version_id}: {resp.status_code}", file=sys.stderr)


def parse_line(line):
    try:
        obj = json.loads(line.strip())
        version_id = obj["id"]
        created_at_str = obj["created_at"]   # keep original string
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        created_epoch = int(created_at.timestamp())
        tags = obj.get("metadata", {}).get("container", {}).get("tags", [])
        return version_id, created_at, created_epoch, tags  # no format change
    except Exception as e:
        print(f"WARNING: failed to parse line: {line!r} -> {e}", file=sys.stderr)
        return None


def main():
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
    args = parser.parse_args()

    owner = args.owner
    package_type = args.type
    pattern = args.name
    cutoff_days = args.days
    interactive = args.interactive
    dry_run = args.dry_run
    tag_pattern = args.tag

    # SCOPE logic from original script
    scope = "users" if owner != "spacetelescope" else "orgs"

    # Determine packages to process
    if any(c in pattern for c in "*?[]"):
        print(f"Searching for packages matching pattern '{pattern}' in {owner} ({scope})...")
        try:
            all_packages = fetch_packages(owner, scope, package_type)
            target_packages = [p["name"] for p in all_packages if fnmatch.fnmatch(p["name"], pattern)]
            
            if not target_packages and not tag_pattern:
                print(f"No packages match '{pattern}'. Searching tags in default package 'nb-wrangler'...")
                target_packages = ["nb-wrangler"]
                tag_pattern = pattern
        except requests.exceptions.RequestException as e:
            print(f"Error fetching packages: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        target_packages = [pattern]

    if not target_packages:
        print(f"No packages found matching pattern: {pattern}")
        return

    print(f"Target packages: {', '.join(target_packages)}")
    if tag_pattern:
        print(f"Tag pattern: {tag_pattern}")

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=cutoff_days)
    cutoff_epoch = int(cutoff_dt.timestamp())

    total_deleted = 0
    total_kept = 0

    for package_name in target_packages:
        print(f"\n--- Processing package: {package_name} ---", file=sys.stderr)
        try:
            versions = fetch_versions(owner, scope, package_type, package_name)
            write_cleanup_lines(versions)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching versions for {package_name}: {e}", file=sys.stderr)
            continue

        deleted = kept = 0
        if CLEANUP_FILE.exists():
            for line in CLEANUP_FILE.read_text().splitlines():
                parsed = parse_line(line)
                if not parsed:
                    continue

                version_id, created_at, created_epoch, tags = parsed

                if tag_pattern:
                    if not any(fnmatch.fnmatch(t, tag_pattern) for t in tags):
                        continue

                if created_epoch < cutoff_epoch:
                    print(f"Candidate for deletion: tags={tags} version id={version_id} created_at={created_at}")

                    if dry_run:
                        print(f"  [DRY RUN] Would delete version {version_id}")
                        deleted += 1
                        continue

                    do_delete = True
                    if interactive:
                        choice = input(f"Delete version {version_id} (tags={tags})? [y/N] ").lower()
                        if choice not in ("y", "yes"):
                            do_delete = False

                    if do_delete:
                        delete_version(owner, scope, package_type, package_name, version_id)
                        deleted += 1
                    else:
                        print(f"Skipping version {version_id}")
                        kept += 1
                else:
                    print(f"Keeping tags={tags} version id={version_id} created_at={created_at} (within cutoff)")
                    kept += 1
                print(f"Current package status: Deleted={deleted}, kept={kept}")

        print(f"Finished package {package_name}. Deleted={deleted}, kept={kept}")
        total_deleted += deleted
        total_kept += kept

    print(f"\nAll done. Total Deleted={total_deleted}, Total Kept={total_kept}")


if __name__ == "__main__":
    sys.exit(main())
