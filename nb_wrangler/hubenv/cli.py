"""hubenv - Persistent Platform Environments CLI for nb-wrangler.

Thin facade that builds a parser and dispatches to subcommand modules.
"""

import sys
from typing import Optional

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.logger import WranglerLogger, get_configured_logger
from nb_wrangler.hubenv._common import HubenvError
from nb_wrangler.constants import __version__
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
from nb_wrangler.hubenv.env_activate import cmd_env_activate, cmd_env_deactivate
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
        logger = get_configured_logger()
        logger.error(exc.message)
        return exc.exit_code
    except KeyboardInterrupt:
        get_configured_logger().info("\nInterrupted.")
        return 130


def _setup_config(args) -> None:
    """Build a WranglerConfig with hubenv fields and set it as the singleton.

    This replaces the legacy ``ensure_config()`` workaround so that
    every hubenv command benefits from proper logging configuration.
    """
    from pathlib import Path

    hubenv_command = _resolve_command_path(args)
    config = WranglerConfig(
        workflows=[],
        spec_file=getattr(args, "spec_uri", ""),
        repos_dir=Path("."),
        output_dir=Path("."),
        verbose=args.verbose,
        quiet=args.quiet,
        debug=args.debug,
        log_times=args.log_times,
        reset_log=args.reset_log,
        color=args.color,
        hubenv_command=hubenv_command,
        hubenv_args=args,
    )
    set_args_config(config)
    WranglerLogger.from_config(config)


def _resolve_command_path(args) -> Optional[str]:
    """Build a command path (e.g. ``var.ls``) from the parsed args.

    Environment verbs are top-level commands, so they simply return their own
    name (``create``, ``ls``, …). Not consumed by any code path today — kept for
    future logging/telemetry.
    """
    if args.command == "var" and args.var_command:
        return f"var.{args.var_command}"
    if args.command == "data" and args.data_command:
        return f"data.{args.data_command}"
    return args.command


def _main(argv: Optional[list[str]] = None) -> int:
    """Actual command dispatch without error wrapping."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if not args.command:
        parser.print_help()
        return 0

    _setup_config(args)

    dispatch = {
        "var": _dispatch_var,
        "data": _dispatch_data,
        "export": cmd_export,
        "status": cmd_status,
        "doctor": cmd_doctor,
        "completions": cmd_completions,
        **_ENV_DISPATCH,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        return _cmd_not_implemented(args.command)
    return handler(args)


def _cmd_not_implemented(name: str) -> int:
    """Log a clear 'not yet implemented' message and exit 2."""
    get_configured_logger().error(
        f"'{name}' is not yet implemented. See docs/plan-b/phases/ for the roadmap."
    )
    return 2


# ---------------------------------------------------------------------------
# Dispatch (dict-based to keep cyclomatic complexity low)
# ---------------------------------------------------------------------------

# Environment verb dispatch table — flattened to top-level commands and merged
# into the main dispatch dict (see ``_main``).
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
    "activate": cmd_env_activate,
    "deactivate": cmd_env_deactivate,
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


def _dispatch_var(args) -> int:
    """Route ``hubenv var`` subcommands via dict lookup."""
    if not args.var_command:
        get_configured_logger().error(
            "hubenv var: sub-command required. Use one of: ls, add, rm"
        )
        return 1
    handler = _VAR_DISPATCH.get(args.var_command)
    if handler is None:
        return _cmd_not_implemented(args.var_command)
    return handler(args)


def _dispatch_data(args) -> int:
    """Route ``hubenv data`` subcommands via dict lookup."""
    if not args.data_command:
        get_configured_logger().error(
            "hubenv data: sub-command required. Use one of: ls, download, "
            "unpack, pack, clean"
        )
        return 1
    handler = _DATA_DISPATCH.get(args.data_command)
    if handler is None:
        return _cmd_not_implemented(args.data_command)
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
