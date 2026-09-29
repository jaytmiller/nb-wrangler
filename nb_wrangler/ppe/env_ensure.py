"""env ensure/register/unregister subcommands."""

import sys
from typing import Optional

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.ppe._common import ensure_config, print_exports
from nb_wrangler.ppe.config import PpeConfig
from nb_wrangler.ppe.env_restore import cmd_env_restore, find_restore_shelf


class EnsureArgs:
    """Minimal args namespace for delegating to ``cmd_env_restore``."""

    def __init__(self, name: str, pantry: Optional[str] = None):
        self.name = name
        self.pantry = pantry
        self.force = False
        self.at_boot = False


def cmd_env_ensure(args) -> int:
    """Handle ``ppe env ensure`` — idempotent ensure an env is available.

    1. If a live env exists -> no-op.
    2. Else if an archive shelf exists -> restore it (reuse Phase 3 restore).
    3. Else -> error with create-suggestion, exit non-zero.
    """
    ensure_config()
    config = PpeConfig()
    em = EnvironmentManager()

    # 1. Live env exists -> no-op
    if em.environment_exists(args.name):
        print(f"Environment '{args.name}' is already live (idempotent skip).")
        print_exports(args.name, config)
        return 0

    # 2. Look for a shelf to restore
    matches = find_restore_shelf(config, EnsureArgs(args.name, args.pantry))
    if matches is None:
        return 1
    if not matches:
        print(
            f"Error: no live environment and no archive shelf for '{args.name}'. "
            f"Run `ppe env create ... --name {args.name}` first.",
            file=sys.stderr,
        )
        return 1

    # Delegate to restore for unpacking + kernel registration
    if args.dry_run:
        print(f"Dry-run: would restore '{args.name}' from {matches[0][1]}")
        return 0

    restore_args = EnsureArgs(args.name, args.pantry)
    return cmd_env_restore(restore_args)


def cmd_env_register(args) -> int:
    """Handle ``ppe env register`` — (re)register the Jupyter kernel."""
    ensure_config()
    em = EnvironmentManager()

    display_name = args.display_name or args.name

    if args.dry_run:
        print(f"Dry-run: would register kernel '{args.name}' as '{display_name}'")
        return 0

    success = em.register_environment(args.name, display_name, {})
    if success:
        print(f"Registered environment '{args.name}' as kernel '{display_name}'.")
        print_exports(args.name, PpeConfig())
        return 0
    return 1


def cmd_env_unregister(args) -> int:
    """Handle ``ppe env unregister`` — remove the Jupyter kernel spec."""
    ensure_config()
    em = EnvironmentManager()

    if args.dry_run:
        print(f"Dry-run: would unregister kernel '{args.name}'")
        return 0

    em.unregister_environment(args.name)
    print(f"Unregistered Jupyter kernel '{args.name}' (if it existed).")
    return 0


# Backward-compat re-exports


def _cmd_env_ensure(args) -> int:
    """Backward-compat alias for ``cmd_env_ensure``."""
    return cmd_env_ensure(args)


def _cmd_env_register(args) -> int:
    """Backward-compat alias for ``cmd_env_register``."""
    return cmd_env_register(args)


def _cmd_env_unregister(args) -> int:
    """Backward-compat alias for ``cmd_env_unregister``."""
    return cmd_env_unregister(args)


_EnsureArgs = EnsureArgs  # backward-compat alias
