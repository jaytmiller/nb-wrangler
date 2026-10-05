"""env ls subcommand: list live environments and pantry shelves."""

from pathlib import Path

from nb_wrangler.hubenv._common import ensure_config, print_shadowing_warnings
from nb_wrangler.hubenv.config import HubenvConfig


def cmd_env_ls(args) -> int:
    """Handle ``hubenv env ls`` — list live envs and pantry shelves."""
    ensure_config()
    config = HubenvConfig()

    pantry_dir = Path(args.pantry) if args.pantry else None
    patterns = args.patterns if args.patterns else [None]

    all_shelves = []
    for pattern in patterns:
        all_shelves.extend(config.list_shelves(glob_expr=pattern, pantry=pantry_dir))

    live_envs = config.list_live_envs()
    live_names = {e["name"] for e in live_envs}

    if args.format == "json":
        print_ls_json(all_shelves, live_envs)
    else:
        print_ls_table(all_shelves, live_names, args.all)

    print_shadowing_warnings(all_shelves)
    return 0


def print_ls_table(shelves: list[dict], live_names: set[str], show_all: bool) -> None:
    """Print a table of shelves and live envs."""
    seen: set[str] = set()
    print(f"{'NAME':<20} {'PANTRY':<30} {'STATUS':<8} {'HASH':<12} {'LIVE'}")
    print("-" * 80)
    for entry in shelves:
        name = entry["name"]
        if not show_all and name in seen:
            continue
        seen.add(name)
        writable = "r/o" if not entry["writable"] else ""
        hash_short = (entry["save_hash"] or "-")[:12]
        live_mark = "*" if name in live_names else ""
        print(
            f"{name:<20} {str(entry['pantry']):<30} {writable:<8} "
            f"{hash_short:<12} {live_mark}"
        )
    for env in live_names - seen:
        print(f"{env:<20} {'<live>':<30} {'':<8} {'':<12} *")


def print_ls_json(shelves: list[dict], live_envs: list[dict]) -> None:
    """Print ls results as JSON."""
    import json

    result = {
        "shelves": [
            {
                "name": s["name"],
                "pantry": str(s["pantry"]),
                "writable": s["writable"],
                "save_hash": s["save_hash"],
            }
            for s in shelves
        ],
        "live_envs": [{"name": e["name"], "path": str(e["path"])} for e in live_envs],
    }
    print(json.dumps(result, indent=2))
