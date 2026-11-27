"""Argument parser construction for the ``hubenv`` CLI.

All ``build_parser`` and ``_add_*`` functions live here so that
``cli.py`` stays as a thin facade.
"""

import argparse
from nb_wrangler.constants import (
    VALID_LOG_TIME_MODES,
    DEFAULT_LOG_TIMES_MODE,
    VALID_COLOR_MODES,
    DEFAULT_COLOR_MODE,
)


def _add_global_flags(
    parser: argparse.ArgumentParser, subcommand: bool = False
) -> None:
    """Add global diagnostic flags to *parser*.

    Registered on the top-level parser and on each command parser so a flag
    such as ``--quiet`` works on either side of a command
    (``hubenv --quiet create`` and ``hubenv create --quiet``).

    When *subcommand* is True, defaults become :data:`argparse.SUPPRESS` so a
    command parser's defaults do not clobber a value already supplied on the
    top level. The top-level parser keeps real defaults so ``args.<flag>``
    always exists.
    """
    d_bool = argparse.SUPPRESS if subcommand else False
    d_color = argparse.SUPPRESS if subcommand else DEFAULT_COLOR_MODE
    d_times = argparse.SUPPRESS if subcommand else DEFAULT_LOG_TIMES_MODE

    global_group = parser.add_argument_group(
        "Global", "Global diagnostic and output-control flags."
    )
    global_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        dest="quiet",
        default=d_bool,
        help="Suppress all log output to stderr; only stdout will be visible.",
    )
    global_group.add_argument(
        "--verbose",
        action="store_true",
        dest="verbose",
        default=d_bool,
        help="Enable verbose log output.",
    )
    global_group.add_argument(
        "--debug",
        action="store_true",
        dest="debug",
        default=d_bool,
        help="Drop into debugging with pdb on exceptions.",
    )
    global_group.add_argument(
        "--color",
        choices=VALID_COLOR_MODES,
        default=d_color,
        dest="color",
        help="Colorize log output.",
    )
    global_group.add_argument(
        "--log-times",
        choices=VALID_LOG_TIME_MODES,
        default=d_times,
        dest="log_times",
        help="Include timestamps in log messages.",
    )
    global_group.add_argument(
        "--reset-log",
        action="store_true",
        dest="reset_log",
        default=d_bool,
        help="Delete nb-wrangler log file.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``hubenv`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="hubenv",
        description=(
            "Persistent Platform Environments CLI for nb-wrangler. "
            "Manage user-installed environments with archive/restore support."
        ),
    )
    _add_global_flags(parser)
    parser.add_argument(
        "--version",
        action="store_true",
        default=False,
        help="Print the nb-wrangler version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")

    _add_env_subcommands(subparsers)
    _add_var_subcommands(subparsers)
    _add_data_subcommands(subparsers)
    _add_export_status_doctor_subcommands(subparsers)
    _add_completions_subcommands(subparsers)
    return parser


def _add_env_subcommands(subparsers) -> None:
    """Add the environment verbs as top-level commands (flattened from ``env``).

    Environments are hubenv's primary resource, so their verbs sit at the top
    level (``hubenv create`` rather than ``hubenv env create``). Each verb
    parser also receives the global flags so both ``hubenv --quiet create`` and
    ``hubenv create --quiet`` parse.
    """
    verbs = [
        ("create", "Create a new environment", _add_create_args),
        ("save", "Pack a live environment into a pantry archive", _add_save_args),
        (
            "restore",
            "Unpack a saved environment and register kernel",
            _add_restore_args,
        ),
        ("ls", "List live envs and pantry shelves", _add_ls_args),
        ("info", "Show detailed info for an environment", _add_info_args),
        ("install", "Install packages into a live environment", _add_install_args),
        (
            "uninstall",
            "Uninstall packages from a live environment",
            _add_uninstall_args,
        ),
        ("relock", "Re-curate locks and validate the implicit spec", _add_relock_args),
        ("rm", "Delete environments from live and/or archive", _add_rm_args),
        (
            "ensure",
            "Idempotently ensure an env is available (live or restored)",
            _add_ensure_args,
        ),
        ("register", "Register Jupyter kernel for an environment", _add_register_args),
        (
            "unregister",
            "Unregister Jupyter kernel for an environment",
            _add_unregister_args,
        ),
        (
            "activate",
            "Print a shell snippet (for eval/source) that activates an environment by path",
            _add_activate_args,
        ),
        (
            "deactivate",
            "Print a shell snippet (for eval/source) that deactivates the current mamba environment",
            None,
        ),
    ]
    for name, help_text, add_args in verbs:
        verb_parser = subparsers.add_parser(name, help=help_text)
        if add_args is not None:
            add_args(verb_parser)
        _add_global_flags(verb_parser, subcommand=True)


