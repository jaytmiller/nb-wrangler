"""status subcommand: show system state summary."""

import json
import os

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.ppe._common import ensure_config
from nb_wrangler.ppe.config import PpeConfig


def cmd_status(args) -> int:
    """Handle ``ppe status`` — show system state summary."""
    ensure_config()
    config = PpeConfig()
    status = aggregate_status(config)
    if args.format == "json":
        print_status_json(status)
    else:
        print_status_table(status)
    return 0


def aggregate_status(config: PpeConfig) -> dict:
    """Build the status dict for table/json output."""
    active_env = os.environ.get("NBW_ACTIVE_ENV")
    live_envs = config.list_live_envs()
    shelves = config.list_shelves()
    kernelspecs = list_kernelspecs()
    kernel_names = {k.lower() for k in kernelspecs}
    envs = build_status_envs(live_envs, shelves, kernel_names)
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


def build_status_envs(live_envs, shelves, kernel_names) -> list[dict]:
    """Build list of env status dicts from live envs and shelves."""
    envs: dict[str, dict] = {}
    for e in live_envs:
        envs[e["name"]] = {
            "name": e["name"],
            "state": "live",
            "live_path": str(e["path"]),
            "pantry": None,
            "kernel_registered": e["name"].lower() in kernel_names,
        }
    for s in shelves:
        if s["name"] not in envs:
            envs[s["name"]] = {
                "name": s["name"],
                "state": "archived",
                "live_path": None,
                "pantry": str(s["pantry"]),
                "kernel_registered": s["name"].lower() in kernel_names,
            }
        elif envs[s["name"]]["state"] == "live":
            envs[s["name"]]["state"] = "both"
            envs[s["name"]]["pantry"] = str(s["pantry"])
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


def print_status_table(status: dict) -> None:
    """Print status as a human-readable table."""
    print(f"Active env:     {status['active_env'] or '(none)'}")
    print(f"Active pantry:  {status['active_pantry']}")
    print()
    print(f"{'ENV':<20} {'STATE':<10} {'LIVE':<36} {'PANTRY':<28} {'KERNEL'}")
    print("-" * 104)
    for env in sorted(status["environments"], key=lambda x: x["name"]):
        kernel = "registered" if env["kernel_registered"] else "absent"
        live = str(env["live_path"] or "-")
        pantry = str(env["pantry"] or "-")
        print(f"{env['name']:<20} {env['state']:<10} {live:<36} {pantry:<28} {kernel}")
    print()
    print("Pantries:")
    for p in status["pantries"]:
        writable = "r/w" if p["writable"] else "r/o"
        print(f"  {p['path']} ({writable})")


def print_status_json(status: dict) -> None:
    """Print status as JSON."""
    print(json.dumps(status, indent=2))


# Backward-compat re-exports


def _cmd_status(args) -> int:
    """Backward-compat alias for ``cmd_status``."""
    return cmd_status(args)


def _aggregate_status(config):
    """Backward-compat alias for ``aggregate_status``."""
    return aggregate_status(config)


def _build_status_envs(live_envs, shelves, kernel_names):
    """Backward-compat alias for ``build_status_envs``."""
    return build_status_envs(live_envs, shelves, kernel_names)


def _list_kernelspecs():
    """Backward-compat alias for ``list_kernelspecs``.

    Tests patch ``nb_wrangler.ppe.cli._list_kernelspecs``; this alias
    keeps that path working when re-exported from ``cli.py``.
    """
    return list_kernelspecs()


def _print_status_table(status):
    """Backward-compat alias for ``print_status_table``."""
    print_status_table(status)


def _print_status_json(status):
    """Backward-compat alias for ``print_status_json``."""
    print_status_json(status)
