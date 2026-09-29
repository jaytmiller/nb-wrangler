"""doctor subcommand: run self-test checks."""

import json
import os
import shutil
from pathlib import Path
from typing import Optional

from nb_wrangler.hubenv._common import ensure_config
from nb_wrangler.hubenv.config import HubenvConfig


def cmd_doctor(args) -> int:
    """Handle ``hubenv doctor`` — run self-test checks."""
    ensure_config()
    config = HubenvConfig()
    checks = run_doctor_checks(config)
    if args.format == "json":
        print_doctor_json(checks)
    else:
        print_doctor_table(checks)
    return 0 if all(c["pass"] for c in checks) else 1


def run_doctor_checks(config: HubenvConfig) -> list[dict]:
    """Run all doctor checks and return results."""
    return [
        check_mamba_availability(),
        check_pantry_writability(config),
        check_efs_mount(config),
        check_kernel_json_sanity(),
    ]


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


def check_pantry_writability(config: HubenvConfig) -> dict:
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


def check_efs_mount(config: HubenvConfig) -> dict:
    """Check EFS mount status for pantry paths."""
    info = detect_efs_mount(config)
    if info:
        return {"check": "EFS mount", "pass": True, "detail": info, "hint": ""}
    return {
        "check": "EFS mount",
        "pass": False,
        "detail": "No EFS mount detected on pantry paths",
        "hint": "Check that EFS is mounted at the pantry path.",
    }


def detect_efs_mount(config: HubenvConfig) -> str:
    """Detect EFS mount for any pantry path."""
    mounts = read_proc_mounts()
    for pantry in config.pantry_dirs:
        if not pantry.exists():
            continue
        for _, mount_point, fstype, _ in mounts:
            if "efs" in fstype.lower() or "efs" in mount_point.lower():
                if str(pantry).startswith(mount_point):
                    return f"{pantry} on {fstype} ({mount_point})"
    return ""


def read_proc_mounts() -> list[tuple[str, str, str, str]]:
    """Parse /proc/mounts and return (device, mount_point, fstype, options)."""
    results: list[tuple[str, str, str, str]] = []
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4:
                    results.append((parts[0], parts[1], parts[2], parts[3]))
    except OSError:
        pass
    return results


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
        "hint": f"Run `hubenv env register {name}` to create it.",
    }


def kernel_json_missing_result(name: str, dir_path: Path) -> dict:
    """Return a fail result for a missing kernel.json."""
    return {
        "check": "kernel-JSON sanity",
        "pass": False,
        "detail": f"kernel.json missing in {dir_path}",
        "hint": f"Re-register: `hubenv env register {name}`",
    }


def kernel_invalid_result(name: str) -> dict:
    """Return a fail result for an invalid kernel.json."""
    return {
        "check": "kernel-JSON sanity",
        "pass": False,
        "detail": f"invalid kernel.json for '{name}'",
        "hint": f"Re-register: `hubenv env register {name}`",
    }


def kernel_no_argv_result(name: str) -> dict:
    """Return a fail result for a kernel.json with no argv."""
    return {
        "check": "kernel-JSON sanity",
        "pass": False,
        "detail": f"kernel.json for '{name}' has no argv",
        "hint": f"Re-register: `hubenv env register {name}`",
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


# Backward-compat re-exports


def _cmd_doctor(args) -> int:
    """Backward-compat alias for ``cmd_doctor``."""
    return cmd_doctor(args)


def _run_doctor_checks(config):
    """Backward-compat alias for ``run_doctor_checks``."""
    return run_doctor_checks(config)


def _check_mamba_availability():
    """Backward-compat alias for ``check_mamba_availability``."""
    return check_mamba_availability()


def _check_pantry_writability(config):
    """Backward-compat alias for ``check_pantry_writability``."""
    return check_pantry_writability(config)


def _check_efs_mount(config):
    """Backward-compat alias for ``check_efs_mount``."""
    return check_efs_mount(config)


def _detect_efs_mount(config):
    """Backward-compat alias for ``detect_efs_mount``."""
    return detect_efs_mount(config)


def _read_proc_mounts():
    """Backward-compat alias for ``read_proc_mounts``."""
    return read_proc_mounts()


def _check_kernel_json_sanity():
    """Backward-compat alias for ``check_kernel_json_sanity``."""
    return check_kernel_json_sanity()


def _find_kernel_dir(env_name):
    """Backward-compat alias for ``find_kernel_dir``."""
    return find_kernel_dir(env_name)


def _load_kernel_json(path):
    """Backward-compat alias for ``load_kernel_json``."""
    return load_kernel_json(path)


def _kernel_missing_result(name):
    """Backward-compat alias for ``kernel_missing_result``."""
    return kernel_missing_result(name)


def _kernel_json_missing_result(name, dir_path):
    """Backward-compat alias for ``kernel_json_missing_result``."""
    return kernel_json_missing_result(name, dir_path)


def _kernel_invalid_result(name):
    """Backward-compat alias for ``kernel_invalid_result``."""
    return kernel_invalid_result(name)


def _kernel_no_argv_result(name):
    """Backward-compat alias for ``kernel_no_argv_result``."""
    return kernel_no_argv_result(name)


def _print_doctor_table(checks):
    """Backward-compat alias for ``print_doctor_table``."""
    print_doctor_table(checks)


def _print_doctor_json(checks):
    """Backward-compat alias for ``print_doctor_json``."""
    print_doctor_json(checks)
