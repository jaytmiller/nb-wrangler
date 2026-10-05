"""hubenv - Persistent Platform Environments CLI for nb-wrangler.

Thin facade that builds a parser and dispatches to subcommand modules.
"""

import sys
from typing import Optional

from nb_wrangler.hubenv.parser import build_parser
from nb_wrangler.hubenv.completions_cmd import cmd_completions
from nb_wrangler.hubenv.env_create import cmd_env_create
from nb_wrangler.hubenv.env_save import cmd_env_save
from nb_wrangler.hubenv.env_restore import cmd_env_restore
from nb_wrangler.hubenv.env_ls import cmd_env_ls
from nb_wrangler.hubenv.env_info import cmd_env_info
from nb_wrangler.hubenv.env_pkg import cmd_env_install, cmd_env_uninstall
from nb_wrangler.hubenv.env_relock import cmd_env_relock
from nb_wrangler.hubenv.env_rm import cmd_env_rm
from nb_wrangler.hubenv.env_ensure import (
    cmd_env_ensure,
    cmd_env_register,
    cmd_env_unregister,
)
from nb_wrangler.hubenv.export import cmd_export
from nb_wrangler.hubenv.var import cmd_var_ls, cmd_var_add, cmd_var_rm
from nb_wrangler.hubenv.data import (
    cmd_data_ls,
    cmd_data_download,
    cmd_data_unpack,
    cmd_data_pack,
    cmd_data_clean,
)
from nb_wrangler.hubenv.status import cmd_status
from nb_wrangler.hubenv.doctor import cmd_doctor


class HubenvError(Exception):
    """Base error for hubenv with a clean message and exit code."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for the ``hubenv`` command.

    Wraps all subcommands in a try/except that maps known errors to
    clean exit codes + messages — no raw tracebacks are shown for
    expected failures.
    """
    try:
        return _main(argv)
    except HubenvError as exc:
        print(f"hubenv: {exc.message}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


def _main(argv: Optional[list[str]] = None) -> int:
    """Actual command dispatch without error wrapping."""
    parser = build_parser()
    args, _ = parser.parse_known_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        "env": _dispatch_env,
        "var": _dispatch_var,
        "data": _dispatch_data,
        "export": cmd_export,
        "status": cmd_status,
        "doctor": cmd_doctor,
        "completions": cmd_completions,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        return _cmd_not_implemented(args.command)
    return handler(args)


def _cmd_not_implemented(name: str) -> int:
    """Print a clear 'not yet implemented' message and exit 2."""
    print(
        f"hubenv: '{name}' is not yet implemented. "
        f"See docs/plan-b/phases/ for the roadmap.",
        file=sys.stderr,
    )
    return 2


# ---------------------------------------------------------------------------
# Dispatch (dict-based to keep cyclomatic complexity low)
# ---------------------------------------------------------------------------

# Environment subcommand dispatch table — replaces a 13-branch if/elif chain.
_ENV_DISPATCH = {
    "create": cmd_env_create,
    "save": cmd_env_save,
    "restore": cmd_env_restore,
    "ls": cmd_env_ls,
    "info": cmd_env_info,
    "install": cmd_env_install,
    "uninstall": cmd_env_uninstall,
    "relock": cmd_env_relock,
    "rm": cmd_env_rm,
    "ensure": cmd_env_ensure,
    "register": cmd_env_register,
    "unregister": cmd_env_unregister,
}

# var subcommand dispatch
_VAR_DISPATCH = {
    "ls": cmd_var_ls,
    "add": cmd_var_add,
    "rm": cmd_var_rm,
}

# data subcommand dispatch
_DATA_DISPATCH = {
    "ls": cmd_data_ls,
    "download": cmd_data_download,
    "unpack": cmd_data_unpack,
    "pack": cmd_data_pack,
    "clean": cmd_data_clean,
}


def _dispatch_env(args) -> int:
    """Route ``hubenv env`` subcommands via dict lookup."""
    if not args.env_command:
        print(
            "hubenv env: sub-command required. Use one of: " + ", ".join(_ENV_DISPATCH)
        )
        return 0
    handler = _ENV_DISPATCH.get(args.env_command)
    if handler is None:
        return _cmd_not_implemented(args.env_command)
    return handler(args)


def _dispatch_var(args) -> int:
    """Route ``hubenv var`` subcommands via dict lookup."""
    if not args.var_command:
        print(
            "hubenv var: sub-command required. Use one of: ls, add, rm",
            file=sys.stderr,
        )
        return 0
    handler = _VAR_DISPATCH.get(args.var_command)
    if handler is None:
        return _cmd_not_implemented(args.var_command)
    return handler(args)


def _dispatch_data(args) -> int:
    """Route ``hubenv data`` subcommands via dict lookup."""
    if not args.data_command:
        print(
            "hubenv data: sub-command required. Use one of: ls, download, "
            "unpack, pack, clean",
            file=sys.stderr,
        )
        return 0
    handler = _DATA_DISPATCH.get(args.data_command)
    if handler is None:
        return _cmd_not_implemented(args.data_command)
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