def _add_export_status_doctor_subcommands(subparsers) -> None:
    """Add export, status, doctor subcommand parsers (Phase 10)."""
    export = subparsers.add_parser(
        "export", help="Export environment spec in various formats"
    )
    _add_export_args(export)
    status = subparsers.add_parser("status", help="Show system state summary")
    _add_status_args(status)
    doctor = subparsers.add_parser("doctor", help="Run self-test checks")
    _add_doctor_args(doctor)


def _add_completions_subcommands(subparsers) -> None:
    """Add the ``completions`` subcommand (Phase 11)."""
    comp = subparsers.add_parser("completions", help="Print shell completion scripts")
    _add_global_flags(comp)
    comp.add_argument(
        "shell",
        choices=["bash", "zsh", "fish"],
        help="Shell to generate completions for",
    )


def _add_var_subcommands(subparsers) -> None:
    """Add the ``var`` subcommand group (Phase 8: env var management)."""
    var_parser = subparsers.add_parser(
        "var", help="Manage environment variables for an env"
    )
    _add_global_flags(var_parser)
    var_sub = var_parser.add_subparsers(dest="var_command")

    ls = var_sub.add_parser("ls", help="List env vars defined for an environment")
    _add_var_ls_args(ls)

    add = var_sub.add_parser("add", help="Add or update env vars")
    _add_var_add_args(add)

    rm = var_sub.add_parser("rm", help="Remove env vars by glob")
    _add_var_rm_args(rm)


def _add_var_ls_args(p) -> None:
    """Add ``var ls`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "globs",
        nargs="*",
        default=[],
        metavar="GLOB",
        help="Filter variables by name glob (default: all vars)",
    )
    p.add_argument(
        "--export",
        action="store_true",
        help="Print 'export VAR=VALUE' lines (suitable for eval)",
    )
    p.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    p.add_argument(
        "--pantry",
        default=None,
        help="Restrict shelf search to a single pantry directory",
    )


def _add_var_add_args(p) -> None:
    """Add ``var add`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "assignments",
        nargs="+",
        metavar="VAR=VALUE",
        help="One or more VAR=VALUE assignments to add/update",
    )
    p.add_argument(
        "--pantry",
        default=None,
        help="Restrict shelf search to a single pantry directory",
    )


def _add_var_rm_args(p) -> None:
    """Add ``var rm`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "globs",
        nargs="+",
        metavar="GLOB",
        help="Glob pattern(s) matching variable names to remove",
    )
    p.add_argument(
        "--pantry",
        default=None,
        help="Restrict shelf search to a single pantry directory",
    )


def _add_data_subcommands(subparsers) -> None:
    """Add the ``data`` subcommand group (Phase 9a: data archive management)."""
    data_parser = subparsers.add_parser(
        "data", help="Manage data archives for an environment"
    )
    _add_global_flags(data_parser)
    data_sub = data_parser.add_subparsers(dest="data_command")

    ls = data_sub.add_parser("ls", help="List data archives for an environment")
    _add_data_ls_args(ls)

    download = data_sub.add_parser("download", help="Download data archives (Phase 9b)")
    _add_data_download_args(download)

    unpack = data_sub.add_parser("unpack", help="Unpack data archives (Phase 9b)")
    _add_data_unpack_args(unpack)

    pack = data_sub.add_parser("pack", help="Pack live data dirs into archive files")
    _add_data_pack_args(pack)

    clean = data_sub.add_parser(
        "clean", help="Delete data archives and/or unpacked files"
    )
    _add_data_clean_args(clean)


