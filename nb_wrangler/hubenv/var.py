"""var subcommand: manage environment variables for PPE environments."""

import fnmatch
import json
import sys

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.hubenv._common import ensure_config
from nb_wrangler.hubenv.config import HubenvConfig
from nb_wrangler.hubenv.env_spec import load_hubenv_spec, save_hubenv_spec


def cmd_var_ls(args) -> int:
    """Handle ``hubenv var ls NAME [GLOB...]``."""
    ensure_config()
    config = HubenvConfig()
    spec = load_hubenv_spec(config, args.name)
    env_vars = spec.get("environment_vars") or {}
    filtered = filter_vars_by_glob(env_vars, args.globs)
    if args.format == "json":
        print_var_ls_json(filtered, args.name)
    elif args.export:
        print_var_ls_export(filtered)
    else:
        print_var_ls_table(filtered, args.name)
    return 0


def filter_vars_by_glob(env_vars: dict, globs: list[str]) -> dict:
    """Return a copy of *env_vars* filtered by *globs* (empty => all)."""
    if not globs:
        return dict(env_vars)
    return {
        k: v for k, v in env_vars.items() if any(fnmatch.fnmatch(k, g) for g in globs)
    }


def print_var_ls_table(env_vars: dict, name: str) -> None:
    """Print a two-column VAR/VALUE table."""
    print(f"{'VAR':<20} VALUE")
    print("-" * 60)
    if not env_vars:
        print(f"(no environment variables defined for '{name}')")
        return
    for key in sorted(env_vars):
        print(f"{key:<20} {env_vars[key]}")


def print_var_ls_export(env_vars: dict) -> None:
    """Print 'export VAR=VALUE' lines suitable for eval."""
    for key in sorted(env_vars):
        print(f"export {key}={env_vars[key]}")


def print_var_ls_json(env_vars: dict, name: str) -> None:
    """Print ls results as JSON."""
    result = {
        "name": name,
        "environment_vars": dict(sorted(env_vars.items())),
    }
    print(json.dumps(result, indent=2))


# -- var add / rm ------------------------------------------------------------


def cmd_var_add(args) -> int:
    """Handle ``hubenv var add NAME VAR=VALUE...``."""
    ensure_config()
    config = HubenvConfig()
    try:
        updates = parse_var_assignments(args.assignments)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    spec = load_hubenv_spec(config, args.name)
    env_vars = spec.get("environment_vars") or {}
    spec["environment_vars"] = env_vars
    env_vars.update(updates)
    save_hubenv_spec(config, args.name, spec)
    refresh_kernel_vars(args.name, env_vars)
    print_var_add_result(args.name, updates)
    return 0


def parse_var_assignments(assignments: list[str]) -> dict[str, str]:
    """Parse ``VAR=VALUE`` strings, splitting on the first ``=``."""
    result: dict[str, str] = {}
    for item in assignments:
        if "=" not in item:
            raise ValueError(f"'{item}' is not a VAR=VALUE assignment")
        key, value = item.split("=", 1)
        result[key] = value
    return result


def print_var_add_result(name: str, updates: dict[str, str]) -> None:
    """Print a summary of added/updated env vars."""
    for key in sorted(updates):
        print(f"Set {key}={updates[key]} for env '{name}'")
    print(f"Kernel refreshed for '{name}'.")


def cmd_var_rm(args) -> int:
    """Handle ``hubenv var rm NAME GLOB...``."""
    ensure_config()
    config = HubenvConfig()
    spec = load_hubenv_spec(config, args.name)
    env_vars = spec.get("environment_vars") or {}
    spec["environment_vars"] = env_vars
    removed = remove_vars_by_glob(env_vars, args.globs)
    if not removed:
        print(f"No matching variables for {args.globs} in env '{args.name}'.")
        return 0
    save_hubenv_spec(config, args.name, spec)
    refresh_kernel_vars(args.name, env_vars)
    print_var_rm_result(args.name, removed)
    return 0


def remove_vars_by_glob(env_vars: dict, globs: list[str]) -> list[str]:
    """Remove glob-matched entries in-place. Return removed var names."""
    to_remove = [k for k in env_vars if any(fnmatch.fnmatch(k, g) for g in globs)]
    for k in to_remove:
        del env_vars[k]
    return sorted(to_remove)


def print_var_rm_result(name: str, removed: list[str]) -> None:
    """Print a summary of removed env vars."""
    for key in sorted(removed):
        print(f"Removed {key} from env '{name}'")
    print(f"Kernel refreshed for '{name}'.")


def refresh_kernel_vars(name: str, env_vars: dict[str, str]) -> None:
    """Re-register the Jupyter kernel so *name* reflects the new env vars.

    The spec is already persisted (it is the source of truth); a failed
    kernel refresh is reported on stderr rather than reverting the spec.
    ``register_environment`` logs the underlying success/failure itself.
    """
    em = EnvironmentManager()
    success = em.register_environment(name, name, env_vars)
    if not success:
        print(
            f"Warning: kernel refresh for '{name}' failed (spec still updated).",
            file=sys.stderr,
        )
