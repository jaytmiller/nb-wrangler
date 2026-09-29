"""Shared helpers for ppe command modules.

Contains helpers used across multiple subcommand modules to avoid
circular imports between command modules.
"""

import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

from nb_wrangler.config import WranglerConfig, set_args_config, get_args_config
from nb_wrangler.logger import WranglerLogger
from nb_wrangler.ppe.config import PpeConfig


def ensure_config() -> WranglerConfig:
    """Return a global WranglerConfig, creating a minimal one if needed."""
    try:
        return get_args_config()
    except (AssertionError, AttributeError):
        config = WranglerConfig(workflows=[], repos_dir=Path("."), output_dir=Path("."))
        set_args_config(config)
        WranglerLogger.from_config(config)  # configure logging
        return config


def print_exports(name: str, config: PpeConfig) -> None:
    """Print eval-able shell exports for environment activation."""
    print(f"export NBW_ACTIVE_ENV={name}")
    print(f"export NBW_ENV_ROOT={config.nbw_root / 'envs' / name}")


def print_no_writable_pantry(forced_path: Optional[str]) -> None:
    """Print a clear error for no writable pantry."""
    if forced_path:
        print(
            f"Error: pantry '{forced_path}' is read-only or does not exist.",
            file=sys.stderr,
        )
    else:
        print(
            "Error: no writable pantry found. " "Set NBW_PANTRY to a writable path.",
            file=sys.stderr,
        )


def print_shadowing_warnings(shelves: list[dict]) -> None:
    """Warn when a name appears in multiple pantries."""
    by_name: dict[str, list[Path]] = defaultdict(list)
    for entry in shelves:
        by_name[entry["name"]].append(entry["pantry"])
    for name, pantries in by_name.items():
        if len(pantries) > 1:
            print(
                f"WARNING: '{name}' shadowed across pantries: "
                + ", ".join(str(p) for p in pantries),
                file=sys.stderr,
            )
