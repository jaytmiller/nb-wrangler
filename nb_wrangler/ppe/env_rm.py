"""env rm subcommand: delete environments from live and/or archive."""

import shutil
import sys
from fnmatch import fnmatch
from pathlib import Path

from nb_wrangler.ppe._common import ensure_config
from nb_wrangler.ppe.config import PpeConfig


def cmd_env_rm(args) -> int:
    """Handle ``ppe env rm`` — delete envs from live and/or archive.

    Orchestrates: resolve targets -> dry-run check -> validate ->
    confirm -> execute.
    """
    ensure_config()
    config = PpeConfig()

    target_type = args.target or "both"
    targets = resolve_rm_targets(config, args.names, target_type, args.pantry)

    if not targets:
        print("No matching environments found.", file=sys.stderr)
        return 1

    if args.dry_run:
        print_rm_plan(targets)
        return 0

    if validate_rm_targets(targets, config):
        return 1

    print_rm_plan(targets)
    return confirm_and_rm(targets, args.yes)


def validate_rm_targets(targets, config) -> bool:
    """Return True if validation fails (error already printed)."""
    errors = check_rm_readonly(targets)
    if errors:
        for msg in errors:
            print(f"Error: {msg}", file=sys.stderr)
        print(
            "Set NBW_PANTRY to a writable path or use --pantry <writable-path>.",
            file=sys.stderr,
        )
        return True

    unsafe = [t for t in targets if not is_safe_rm_path(t, config)]
    if unsafe:
        for t in unsafe:
            print(
                f"Error: refusing to delete path outside safe roots: {t['path']}",
                file=sys.stderr,
            )
        return True
    return False


def confirm_and_rm(targets, yes: bool) -> int:
    """Prompt for confirmation then execute deletions."""
    if not yes:
        if not prompt_rm_confirmation():
            print("Aborted.", file=sys.stderr)
            return 1
    return 1 if do_rm(targets) > 0 else 0


def resolve_rm_targets(config, patterns, target_type, pantry_filter):
    """Resolve NAME patterns against live envs and/or shelves."""
    targets = []
    if target_type in ("live", "both"):
        targets.extend(resolve_live_targets(config, patterns))
    if target_type in ("archived", "both"):
        targets.extend(resolve_shelf_targets(config, patterns, pantry_filter))
    return targets


def resolve_live_targets(config, patterns):
    """Resolve patterns against live envs under NBW_ROOT/envs/."""
    live_envs = config.list_live_envs()
    return [
        {"type": "live", "name": e["name"], "path": e["path"], "writable": True}
        for e in live_envs
        if matches_any_pattern(e["name"], patterns)
    ]


def resolve_shelf_targets(config, patterns, pantry_filter):
    """Resolve patterns against shelves across pantries."""
    pantry_dir = Path(pantry_filter) if pantry_filter else None
    shelves = config.list_shelves(pantry=pantry_dir)
    return [
        {
            "type": "shelf",
            "name": s["name"],
            "path": s["path"],
            "pantry": s["pantry"],
            "writable": s["writable"],
        }
        for s in shelves
        if matches_any_pattern(s["name"], patterns)
    ]


def matches_any_pattern(name, patterns):
    """Check if *name* matches any of the glob *patterns*."""
    return any(fnmatch(name, p) for p in patterns)


def check_rm_readonly(targets):
    """Return list of error messages for read-only targets."""
    errors = []
    for t in targets:
        if t["type"] == "shelf" and not t["writable"]:
            errors.append(
                f"cannot delete '{t['name']}' from read-only pantry: {t['pantry']}"
            )
    return errors


def is_safe_rm_path(target, config):
    """Check that a resolved rm target path is under a safe root."""
    path = target["path"].resolve()
    if target["type"] == "live":
        safe_root = (config.nbw_root / "envs").resolve()
        return path.is_relative_to(safe_root)
    for pantry in config.pantry_dirs:
        safe_root = (pantry / "shelves").resolve()
        if path.is_relative_to(safe_root):
            return True
    return False


def print_rm_plan(targets):
    """Print the planned deletions."""
    print("The following will be removed:")
    for t in targets:
        if t["type"] == "live":
            print(f"  [live]   {t['name']:<20} -> {t['path']}")
        else:
            print(f"  [shelf]  {t['name']:<20} -> {t['path']}  ({t['pantry']})")


def prompt_rm_confirmation():
    """Prompt for confirmation. Returns True if confirmed."""
    try:
        response = input("Proceed? (y/N): ").strip().lower()
    except EOFError:
        return False
    return response in ("y", "yes")


def do_rm(targets):
    """Delete the resolved targets. Returns number of failures."""
    failures = 0
    for t in targets:
        path = t["path"]
        if not path.exists():
            print(f"Already gone: {t['type']} '{t['name']}'")
            continue
        try:
            shutil.rmtree(path)
            print(f"Removed {t['type']} '{t['name']}' at {path}")
        except OSError as e:
            print(f"Warning: could not remove {t['name']}: {e}", file=sys.stderr)
            failures += 1
    cleanup_empty_shelf_dirs(targets)
    return failures


def cleanup_empty_shelf_dirs(targets):
    """Best-effort removal of now-empty shelves/ directories."""
    seen = set()
    for t in targets:
        if t["type"] != "shelf":
            continue
        shelves_dir = t["pantry"] / "shelves"
        if shelves_dir in seen:
            continue
        seen.add(shelves_dir)
        if shelves_dir.exists():
            try:
                if not list(shelves_dir.iterdir()):
                    shutil.rmtree(shelves_dir)
            except OSError:
                pass


# Backward-compat re-exports


def _cmd_env_rm(args) -> int:
    """Backward-compat alias for ``cmd_env_rm``."""
    return cmd_env_rm(args)


def _resolve_rm_targets(config, patterns, target_type, pantry_filter):
    """Backward-compat alias for ``resolve_rm_targets``."""
    return resolve_rm_targets(config, patterns, target_type, pantry_filter)


def _resolve_live_targets(config, patterns):
    """Backward-compat alias for ``resolve_live_targets``."""
    return resolve_live_targets(config, patterns)


def _resolve_shelf_targets(config, patterns, pantry_filter):
    """Backward-compat alias for ``resolve_shelf_targets``."""
    return resolve_shelf_targets(config, patterns, pantry_filter)


def _matches_any_pattern(name, patterns):
    """Backward-compat alias for ``matches_any_pattern``."""
    return matches_any_pattern(name, patterns)


def _check_rm_readonly(targets):
    """Backward-compat alias for ``check_rm_readonly``."""
    return check_rm_readonly(targets)


def _is_safe_rm_path(target, config):
    """Backward-compat alias for ``is_safe_rm_path``.

    This is the function directly imported/patched by tests.
    """
    return is_safe_rm_path(target, config)


def _print_rm_plan(targets):
    """Backward-compat alias for ``print_rm_plan``."""
    print_rm_plan(targets)


def _prompt_rm_confirmation():
    """Backward-compat alias for ``prompt_rm_confirmation``."""
    return prompt_rm_confirmation()


def _do_rm(targets):
    """Backward-compat alias for ``do_rm``."""
    return do_rm(targets)


def _cleanup_empty_shelf_dirs(targets):
    """Backward-compat alias for ``cleanup_empty_shelf_dirs``."""
    cleanup_empty_shelf_dirs(targets)
