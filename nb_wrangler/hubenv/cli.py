"""hubenv - Persistent Platform Environments CLI for nb-wrangler.

Thin facade that re-exports ``build_parser`` and dispatches to
subcommand modules.  All ``_cmd_*`` and helper functions are defined in
dedicated modules and re-exported here for backward compatibility with
existing ``from nb_wrangler.hubenv.cli import ...`` and
``patch("nb_wrangler.hubenv.cli.*")`` references in tests.
"""

import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Backward-compat re-exports of module-level attributes that tests patch
# ---------------------------------------------------------------------------

from nb_wrangler import data_manager  # noqa: F401
from nb_wrangler.utils import sha256_file  # noqa: F401

# ---------------------------------------------------------------------------
# Module imports (subcommands live in dedicated modules)
# ---------------------------------------------------------------------------

from nb_wrangler.hubenv.parser import build_parser
from nb_wrangler.hubenv.completions_cmd import cmd_completions
from nb_wrangler.hubenv.env_create import cmd_env_create
from nb_wrangler.hubenv.env_save import cmd_env_save
from nb_wrangler.hubenv.env_restore import cmd_env_restore, find_restore_shelf
from nb_wrangler.hubenv.env_ls import cmd_env_ls
from nb_wrangler.hubenv.env_info import cmd_env_info
from nb_wrangler.hubenv.env_pkg import cmd_env_install, cmd_env_uninstall
from nb_wrangler.hubenv.env_relock import cmd_env_relock
from nb_wrangler.hubenv.env_rm import cmd_env_rm, is_safe_rm_path
from nb_wrangler.hubenv.env_ensure import (
    cmd_env_ensure,
    cmd_env_register,
    cmd_env_unregister,
    EnsureArgs,
)
from nb_wrangler.hubenv.export import (
    cmd_export,
    spec_to_requirements,
    spec_to_wrangler,
    split_conda_pip,
    extract_python_version,
)
from nb_wrangler.hubenv.var import cmd_var_ls, cmd_var_add, cmd_var_rm
from nb_wrangler.hubenv.data import (
    cmd_data_ls,
    cmd_data_download,
    cmd_data_unpack,
    cmd_data_pack,
    cmd_data_clean,
)
from nb_wrangler.hubenv.status import cmd_status, list_kernelspecs
from nb_wrangler.hubenv.doctor import (
    cmd_doctor,
    check_mamba_availability,
    check_pantry_writability,
    check_efs_mount,
    check_kernel_json_sanity,
)


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


# ---------------------------------------------------------------------------
# Backward-compat re-exports
#
# These aliases keep ``from nb_wrangler.hubenv.cli import _cmd_env_create``
# and ``patch("nb_wrangler.hubenv.cli._compile_pip_packages")`` working.
# ---------------------------------------------------------------------------

# env_create
_cmd_env_create = cmd_env_create

# env_save
_cmd_env_save = cmd_env_save

# env_restore
_cmd_env_restore = cmd_env_restore
_find_restore_shelf = find_restore_shelf

# env_ls
_cmd_env_ls = cmd_env_ls

# env_info
_cmd_env_info = cmd_env_info

# env_pkg
_cmd_env_install = cmd_env_install
_cmd_env_uninstall = cmd_env_uninstall

# env_relock
_cmd_env_relock = cmd_env_relock

# env_rm
_cmd_env_rm = cmd_env_rm
_is_safe_rm_path = is_safe_rm_path

# env_ensure
_cmd_env_ensure = cmd_env_ensure
_cmd_env_register = cmd_env_register
_cmd_env_unregister = cmd_env_unregister
_EnsureArgs = EnsureArgs

# export
_spec_to_requirements = spec_to_requirements
_spec_to_wrangler = spec_to_wrangler
_extract_python_version = extract_python_version
_split_conda_pip = split_conda_pip

# data
_cmd_data_ls = cmd_data_ls
_cmd_data_download = cmd_data_download
_cmd_data_unpack = cmd_data_unpack
_cmd_data_pack = cmd_data_pack
_cmd_data_clean = cmd_data_clean

# status
_cmd_status = cmd_status
_list_kernelspecs = list_kernelspecs

# doctor
_cmd_doctor = cmd_doctor
_check_mamba_availability = check_mamba_availability
_check_pantry_writability = check_pantry_writability
_check_efs_mount = check_efs_mount
_check_kernel_json_sanity = check_kernel_json_sanity

# var
_cmd_var_ls = cmd_var_ls
_cmd_var_add = cmd_var_add
_cmd_var_rm = cmd_var_rm

# completions
_cmd_completions = cmd_completions


if __name__ == "__main__":
    sys.exit(main())
