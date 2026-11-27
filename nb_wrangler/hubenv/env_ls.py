"""env ls subcommand: list live environments and pantry shelves."""

from pathlib import Path

from nb_wrangler.hubenv._common import print_shadowing_warnings
from nb_wrangler.hubenv.config import PantryStore


def cmd_env_ls(args) -> int:
    """Handle ``hubenv ls`` — list live envs and pantry shelves."""
    config = PantryStore()

    pantry_dir = Path(args.pantry) if args.pantry else None
    patterns = args.patterns if args.patterns else [None]

    all_shelves = []
    for pattern in patterns:
        all_shelves.extend(config.list_shelves(glob_expr=pattern, pantry=pantry_dir))

    live_envs = config.list_live_envs()
    live_names = {e["name"] for e in live_envs}

    if args.format == "json":
        print_ls_json(all_shelves, live_envs, config)
    else:
        print_ls_table(all_shelves, live_names, args.all, config)

    print_shadowing_warnings(all_shelves)
    return 0


def _archive_cell(name: str, entry: dict, config) -> str:
    """Return a short ARCHIVE cell: a truncated hash, or a spec-only marker."""
    if config.has_can(name):
        return (entry["save_hash"] or "ok")[:12]
    return "spec-only"


def print_ls_table(
    shelves: list[dict], live_names: set[str], show_all: bool, config: PantryStore
) -> None:
    """Print a table of shelves and live envs."""
    seen: set[str] = set()
    print(f"{'NAME':<20} {'PANTRY':<30} {'STATUS':<8} {'ARCHIVE':<16} {'LIVE'}")
    print("-" * 88)
    for entry in shelves:
        name = entry["name"]
        if not show_all and name in seen:
            continue
        seen.add(name)
        writable = "r/o" if not entry["writable"] else ""
        archive = _archive_cell(name, entry, config)
        live_mark = "*" if name in live_names else ""
        print(
            f"{name:<20} {str(entry['pantry']):<30} {writable:<8} "
            f"{archive:<16} {live_mark}"
        )
    for env in live_names - seen:
        print(f"{env:<20} {'<live>':<30} {'':<8} {'not a shelf':<16} *")


def print_ls_json(
    shelves: list[dict], live_envs: list[dict], config: PantryStore
) -> None:
    """Print ls results as JSON."""
    import json

    result = {
        "shelves": [
            {
                "name": s["name"],
                "pantry": str(s["pantry"]),
                "writable": s["writable"],
                "save_hash": s["save_hash"],
                "can": config.has_can(s["name"]),
            }
            for s in shelves
        ],
        "live_envs": [{"name": e["name"], "path": str(e["path"])} for e in live_envs],
    }
    print(json.dumps(result, indent=2))
