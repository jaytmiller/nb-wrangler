"""status subcommand: show system state summary."""

import json
import os

from tabulate import tabulate

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.hubenv.config import PantryStore


def cmd_status(args) -> int:
    """Handle ``hubenv status`` — show system state summary."""
    config = PantryStore()
    status = aggregate_status(config)
    if args.format == "json":
        print_status_json(status)
    else:
        print_status_table(status)
    return 0


def aggregate_status(config: PantryStore) -> dict:
    """Build the status dict for table/json output."""
    active_env = os.environ.get("NBW_ACTIVE_ENV")
    live_envs = config.list_live_envs()
    shelves = config.list_shelves()
    kernelspecs = list_kernelspecs()
    kernel_names = {k.lower() for k in kernelspecs}
    envs = build_status_envs(config, live_envs, shelves, kernel_names)
    return {
        "active_env": active_env,
        "active_pantry": os.environ.get("NBW_PANTRY")
        or str(config.first_writable_pantry()),
        "pantries": [
            {"path": str(p), "writable": config.is_writable(p)}
            for p in config.pantry_dirs
        ],
        "environments": envs,
    }


def _state_for(live: bool, has_shelf: bool, has_can: bool) -> str:
    """Derive the self-describing state string for an environment.

    - live + can        -> "live+archived"
    - live + no can     -> "live+spec-only"
    - no live + can     -> "archived"
    - no live + no can  -> "spec-only"
    - live only (no shelf) -> "live"
    """
    if live and has_can:
        return "live+archived"
    if live and has_shelf and not has_can:
        return "live+spec-only"
    if live:
        return "live"
    if has_can:
        return "archived"
    if has_shelf:
        return "spec-only"
    return "unknown"


def build_status_envs(
    config: PantryStore, live_envs, shelves, kernel_names
) -> list[dict]:
    """Build list of env status dicts from live envs and shelves.

    Uses :meth:`PantryStore.has_can` as the single source of truth for
    "actually archived" — a shelf directory alone is NOT archived.
    """
    envs: dict[str, dict] = {}
    for e in live_envs:
        name = e["name"]
        has_can = config.has_can(name)
        envs[name] = {
            "name": name,
            "state": _state_for(True, config.has_shelf(name), has_can),
            "live": True,
            "can": has_can,
            "live_path": str(e["path"]),
            "pantry": None,
            "kernel_registered": name.lower() in kernel_names,
        }
    for s in shelves:
        name = s["name"]
        has_can = config.has_can(name)
        if name not in envs:
            envs[name] = {
                "name": name,
                "state": _state_for(False, True, has_can),
                "live": False,
                "can": has_can,
                "live_path": None,
                "pantry": str(s["pantry"]),
                "kernel_registered": name.lower() in kernel_names,
            }
        else:
            envs[name]["pantry"] = str(s["pantry"])
            envs[name]["state"] = _state_for(True, True, has_can)
            envs[name]["can"] = has_can
    return list(envs.values())


def list_kernelspecs() -> dict:
    """Return kernelspecs via ``jupyter kernelspec list --json``."""
    em = EnvironmentManager()
    result = em.wrangler_run("jupyter kernelspec list --json", check=False)
    if not hasattr(result, "returncode"):
        return {}
    if getattr(result, "returncode", 0) != 0:
        return {}
    stdout = getattr(result, "stdout", None) or ""
    try:
        return json.loads(stdout).get("kernelspecs", {})
    except (ValueError, TypeError):
        return {}


def _build_env_rows(envs: list[dict]) -> list[list[str]]:
    """Return one table row per environment, sorted by name."""
    rows = []
    for env in sorted(envs, key=lambda x: x["name"]):
        rows.append(
            [
                env["name"],
                env["state"],
                str(env["live_path"] or "-"),
                str(env["pantry"] or "-"),
                "registered" if env["kernel_registered"] else "absent",
                "yes" if env["can"] else "no (spec-only)",
            ]
        )
    return rows


def print_status_table(status: dict) -> None:
    """Print status as a human-readable table."""
    print(f"Active env:     {status['active_env'] or '(none)'}")
    print(f"Active pantry:  {status['active_pantry']}")
    print()
    print(
        tabulate(
            _build_env_rows(status["environments"]),
            headers=["ENV", "STATE", "LIVE", "PANTRY", "KERNEL", "ARCHIVED"],
            tablefmt="grid",
        )
    )
    print()
    print("Pantries:")
    pantry_rows = [
        [str(p["path"]), "r/w" if p["writable"] else "r/o"] for p in status["pantries"]
    ]
    print(
        tabulate(
            pantry_rows,
            headers=["PATH", "Writable"],
            tablefmt="grid",
        )
    )


def print_status_json(status: dict) -> None:
    """Print status as JSON."""
    print(json.dumps(status, indent=2))