def _add_create_args(p) -> None:
    """Add ``env create`` specific arguments to *p*."""
    sources = p.add_mutually_exclusive_group(required=True)
    sources.add_argument(
        "--from-empty", action="store_true", help="Create an empty environment"
    )
    sources.add_argument(
        "--from-requirements",
        nargs="*",
        metavar="FILE",
        default=[],
        help="Seed from one or more requirements files",
    )
    sources.add_argument(
        "--from-mamba-spec",
        metavar="FILE",
        help="Seed from a mamba/conda spec YAML file",
    )
    sources.add_argument(
        "--from-wrangler-spec",
        metavar="FILE",
        help="Seed from a wrangler spec YAML file",
    )
    sources.add_argument(
        "--from-existing-env",
        metavar="ENV_NAME",
        help="Import an existing mamba environment into the PPE lifecycle",
    )
    p.add_argument(
        "--name",
        default=None,
        help="Environment name. Required for --from-empty and --from-requirements; "
        "optional for the other sources, where it defaults to the source's own "
        "name (mamba spec name, wrangler spec kernel_name or image_name or "
        "inline mamba spec name, imported env name).",
    )
    p.add_argument(
        "--display-name",
        default=None,
        help="Jupyter kernel display name (defaults to the wrangler spec's "
        "display_name, then env name).",
    )
    p.add_argument("--python", default=None, help="Python version (e.g. 3.11)")
    p.add_argument(
        "--pantry",
        default=None,
        help="Target pantry directory (default: first writable pantry)",
    )
    p.add_argument(
        "--ephemeral",
        action="store_true",
        help="Build only the live environment; skip shelf-spec persistence "
        "and kernel registration. Use for temporary or CI scratch envs.",
    )
    p.add_argument(
        "--save",
        action="store_true",
        help="Archive the environment into a pantry can immediately after "
        "creation (equivalent to a subsequent `hubenv save NAME`).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the seeded spec without installing",
    )


def _add_save_args(p) -> None:
    """Add ``env save`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name to archive")
    p.add_argument(
        "--pantry",
        default=None,
        help="Target pantry directory (default: first writable pantry)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned paths without writing",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing archive",
    )


def _add_restore_args(p) -> None:
    """Add ``env restore`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name to restore")
    p.add_argument(
        "--pantry",
        default=None,
        help="Source pantry directory (default: search all pantries)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Skip idempotency check and re-unpack",
    )
    p.add_argument(
        "--at-boot",
        action="store_true",
        help="Write a guarded startup snippet for idempotent restore",
    )


def _add_ls_args(p) -> None:
    """Add ``env ls`` specific arguments to *p*."""
    p.add_argument(
        "patterns",
        nargs="*",
        default=[],
        metavar="NAME-or-glob",
        help="Filter shelves by name or glob pattern",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Show every match across pantries (don't collapse to first)",
    )
    p.add_argument(
        "--pantry",
        default=None,
        help="Restrict search to a single pantry directory",
    )
    p.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )


def _add_info_args(p) -> None:
    """Add ``env info`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name to inspect")
    p.add_argument(
        "--pantry",
        default=None,
        help="Restrict search to a single pantry directory",
    )
    p.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )


def _add_install_args(p) -> None:
    """Add ``env install`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument("packages", nargs="+", metavar="PACKAGE", help="Packages to install")
    p.add_argument(
        "--using",
        choices=["mamba", "pip", "uv"],
        default=None,
        help="Installer to use (default: pip via NBW_PIP_CMD)",
    )
    p.add_argument(
        "--no-relock",
        action="store_true",
        help="Suppress the relock suggestion message",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned action without executing",
    )


def _add_uninstall_args(p) -> None:
    """Add ``env uninstall`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "packages", nargs="+", metavar="PACKAGE", help="Packages to uninstall"
    )
    p.add_argument(
        "--using",
        choices=["mamba", "pip", "uv"],
        default=None,
        help="Installer to use (default: pip via NBW_PIP_CMD)",
    )
    p.add_argument(
        "--no-relock",
        action="store_true",
        help="Suppress the relock suggestion message",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned action without executing",
    )


def _add_relock_args(p) -> None:
    """Add ``env relock`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show resolved plan without writing",
    )


