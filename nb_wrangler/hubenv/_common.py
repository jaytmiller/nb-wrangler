"""Shared helpers for hubenv command modules.

Contains helpers used across multiple subcommand modules to avoid
circular imports between command modules.
"""

from collections import defaultdict
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from nb_wrangler.config import get_args_config
from nb_wrangler.logger import get_configured_logger
from nb_wrangler.hubenv.config import PantryStore

if TYPE_CHECKING:
    from nb_wrangler.config import WranglerConfig


def get_logger():
    """Return the configured logger for hubenv commands."""
    return get_configured_logger()


def get_config() -> "WranglerConfig":
    """Return the current WranglerConfig (must be set via _setup_config)."""
    return get_args_config()


def print_exports(name: str, store: PantryStore) -> None:
    """Print eval-able shell exports for environment activation."""
    print(f"export NBW_ACTIVE_ENV={name}")
    print(f"export NBW_ENV_ROOT={store.live_envs_root / name}")


def var_export_lines(name: str, store: PantryStore) -> list[str]:
    """Return ``export KEY=VALUE`` lines for ``name``'s shelf ``environment_vars``.

    Matches the line format of ``hubenv var ls NAME --export`` so that
    ``hubenv env activate`` stays byte-equivalent in its variable exports.
    Returns an empty list when the shelf has no spec or variables defined.
    """
    try:
        from nb_wrangler.hubenv.env_spec import load_hubenv_spec

        env_vars = load_hubenv_spec(store, name).get("environment_vars") or {}
    except Exception:
        return []
    return [f"export {key}={value}" for key, value in sorted(env_vars.items())]


def print_no_writable_pantry(forced_path: Optional[str]) -> None:
    """Print a clear error for no writable pantry."""
    if forced_path:
        get_logger().error(f"Pantry '{forced_path}' is read-only or does not exist.")
    else:
        get_logger().error(
            "No writable pantry found. Set NBW_PANTRY to a writable path."
        )


def print_shadowing_warnings(shelves: list[dict]) -> None:
    """Warn when a name appears in multiple pantries."""
    by_name: dict[str, list[Path]] = defaultdict(list)
    for entry in shelves:
        by_name[entry["name"]].append(entry["pantry"])
    for name, pantries in by_name.items():
        if len(pantries) > 1:
            get_logger().warning(
                f"'{name}' shadowed across pantries: "
                + ", ".join(str(p) for p in pantries)
            )
