"""env info subcommand: show detailed environment metadata."""

from pathlib import Path

from nb_wrangler.hubenv._common import get_logger, print_shadowing_warnings
from nb_wrangler.hubenv.config import PantryStore


def cmd_env_info(args) -> int:
    """Handle ``hubenv env info NAME`` — show detailed environment metadata."""
    config = PantryStore()

    pantry_dir = Path(args.pantry) if args.pantry else None
    shelves = config.list_shelves(glob_expr=args.name, pantry=pantry_dir)
    live_envs = config.list_live_envs()
    live_names = {e["name"] for e in live_envs}

    if not shelves and args.name not in live_names:
        get_logger().warning(f"No shelf or live env named '{args.name}' found.")
        return 1

    if args.format == "json":
        print_info_json(args.name, shelves, live_envs)
    else:
        print_info_table(args.name, shelves, live_envs)

    print_shadowing_warnings(shelves)
    return 0


def print_info_table(name: str, shelves: list[dict], live_envs: list[dict]) -> None:
    """Print table-style info for *name*."""
    print(f"Environment: {name}")
    print()

    live_match = next((e for e in live_envs if e["name"] == name), None)
    if live_match:
        print(f"  Live env:    {live_match['path']} *")
    else:
        print("  Live env:    (not installed)")
    print()

    if not shelves:
        print("  No shelves found.")
        return

    for i, entry in enumerate(shelves):
        writable = "r/o" if not entry["writable"] else "r/w"
        hash_short = entry["save_hash"] or "none"
        print(f"  Shelf {i + 1}:")
        print(f"    Pantry:     {entry['pantry']}")
        print(f"    Path:       {entry['path']}")
        print(f"    Writable:   {writable}")
        print(f"    Save hash:  {hash_short}")
        print()


def print_info_json(name: str, shelves: list[dict], live_envs: list[dict]) -> None:
    """Print JSON-style info for *name*."""
    import json

    result = {
        "name": name,
        "shelves": [
            {
                "name": s["name"],
                "pantry": str(s["pantry"]),
                "writable": s["writable"],
                "save_hash": s["save_hash"],
            }
            for s in shelves
        ],
        "live_env": next(
            (
                {"name": e["name"], "path": str(e["path"])}
                for e in live_envs
                if e["name"] == name
            ),
            None,
        ),
    }
    print(json.dumps(result, indent=2))