def _add_rm_args(p) -> None:
    """Add ``env rm`` specific arguments to *p*."""
    p.add_argument(
        "names",
        nargs="+",
        metavar="NAME",
        help="Environment name(s) or glob patterns (e.g. team-*)",
    )
    target = p.add_mutually_exclusive_group()
    target.add_argument(
        "--live",
        action="store_const",
        dest="target",
        const="live",
        help="Remove only from live envs (NBW_MM/envs/)",
    )
    target.add_argument(
        "--archived",
        action="store_const",
        dest="target",
        const="archived",
        help="Remove only from archived shelves",
    )
    target.add_argument(
        "--both",
        action="store_const",
        dest="target",
        const="both",
        help="Remove from both live and archived (default)",
    )
    p.add_argument(
        "--pantry",
        default=None,
        help="Restrict shelf search to a single pantry directory",
    )
    p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt (scripts/automation)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned deletions without executing",
    )


def _add_ensure_args(p) -> None:
    """Add ``env ensure`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name to ensure")
    p.add_argument(
        "--pantry",
        default=None,
        help="Source pantry directory (default: search all pantries)",
    )
    p.add_argument(
        "--display-name",
        default=None,
        help="Jupyter kernel display name (default: same as env name)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned action without executing",
    )


def _add_register_args(p) -> None:
    """Add ``env register`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name to register")
    p.add_argument(
        "--display-name",
        default=None,
        help="Jupyter kernel display name (default: same as env name)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned action without executing",
    )


def _add_unregister_args(p) -> None:
    """Add ``env unregister`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name to unregister")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned action without executing",
    )


def _add_activate_args(p) -> None:
    """Add ``env activate`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name to activate")


def _add_export_args(p) -> None:
    """Add ``export`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name to export")
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument(
        "--to-mamba-spec",
        action="store_true",
        help="Export as mamba spec YAML (default)",
    )
    fmt.add_argument(
        "--to-requirements", action="store_true", help="Export as pip requirements list"
    )
    fmt.add_argument(
        "--to-wrangler-spec", action="store_true", help="Export as wrangler spec YAML"
    )
    p.add_argument(
        "-o",
        "--output",
        default="-",
        metavar="FILE",
        help="Output file (default: '-' for stdout)",
    )
    p.add_argument(
        "--pantry",
        default=None,
        help="Restrict shelf search to a single pantry directory",
    )


def _add_status_args(p) -> None:
    """Add ``status`` specific arguments to *p*."""
    p.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )


def _add_doctor_args(p) -> None:
    """Add ``doctor`` specific arguments to *p*."""
    p.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )


# -- data sub-args -------------------------------------------------------------


def _add_data_ls_args(p) -> None:
    """Add ``data ls`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )


def _add_data_download_args(p) -> None:
    """Add ``data download`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "--select",
        default=".*",
        metavar="REGEX",
        help="Select specific archives by REGEX (default: all)",
    )
    p.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip post-download checksum/manifest validation",
    )


def _add_data_unpack_args(p) -> None:
    """Add ``data unpack`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "--no-unpack-existing",
        action="store_true",
        help="Skip archives that are already unpacked",
    )
    syms = p.add_mutually_exclusive_group()
    syms.add_argument(
        "--symlinks",
        dest="symlinks",
        action="store_true",
        default=True,
        help="Create symlinks at install_data locations (default)",
    )
    syms.add_argument(
        "--no-symlinks",
        dest="symlinks",
        action="store_false",
        help="Do not create symlinks at install_data locations",
    )


def _add_data_pack_args(p) -> None:
    """Add ``data pack`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")


def _add_data_clean_args(p) -> None:
    """Add ``data clean`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "mode",
        nargs="?",
        choices=["archived", "unpacked", "both"],
        default="both",
        help="What to delete: archived, unpacked, or both (default: both)",
    )
