"""doctor subcommand: run self-test checks."""

import json
import os
import shutil
from pathlib import Path
from typing import Optional

from nb_wrangler.hubenv.config import PantryStore


def cmd_doctor(args) -> int:
    """Handle ``hubenv doctor`` — run self-test checks."""
    config = PantryStore()
    checks = run_doctor_checks(config)
    if args.format == "json":
        print_doctor_json(checks)
    else:
        print_doctor_table(checks)
    return 0 if all(c["pass"] for c in checks) else 1


def run_doctor_checks(config: PantryStore) -> list[dict]:
    """Run all doctor checks and return results."""
    return [
        check_mamba_availability(),
        check_pantry_writability(config),
        check_kernel_json_sanity(),
        check_spec_only_shelves(config),
    ]


def check_spec_only_shelves(config: PantryStore) -> dict:
    """Flag shelves that have a spec but no packed can (not restorable)."""
    spec_only = [
        s["name"] for s in config.list_shelves() if not config.has_can(s["name"])
    ]
    if not spec_only:
        return {
            "check": "spec-only shelves",
            "pass": True,
            "detail": "all shelves have an archive can",
            "hint": "",
        }
    names = ", ".join(sorted(spec_only))
    return {
        "check": "spec-only shelves",
        "pass": False,
        "detail": f"spec-only (no can yet): {names}",
        "hint": "Run `hubenv save <name>` for each to make it restorable.",
    }


def check_mamba_availability() -> dict:
    """Check for micromamba/mamba availability on PATH."""
    found = []
    for tool in ("micromamba", "mamba"):
        path = shutil.which(tool)
        if path:
            found.append(f"{tool} = {path}")
    if found:
        return {
            "check": "mamba/micromamba",
            "pass": True,
            "detail": ", ".join(found),
            "hint": "",
        }
    return {
        "check": "mamba/micromamba",
        "pass": False,
        "detail": "neither micromamba nor mamba on PATH",
        "hint": "Install micromamba or add mamba to PATH.",
    }


def check_pantry_writability(config: PantryStore) -> dict:
    """Check that at least one pantry is writable."""
    writable = [str(p) for p in config.writable_pantries()]
    if writable:
        return {
            "check": "pantry writability",
            "pass": True,
            "detail": ", ".join(writable),
            "hint": "",
        }
    all_paths = [str(p) for p in config.pantry_dirs]
    return {
        "check": "pantry writability",
        "pass": False,
        "detail": "No writable pantries",
        "hint": f"Check permissions on: {', '.join(all_paths)}",
    }


def check_kernel_json_sanity() -> dict:
    """Check kernel-JSON sanity for the active environment."""
    active = os.environ.get("NBW_ACTIVE_ENV")
    if not active:
        return {
            "check": "kernel-JSON sanity",
            "pass": True,
            "detail": "no active env — skipped",
            "hint": "",
        }
    kernel_dir = find_kernel_dir(active)
    if not kernel_dir:
        return kernel_missing_result(active)
    kernel_json = kernel_dir / "kernel.json"
    if not kernel_json.exists():
        return kernel_json_missing_result(active, kernel_dir)
    data = load_kernel_json(kernel_json)
    if data is None:
        return kernel_invalid_result(active)
    if not data.get("argv"):
        return kernel_no_argv_result(active)
    return {
        "check": "kernel-JSON sanity",
        "pass": True,
        "detail": f"valid kernel.json for '{active}'",
        "hint": "",
    }


def find_kernel_dir(env_name: str) -> Optional[Path]:
    """Find the Jupyter kernel directory for *env_name*."""
    kernels_base = Path.home() / ".local" / "share" / "jupyter" / "kernels"
    for name in (env_name, env_name.lower()):
        candidate = kernels_base / name
        if candidate.is_dir():
            return candidate
    return None


def load_kernel_json(path: Path) -> Optional[dict]:
    """Load and parse a kernel.json file, returning None on failure."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def kernel_missing_result(name: str) -> dict:
    """Return a fail result for a missing kernel spec."""
    return {
        "check": "kernel-JSON sanity",
        "pass": False,
        "detail": f"kernel spec for '{name}' not found",
        "hint": f"Run `hubenv register {name}` to create it.",
    }


def kernel_json_missing_result(name: str, dir_path: Path) -> dict:
    """Return a fail result for a missing kernel.json."""
    return {
        "check": "kernel-JSON sanity",
        "pass": False,
        "detail": f"kernel.json missing in {dir_path}",
        "hint": f"Re-register: `hubenv register {name}`",
    }


def kernel_invalid_result(name: str) -> dict:
    """Return a fail result for an invalid kernel.json."""
    return {
        "check": "kernel-JSON sanity",
        "pass": False,
        "detail": f"invalid kernel.json for '{name}'",
        "hint": f"Re-register: `hubenv register {name}`",
    }


def kernel_no_argv_result(name: str) -> dict:
    """Return a fail result for a kernel.json with no argv."""
    return {
        "check": "kernel-JSON sanity",
        "pass": False,
        "detail": f"kernel.json for '{name}' has no argv",
        "hint": f"Re-register: `hubenv register {name}`",
    }


def print_doctor_table(checks: list[dict]) -> None:
    """Print doctor check results as a table."""
    print("hubenv doctor — self-test results")
    print("=" * 80)
    for c in checks:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"  [{status}] {c['check']}")
        print(f"        {c['detail']}")
        if c["hint"]:
            print(f"        hint: {c['hint']}")
    print("=" * 80)
    passed = sum(1 for c in checks if c["pass"])
    print(f"{passed}/{len(checks)} checks passed")


def print_doctor_json(checks: list[dict]) -> None:
    """Print doctor check results as JSON."""
    result = {"checks": checks, "all_pass": all(c["pass"] for c in checks)}
    print(json.dumps(result, indent=2))
