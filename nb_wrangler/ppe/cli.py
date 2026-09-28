"""ppe - Persistent Platform Environments CLI for nb-wrangler.

Thin wrapper over nb-wrangler that exposes a ``conda``/``uv``-style
subcommand-group CLI for managing user-installed persistent environments.
"""

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Optional

from nb_wrangler.config import WranglerConfig, set_args_config, get_args_config
from nb_wrangler.constants import (
    DEFAULT_ARCHIVE_FORMAT,
    NBW_MAMBA_CMD,
    NBW_PIP_CMD,
)
from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.logger import WranglerLogger
from nb_wrangler.pantry import NbwShelf
from nb_wrangler.ppe.config import PpeConfig
from nb_wrangler.ppe.seeds import (
    seed_from_empty,
    seed_from_mamba_spec,
    seed_from_notebooks,
    seed_from_requirements,
    seed_from_wrangler_spec,
)
from nb_wrangler.utils import yaml_dumps, sha256_file, get_yaml, writelines

# env subcommands implemented vs. stubbed for later phases
_ENV_CREATE = "create"
_ENV_SAVE = "save"
_ENV_RESTORE = "restore"
_ENV_LS = "ls"
_ENV_INFO = "info"
_ENV_ENSURE = "ensure"
_ENV_REGISTER = "register"
_ENV_UNREGISTER = "unregister"

# top-level groups stubbed for future phases (var is implemented in Phase 8)
_TOP_LEVEL_STUBS = ["data", "export", "status", "doctor"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for the ``ppe`` command."""
    parser = build_parser()
    args, _ = parser.parse_known_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "env":
        return _dispatch_env(args, parser)
    if args.command == "var":
        return _dispatch_var(args, parser)
    return _cmd_not_implemented(args.command)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``ppe`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="ppe",
        description=(
            "Persistent Platform Environments CLI for nb-wrangler. "
            "Manage user-installed environments with archive/restore support."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    _add_env_subcommands(subparsers)
    _add_var_subcommands(subparsers)
    _add_stub_groups(subparsers)
    return parser


def _add_env_subcommands(subparsers) -> None:
    """Add the ``env`` subcommand group with create, save, restore + stubs."""
    env_parser = subparsers.add_parser("env", help="Environment management")
    env_sub = env_parser.add_subparsers(dest="env_command")

    create = env_sub.add_parser("create", help="Create a new environment")
    _add_create_args(create)

    save = env_sub.add_parser(
        "save", help="Pack a live environment into a pantry archive"
    )
    _add_save_args(save)

    restore = env_sub.add_parser(
        "restore", help="Unpack a saved environment and register kernel"
    )
    _add_restore_args(restore)

    ls = env_sub.add_parser("ls", help="List live envs and pantry shelves")
    _add_ls_args(ls)

    info = env_sub.add_parser("info", help="Show detailed info for an environment")
    _add_info_args(info)

    install = env_sub.add_parser(
        "install", help="Install packages into a live environment"
    )
    _add_install_args(install)

    uninstall = env_sub.add_parser(
        "uninstall", help="Uninstall packages from a live environment"
    )
    _add_uninstall_args(uninstall)

    relock = env_sub.add_parser(
        "relock", help="Re-curate locks and validate the implicit spec"
    )
    _add_relock_args(relock)

    rm = env_sub.add_parser("rm", help="Delete environments from live and/or archive")
    _add_rm_args(rm)

    ensure = env_sub.add_parser(
        _ENV_ENSURE, help="Idempotently ensure an env is available (live or restored)"
    )
    _add_ensure_args(ensure)

    register = env_sub.add_parser(
        _ENV_REGISTER, help="Register Jupyter kernel for an environment"
    )
    _add_register_args(register)

    unregister = env_sub.add_parser(
        _ENV_UNREGISTER, help="Unregister Jupyter kernel for an environment"
    )
    _add_unregister_args(unregister)


def _add_stub_groups(subparsers) -> None:
    """Add top-level stub groups for future phases."""
    for group in _TOP_LEVEL_STUBS:
        subparsers.add_parser(group, help=f"({group} -- not yet implemented)")


def _add_var_subcommands(subparsers) -> None:
    """Add the ``var`` subcommand group (Phase 8: env var management)."""
    var_parser = subparsers.add_parser(
        "var", help="Manage environment variables for an env"
    )
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


def _add_var_add_args(p) -> None:
    """Add ``var add`` specific arguments to *p*."""
    p.add_argument("name", help="Environment name")
    p.add_argument(
        "assignments",
        nargs="+",
        metavar="VAR=VALUE",
        help="One or more VAR=VALUE assignments to add/update",
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
        "--from-notebooks",
        nargs="*",
        metavar="PATH",
        default=[],
        help="Seed from Python imports in notebook files",
    )
    p.add_argument("--name", required=True, help="Environment name")
    p.add_argument("--display-name", default=None, help="Jupyter kernel display name")
    p.add_argument("--python", default=None, help="Python version (e.g. 3.11)")
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
        help="Remove only from live envs (NBW_ROOT/envs/)",
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


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _dispatch_env(args, parser) -> int:
    """Route ``ppe env`` subcommands."""
    if not args.env_command:
        print(
            "ppe env: sub-command required. Use one of: "
            + ", ".join(
                [
                    _ENV_CREATE,
                    _ENV_SAVE,
                    _ENV_RESTORE,
                    _ENV_LS,
                    _ENV_INFO,
                    "rm",
                    _ENV_ENSURE,
                    _ENV_REGISTER,
                    _ENV_UNREGISTER,
                ]
            )
        )
        return 0
    if args.env_command == _ENV_CREATE:
        return _cmd_env_create(args)
    if args.env_command == _ENV_SAVE:
        return _cmd_env_save(args)
    if args.env_command == _ENV_RESTORE:
        return _cmd_env_restore(args)
    if args.env_command == _ENV_LS:
        return _cmd_env_ls(args)
    if args.env_command == _ENV_INFO:
        return _cmd_env_info(args)
    if args.env_command == "install":
        return _cmd_env_install(args)
    if args.env_command == "uninstall":
        return _cmd_env_uninstall(args)
    if args.env_command == "relock":
        return _cmd_env_relock(args)
    if args.env_command == "rm":
        return _cmd_env_rm(args)
    if args.env_command == _ENV_ENSURE:
        return _cmd_env_ensure(args)
    if args.env_command == _ENV_REGISTER:
        return _cmd_env_register(args)
    if args.env_command == _ENV_UNREGISTER:
        return _cmd_env_unregister(args)
    return _cmd_not_implemented(args.env_command)


def _cmd_not_implemented(name: str) -> int:
    """Print a clear 'not yet implemented' message and exit 2."""
    print(
        f"ppe: '{name}' is not yet implemented. "
        f"See docs/plan-b/phases/ for the roadmap.",
        file=sys.stderr,
    )
    return 2


# ---------------------------------------------------------------------------
# var (env vars for PPE environments)
# ---------------------------------------------------------------------------


def _dispatch_var(args, parser) -> int:
    """Route ``ppe var`` subcommands."""
    if not args.var_command:
        print(
            "ppe var: sub-command required. Use one of: ls, add, rm",
            file=sys.stderr,
        )
        return 0
    if args.var_command == "ls":
        return _cmd_var_ls(args)
    if args.var_command == "add":
        return _cmd_var_add(args)
    if args.var_command == "rm":
        return _cmd_var_rm(args)
    return _cmd_not_implemented(args.var_command)


def _cmd_var_ls(args) -> int:
    """Handle ``ppe var ls NAME [GLOB...]``."""
    _ensure_config()
    config = PpeConfig()
    spec = _load_ppe_spec(config, args.name)
    env_vars = spec.get("environment_vars") or {}
    filtered = _filter_vars_by_glob(env_vars, args.globs)
    if args.format == "json":
        _print_var_ls_json(filtered, args.name)
    elif args.export:
        _print_var_ls_export(filtered)
    else:
        _print_var_ls_table(filtered, args.name)
    return 0


def _filter_vars_by_glob(env_vars: dict, globs: list[str]) -> dict:
    """Return a copy of *env_vars* filtered by *globs* (empty => all)."""
    import fnmatch

    if not globs:
        return dict(env_vars)
    return {
        k: v for k, v in env_vars.items() if any(fnmatch.fnmatch(k, g) for g in globs)
    }


def _print_var_ls_table(env_vars: dict, name: str) -> None:
    """Print a two-column VAR/VALUE table."""
    print(f"{'VAR':<20} VALUE")
    print("-" * 60)
    if not env_vars:
        print(f"(no environment variables defined for '{name}')")
        return
    for key in sorted(env_vars):
        print(f"{key:<20} {env_vars[key]}")


def _print_var_ls_export(env_vars: dict) -> None:
    """Print 'export VAR=VALUE' lines suitable for eval."""
    for key in sorted(env_vars):
        print(f"export {key}={env_vars[key]}")


def _print_var_ls_json(env_vars: dict, name: str) -> None:
    """Print ls results as JSON."""
    import json

    result = {
        "name": name,
        "environment_vars": dict(sorted(env_vars.items())),
    }
    print(json.dumps(result, indent=2))


def _cmd_var_add(args) -> int:
    """Handle ``ppe var add NAME VAR=VALUE...``."""
    _ensure_config()
    config = PpeConfig()
    try:
        updates = _parse_var_assignments(args.assignments)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    spec = _load_ppe_spec(config, args.name)
    env_vars = spec.get("environment_vars") or {}
    spec["environment_vars"] = env_vars
    env_vars.update(updates)
    _save_ppe_spec(config, args.name, spec)
    _refresh_kernel_vars(args.name, env_vars)
    _print_var_add_result(args.name, updates)
    return 0


def _parse_var_assignments(assignments: list[str]) -> dict[str, str]:
    """Parse ``VAR=VALUE`` strings, splitting on the first ``=``."""
    result: dict[str, str] = {}
    for item in assignments:
        if "=" not in item:
            raise ValueError(f"'{item}' is not a VAR=VALUE assignment")
        key, value = item.split("=", 1)
        result[key] = value
    return result


def _print_var_add_result(name: str, updates: dict[str, str]) -> None:
    """Print a summary of added/updated env vars."""
    for key in sorted(updates):
        print(f"Set {key}={updates[key]} for env '{name}'")
    print(f"Kernel refreshed for '{name}'.")


def _cmd_var_rm(args) -> int:
    """Handle ``ppe var rm NAME GLOB...``."""
    _ensure_config()
    config = PpeConfig()
    spec = _load_ppe_spec(config, args.name)
    env_vars = spec.get("environment_vars") or {}
    spec["environment_vars"] = env_vars
    removed = _remove_vars_by_glob(env_vars, args.globs)
    if not removed:
        print(f"No matching variables for {args.globs} in env '{args.name}'.")
        return 0
    _save_ppe_spec(config, args.name, spec)
    _refresh_kernel_vars(args.name, env_vars)
    _print_var_rm_result(args.name, removed)
    return 0


def _remove_vars_by_glob(env_vars: dict, globs: list[str]) -> list[str]:
    """Remove glob-matched entries in-place. Return removed var names."""
    import fnmatch

    to_remove = [k for k in env_vars if any(fnmatch.fnmatch(k, g) for g in globs)]
    for k in to_remove:
        del env_vars[k]
    return sorted(to_remove)


def _print_var_rm_result(name: str, removed: list[str]) -> None:
    """Print a summary of removed env vars."""
    for key in sorted(removed):
        print(f"Removed {key} from env '{name}'")
    print(f"Kernel refreshed for '{name}'.")


def _refresh_kernel_vars(name: str, env_vars: dict[str, str]) -> None:
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


# ---------------------------------------------------------------------------
# env create
# ---------------------------------------------------------------------------


def _ensure_config() -> WranglerConfig:
    """Return a global WranglerConfig, creating a minimal one if needed."""
    try:
        return get_args_config()
    except (AssertionError, AttributeError):
        config = WranglerConfig(workflows=[], repos_dir=Path("."), output_dir=Path("."))
        set_args_config(config)
        WranglerLogger.from_config(config)  # configure logging
        return config


def _build_seed_dict(args) -> dict:
    """Build the seeded mamba-spec dict from the chosen source."""
    name = args.name
    python = args.python
    if args.from_empty:
        return seed_from_empty(name, python)
    if args.from_requirements:
        return seed_from_requirements(name, args.from_requirements, python)
    if args.from_mamba_spec:
        return seed_from_mamba_spec(name, args.from_mamba_spec)
    if args.from_wrangler_spec:
        return seed_from_wrangler_spec(name, args.from_wrangler_spec)
    if args.from_notebooks:
        return seed_from_notebooks(name, args.from_notebooks, python)
    # Should not reach here due to mutually-exclusive required group
    raise ValueError("No seed source specified")


def _cmd_env_create(args) -> int:
    """Handle ``ppe env create``."""
    _ensure_config()

    seed = _build_seed_dict(args)
    spec_yaml = yaml_dumps(seed)

    if args.dry_run:
        print(spec_yaml)
        return 0

    return _install_environment(args.name, spec_yaml)


def _install_environment(name: str, spec_yaml: str) -> int:
    """Write the spec to a temp file and create the environment."""
    em = EnvironmentManager()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix=f"{name}-"
    ) as tmp:
        tmp.write(spec_yaml)
        tmp_path = Path(tmp.name)
    try:
        success = em.create_environment(name, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return 0 if success else 1


# ---------------------------------------------------------------------------
# env save
# ---------------------------------------------------------------------------


def _cmd_env_save(args) -> int:
    """Handle ``ppe env save``.

    Pack an installed environment into a pantry archive. Uses wrangler's
    NbwShelf.pack_environment routine for tarball creation.
    """
    _ensure_config()
    config = PpeConfig()

    target = config.target_pantry(args.pantry)
    if target is None:
        _print_no_writable_pantry(args.pantry)
        return 1

    em = EnvironmentManager()
    env_path = em.env_live_path(args.name)
    if not env_path.exists():
        print(
            f"Error: live environment '{args.name}' not found at {env_path}",
            file=sys.stderr,
        )
        return 1

    shelf = NbwShelf(target / "shelves" / args.name, pantry_path=target)
    can_path = shelf.env_archive_path(args.name, DEFAULT_ARCHIVE_FORMAT)

    if args.dry_run:
        print(f"shelf: {shelf.path}")
        print(f"can: {can_path}")
        print(f"live env: {env_path}")
        return 0

    if can_path.exists() and not args.force:
        print(
            f"Error: archive already exists at {can_path}. "
            f"Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    success = shelf.pack_environment(args.name, args.name, DEFAULT_ARCHIVE_FORMAT)
    if not success:
        return 1

    _persist_save_hash(shelf, can_path)
    print(f"Saved environment '{args.name}' to {can_path}")
    return 0


def _print_no_writable_pantry(forced_path: Optional[str]) -> None:
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


def _persist_save_hash(shelf: NbwShelf, can_path: Path) -> None:
    """Compute and persist a save-hash for idempotency checks."""
    save_hash = sha256_file(can_path)
    hash_file = shelf.archive_root / "last-save.sha256"
    shelf.archive_root.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(save_hash + "\n")


# ---------------------------------------------------------------------------
# env restore
# ---------------------------------------------------------------------------


def _cmd_env_restore(args) -> int:
    """Handle ``ppe env restore``.

    Unpack a saved can into NBW_ROOT and register a Jupyter kernel.
    Supports idempotency (skip if restored hash matches save hash).
    """
    _ensure_config()
    config = PpeConfig()

    matches = _find_restore_shelf(config, args)
    if matches is None:
        return 1
    if not matches:
        print(
            f"Error: no shelf '{args.name}' found in any pantry.",
            file=sys.stderr,
        )
        return 1

    pantry_path, shelf_path = matches[0]
    shelf = NbwShelf(shelf_path, pantry_path=pantry_path)
    can_path = shelf.env_archive_path(args.name, DEFAULT_ARCHIVE_FORMAT)

    if not can_path.exists():
        print(f"Error: no archive (can) found at {can_path}", file=sys.stderr)
        return 1

    # Idempotency check
    if not args.force:
        save_hash = _read_save_hash(shelf)
        restore_hash = _read_restore_hash(config, args.name)
        if save_hash and restore_hash and save_hash == restore_hash:
            print(
                f"Environment '{args.name}' already restored (idempotent skip). "
                f"Use --force to re-unpack."
            )
            _print_exports(args.name, config)
            return 0

    # Unpack
    success = shelf.unpack_environment(args.name, args.name, DEFAULT_ARCHIVE_FORMAT)
    if not success:
        return 1

    # Record restore-hash
    save_hash = _read_save_hash(shelf) or ""
    _record_restore_hash(config, args.name, save_hash)

    # Register kernel
    em = EnvironmentManager()
    em.register_environment(args.name, args.name, {})

    # Print exports for eval
    _print_exports(args.name, config)

    if args.at_boot:
        _write_at_boot_snippet(args.name)

    return 0


def _find_restore_shelf(config: PpeConfig, args) -> Optional[list[tuple[Path, Path]]]:
    """Find shelf(s) for restore, handling --pantry and multi-match."""
    if args.pantry:
        forced = Path(args.pantry)
        shelf_path = forced / "shelves" / args.name
        if shelf_path.exists():
            return [(forced, shelf_path)]
        print(
            f"Error: no shelf '{args.name}' found in pantry {forced}.",
            file=sys.stderr,
        )
        return None

    matches = config.find_shelves(args.name)
    if len(matches) > 1:
        print(
            f"Error: '{args.name}' found in multiple pantries:",
            file=sys.stderr,
        )
        for pantry, shelf_path in matches:
            print(f"  {shelf_path}", file=sys.stderr)
        print("Use --pantry to select a specific one.", file=sys.stderr)
        return None
    return matches


def _read_save_hash(shelf: NbwShelf) -> Optional[str]:
    """Read the save-hash from the shelf."""
    hash_file = shelf.archive_root / "last-save.sha256"
    if hash_file.exists():
        return hash_file.read_text().strip()
    return None


def _read_restore_hash(config: PpeConfig, name: str) -> Optional[str]:
    """Read the restore-hash for *name* from the live store."""
    hash_file = config.restore_hash_path(name)
    if hash_file.exists():
        return hash_file.read_text().strip()
    return None


def _record_restore_hash(config: PpeConfig, name: str, save_hash: str) -> None:
    """Persist the restore-hash for future idempotency checks."""
    hash_file = config.restore_hash_path(name)
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(save_hash + "\n")


def _print_exports(name: str, config: PpeConfig) -> None:
    """Print eval-able shell exports for environment activation."""
    print(f"export NBW_ACTIVE_ENV={name}")
    print(f"export NBW_ENV_ROOT={config.nbw_root / 'envs' / name}")


def _write_at_boot_snippet(name: str) -> None:
    """Write a guarded, idempotent snippet for startup restore."""
    snippet_dir = Path.home() / ".ppe"
    snippet_dir.mkdir(parents=True, exist_ok=True)
    snippet_path = snippet_dir / f"env-{name}.sh"

    snippet = (
        f"# ppe env ensure {name} - idempotent restore at boot\n"
        f'if [ -z "${{NBW_ACTIVE_ENV+set}}" ]; then\n'
        f'    export NBW_ACTIVE_ENV="{name}"\n'
        f"    ppe env ensure {name} 2>/dev/null || true\n"
        f"fi\n"
    )
    snippet_path.write_text(snippet)

    # Append source line to .bashrc if not already present
    bashrc = Path.home() / ".bashrc"
    marker = f"source ~/.ppe/env-{name}.sh"
    if not bashrc.exists() or marker not in bashrc.read_text():
        with bashrc.open("a") as f:
            f.write(f"\n# Added by ppe\n{marker}\n")
        print(f"Appended to {bashrc}: {marker}")
    print(f"At-boot snippet written to {snippet_path}")


# ---------------------------------------------------------------------------
# env ls
# ---------------------------------------------------------------------------


def _cmd_env_ls(args) -> int:
    """Handle ``ppe env ls`` — list live envs and pantry shelves."""
    _ensure_config()
    config = PpeConfig()

    pantry_dir = Path(args.pantry) if args.pantry else None
    patterns = args.patterns if args.patterns else [None]

    all_shelves = []
    for pattern in patterns:
        all_shelves.extend(config.list_shelves(glob_expr=pattern, pantry=pantry_dir))

    live_envs = config.list_live_envs()
    live_names = {e["name"] for e in live_envs}

    if args.format == "json":
        _print_ls_json(all_shelves, live_envs)
    else:
        _print_ls_table(all_shelves, live_names, args.all)

    _print_shadowing_warnings(all_shelves)
    return 0


def _print_ls_table(shelves: list[dict], live_names: set[str], show_all: bool) -> None:
    """Print a table of shelves and live envs."""
    seen: set[str] = set()
    print(f"{'NAME':<20} {'PANTRY':<30} {'STATUS':<8} {'HASH':<12} {'LIVE'}")
    print("-" * 80)
    for entry in shelves:
        name = entry["name"]
        if not show_all and name in seen:
            continue
        seen.add(name)
        writable = "r/o" if not entry["writable"] else ""
        hash_short = (entry["save_hash"] or "-")[:12]
        live_mark = "*" if name in live_names else ""
        print(
            f"{name:<20} {str(entry['pantry']):<30} {writable:<8} {hash_short:<12} {live_mark}"
        )
    for env in live_names - seen:
        print(f"{env:<20} {'<live>':<30} {'':<8} {'':<12} *")


def _print_ls_json(shelves: list[dict], live_envs: list[dict]) -> None:
    """Print ls results as JSON."""
    import json

    result = {
        "shelves": [
            {
                "name": s["name"],
                "pantry": str(s["pantry"]),
                "writable": s["writable"],
                "save_hash": s["save_hash"],
            }
            for s in shelves
        ],
        "live_envs": [{"name": e["name"], "path": str(e["path"])} for e in live_envs],
    }
    print(json.dumps(result, indent=2))


def _print_shadowing_warnings(shelves: list[dict]) -> None:
    """Warn when a name appears in multiple pantries."""
    from collections import defaultdict

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


# ---------------------------------------------------------------------------
# env info
# ---------------------------------------------------------------------------


def _cmd_env_info(args) -> int:
    """Handle ``ppe env info NAME`` — show detailed environment metadata."""
    _ensure_config()
    config = PpeConfig()

    pantry_dir = Path(args.pantry) if args.pantry else None
    shelves = config.list_shelves(glob_expr=args.name, pantry=pantry_dir)
    live_envs = config.list_live_envs()
    live_names = {e["name"] for e in live_envs}

    if not shelves and args.name not in live_names:
        print(
            f"Info: no shelf or live env named '{args.name}' found.",
            file=sys.stderr,
        )
        return 1

    if args.format == "json":
        _print_info_json(args.name, shelves, live_envs)
    else:
        _print_info_table(args.name, shelves, live_envs)

    _print_shadowing_warnings(shelves)
    return 0


def _print_info_table(name: str, shelves: list[dict], live_envs: list[dict]) -> None:
    """Print table-style info for *name*."""
    print(f"Environment: {name}")
    print()

    live_match = next((e for e in live_envs if e["name"] == name), None)
    if live_match:
        print(f"  Live env:    {live_match['path']} *")
    else:
        print("  Live env:    (not installed)")
    print()

    if not shelves:
        print("  No shelves found.")
        return

    for i, entry in enumerate(shelves):
        writable = "r/o" if not entry["writable"] else "r/w"
        hash_short = entry["save_hash"] or "none"
        print(f"  Shelf {i + 1}:")
        print(f"    Pantry:     {entry['pantry']}")
        print(f"    Path:       {entry['path']}")
        print(f"    Writable:   {writable}")
        print(f"    Save hash:  {hash_short}")
        print()


def _print_info_json(name: str, shelves: list[dict], live_envs: list[dict]) -> None:
    """Print JSON-style info for *name*."""
    import json

    result = {
        "name": name,
        "shelves": [
            {
                "name": s["name"],
                "pantry": str(s["pantry"]),
                "writable": s["writable"],
                "save_hash": s["save_hash"],
            }
            for s in shelves
        ],
        "live_env": next(
            (
                {"name": e["name"], "path": str(e["path"])}
                for e in live_envs
                if e["name"] == name
            ),
            None,
        ),
    }
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# env install / uninstall / relock  (Phase 5)
# ---------------------------------------------------------------------------


def _cmd_env_install(args) -> int:
    """Handle ``ppe env install``."""
    return _cmd_env_pkg_action(args, "install")


def _cmd_env_uninstall(args) -> int:
    """Handle ``ppe env uninstall``."""
    return _cmd_env_pkg_action(args, "uninstall")


def _cmd_env_pkg_action(args, action: str) -> int:
    """Shared install/uninstall handler."""
    _ensure_config()
    config = PpeConfig()
    em = EnvironmentManager()

    if not em.environment_exists(args.name):
        print(f"Error: live environment '{args.name}' not found.", file=sys.stderr)
        return 1

    if args.dry_run:
        return _pkg_dry_run(args, action)

    return _do_pkg_action(em, config, args, action)


def _do_pkg_action(em, config, args, action) -> int:
    """Execute the install/uninstall and update the implicit spec."""
    using = args.using
    if not _run_pkg_action(em, args.name, using, action, args.packages):
        return 1
    _update_and_save_spec(config, args.name, args.packages, action, using)
    _print_relock_suggestion(args.name, args.no_relock)
    return 0


def _run_pkg_action(em, name, using, action, packages) -> bool:
    """Run the installer command in the live env."""
    if using == "mamba":
        return _run_mamba_action(em, name, action, packages)
    return _run_pip_action(em, name, using, action, packages)


def _run_mamba_action(em, name, action, packages) -> bool:
    """Run a mamba install/remove action."""
    verb = "install" if action == "install" else "remove"
    cmd = f"{NBW_MAMBA_CMD} {verb} -n {name} -y {' '.join(packages)}"
    result = em.wrangler_run(cmd, check=False)
    return em.handle_result(result, f"Failed to {action} packages in '{name}': ")


def _run_pip_action(em, name, using, action, packages) -> bool:
    """Run a pip/uv install/uninstall action."""
    installer = _build_installer_str(using)
    verb = "install" if action == "install" else "uninstall"
    cmd = f"{installer} {verb} {' '.join(packages)}"
    result = em.env_run(name, cmd, check=False)
    return em.handle_result(result, f"Failed to {action} packages in '{name}': ")


def _build_installer_str(using) -> str:
    """Build the installer command prefix string for pip/uv operations."""
    if using == "uv":
        return "uv pip"
    if using == "pip":
        return "pip"
    return str(NBW_PIP_CMD)  # default (None)


# -- dry-run helpers ---------------------------------------------------------


def _pkg_dry_run(args, action) -> int:
    """Print dry-run output for install/uninstall."""
    cmd = _build_pkg_cmd(args, action)
    delta = _format_spec_delta(args.packages, action)
    print(f"Dry-run: would run: {cmd}")
    print(f"Spec delta: {delta}")
    return 0


def _build_pkg_cmd(args, action) -> str:
    """Build the planned installer command string."""
    verb = "install" if action == "install" else "uninstall"
    using = args.using
    if using == "mamba":
        return f"{NBW_MAMBA_CMD} {verb} -n {args.name} -y {' '.join(args.packages)}"
    installer = _build_installer_str(using)
    return f"{installer} {verb} {' '.join(args.packages)}"


def _format_spec_delta(packages, action) -> str:
    """Format the package delta for display."""
    sign = "+" if action == "install" else "-"
    return ", ".join(f"{sign} {p}" for p in packages)


def _print_relock_suggestion(name, no_relock) -> None:
    """Print the relock suggestion unless suppressed."""
    if not no_relock:
        print(
            f"Spec updated. Run `ppe env relock {name}` "
            f"to re-curate locks and validate."
        )


# -- implicit spec persistence -----------------------------------------------


def _load_ppe_spec(config, name) -> dict:
    """Load the implicit spec, or create a base spec if none exists."""
    spec_path = config.ppe_spec_path(name)
    if spec_path.exists():
        yaml = get_yaml()
        with open(spec_path) as f:
            return yaml.load(f)
    return seed_from_empty(name, None)


def _save_ppe_spec(config, name, spec) -> None:
    """Persist the implicit spec to disk."""
    spec_path = config.ppe_spec_path(name)
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(yaml_dumps(spec))


def _update_and_save_spec(config, name, packages, action, using) -> None:
    """Load, update, and persist the implicit spec."""
    spec = _load_ppe_spec(config, name)
    _update_spec_packages(spec, packages, action, using)
    _save_ppe_spec(config, name, spec)


# -- spec package list manipulation ------------------------------------------


def _update_spec_packages(spec, packages, action, using) -> None:
    """Update the spec's package list for the given action and installer."""
    deps = spec.setdefault("dependencies", [])
    if using != "mamba":
        pip_list = _get_or_create_pip_section(deps)
        if action == "install":
            _add_to_list(pip_list, packages)
        else:
            _remove_from_list(pip_list, packages)
    else:
        if action == "install":
            _add_conda_packages(deps, packages)
        else:
            _remove_conda_packages(deps, packages)


def _get_or_create_pip_section(deps) -> list:
    """Get or create the pip section list in dependencies."""
    for dep in deps:
        if isinstance(dep, dict) and "pip" in dep:
            return dep["pip"]
    pip_section: dict = {"pip": []}
    deps.append(pip_section)
    return pip_section["pip"]


def _add_to_list(lst, items) -> None:
    """Add items to a list if not already present."""
    for item in items:
        if item not in lst:
            lst.append(item)


def _remove_from_list(lst, items) -> None:
    """Remove items from a list by base name."""
    to_remove = {i.strip().lower() for i in items}
    lst[:] = [x for x in lst if _pkg_base_name(x) not in to_remove]


def _pkg_base_name(pkg: str) -> str:
    """Extract the base package name (without version constraints)."""
    for sep in ("=", "<", ">", "!", "~"):
        pkg = pkg.split(sep)[0]
    return pkg.strip().lower()


def _add_conda_packages(deps, packages) -> None:
    """Add conda packages to dependencies, before any pip section."""
    for pkg in packages:
        if pkg not in deps:
            idx = _pip_section_index(deps)
            deps.insert(idx, pkg)


def _pip_section_index(deps) -> int:
    """Return the index of the first dict in deps, or len(deps)."""
    for i, d in enumerate(deps):
        if isinstance(d, dict):
            return i
    return len(deps)


def _remove_conda_packages(deps, packages) -> None:
    """Remove conda packages from dependencies by base name."""
    to_remove = {p.strip().lower() for p in packages}
    deps[:] = [
        d for d in deps if not (isinstance(d, str) and _pkg_base_name(d) in to_remove)
    ]


# -- relock ------------------------------------------------------------------


def _cmd_env_relock(args) -> int:
    """Handle ``ppe env relock``."""
    _ensure_config()
    config = PpeConfig()
    em = EnvironmentManager()

    if not em.environment_exists(args.name):
        print(f"Error: live environment '{args.name}' not found.", file=sys.stderr)
        return 1

    return _do_relock(config, em, args.name, args.dry_run)


def _do_relock(config, em, name, dry_run) -> int:
    """Perform the relock operation."""
    spec = _load_ppe_spec(config, name)
    pip_list = _get_or_create_pip_section(spec.get("dependencies", []))

    if not pip_list:
        print(f"No pip packages to relock in '{name}'.")
        return 0

    compiled = _compile_pip_packages(em, name, pip_list)
    if compiled is None:
        return 1

    if dry_run:
        _print_relock_dry_run(name, compiled)
        return 0

    _apply_relock(config, name, spec, compiled)
    return 0


def _compile_pip_packages(em, name, packages):
    """Compile pip packages using uv pip compile. Returns resolved versions."""
    req_path = writelines(packages, em.nbw_temp_dir / f"relock_reqs_{name}.txt")
    output_path = em.nbw_temp_dir / f"relock_compiled_{name}.txt"

    cmd = (
        f"uv pip compile --output-file {output_path} "
        f"--python {sys.executable} --no-header --annotate {req_path}"
    )
    result = em.wrangler_run(cmd, check=False)

    if not em.handle_result(
        result, f"Failed to compile packages for relock of '{name}': "
    ):
        return None

    return _read_compiled_versions(output_path)


def _read_compiled_versions(filepath) -> list[str]:
    """Read compiled package versions from a requirements file."""
    if not filepath.exists():
        return []
    packages = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith(("#", "--")):
                packages.append(line)
    return packages


def _print_relock_dry_run(name, compiled) -> None:
    """Print dry-run output for relock."""
    print(f"Dry-run: would re-curate {len(compiled)} packages for '{name}':")
    for pkg in compiled:
        print(f"  {pkg}")


def _apply_relock(config, name, spec, compiled) -> None:
    """Persist the relocked spec."""
    pip_section = _get_or_create_pip_section(spec.get("dependencies", []))
    pip_section[:] = compiled
    _save_ppe_spec(config, name, spec)
    print(f"Relocked {len(compiled)} packages for '{name}'.")


# ---------------------------------------------------------------------------
# env rm  (Phase 6)
# ---------------------------------------------------------------------------


def _cmd_env_rm(args) -> int:
    """Handle ``ppe env rm`` — delete envs from live and/or archive."""
    _ensure_config()
    config = PpeConfig()

    target_type = args.target or "both"
    targets = _resolve_rm_targets(config, args.names, target_type, args.pantry)

    if not targets:
        print("No matching environments found.", file=sys.stderr)
        return 1

    if args.dry_run:
        _print_rm_plan(targets)
        return 0

    errors = _check_rm_readonly(targets)
    if errors:
        for msg in errors:
            print(f"Error: {msg}", file=sys.stderr)
        print(
            "Set NBW_PANTRY to a writable path or use --pantry <writable-path>.",
            file=sys.stderr,
        )
        return 1

    unsafe = [t for t in targets if not _is_safe_rm_path(t, config)]
    if unsafe:
        for t in unsafe:
            print(
                f"Error: refusing to delete path outside safe roots: {t['path']}",
                file=sys.stderr,
            )
        return 1

    _print_rm_plan(targets)

    if not args.yes:
        if not _prompt_rm_confirmation():
            print("Aborted.", file=sys.stderr)
            return 1

    return 1 if _do_rm(targets) > 0 else 0


def _resolve_rm_targets(config, patterns, target_type, pantry_filter):
    """Resolve NAME patterns against live envs and/or shelves."""
    targets = []
    if target_type in ("live", "both"):
        targets.extend(_resolve_live_targets(config, patterns))
    if target_type in ("archived", "both"):
        targets.extend(_resolve_shelf_targets(config, patterns, pantry_filter))
    return targets


def _resolve_live_targets(config, patterns):
    """Resolve patterns against live envs under NBW_ROOT/envs/."""
    live_envs = config.list_live_envs()
    return [
        {"type": "live", "name": e["name"], "path": e["path"], "writable": True}
        for e in live_envs
        if _matches_any_pattern(e["name"], patterns)
    ]


def _resolve_shelf_targets(config, patterns, pantry_filter):
    """Resolve patterns against shelves across pantries."""
    pantry_dir = Path(pantry_filter) if pantry_filter else None
    shelves = config.list_shelves(pantry=pantry_dir)
    return [
        {
            "type": "shelf",
            "name": s["name"],
            "path": s["path"],
            "pantry": s["pantry"],
            "writable": s["writable"],
        }
        for s in shelves
        if _matches_any_pattern(s["name"], patterns)
    ]


def _matches_any_pattern(name, patterns):
    """Check if *name* matches any of the glob *patterns*."""
    import fnmatch

    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _check_rm_readonly(targets):
    """Return list of error messages for read-only targets."""
    errors = []
    for t in targets:
        if t["type"] == "shelf" and not t["writable"]:
            errors.append(
                f"cannot delete '{t['name']}' from read-only pantry: {t['pantry']}"
            )
    return errors


def _is_safe_rm_path(target, config):
    """Check that a resolved rm target path is under a safe root."""
    path = target["path"].resolve()
    if target["type"] == "live":
        safe_root = (config.nbw_root / "envs").resolve()
        return path.is_relative_to(safe_root)
    for pantry in config.pantry_dirs:
        safe_root = (pantry / "shelves").resolve()
        if path.is_relative_to(safe_root):
            return True
    return False


def _print_rm_plan(targets):
    """Print the planned deletions."""
    print("The following will be removed:")
    for t in targets:
        if t["type"] == "live":
            print(f"  [live]   {t['name']:<20} -> {t['path']}")
        else:
            print(f"  [shelf]  {t['name']:<20} -> {t['path']}  ({t['pantry']})")


def _prompt_rm_confirmation():
    """Prompt for confirmation. Returns True if confirmed."""
    try:
        response = input("Proceed? (y/N): ").strip().lower()
    except EOFError:
        return False
    return response in ("y", "yes")


def _do_rm(targets):
    """Delete the resolved targets. Returns number of failures."""
    import shutil

    failures = 0
    for t in targets:
        path = t["path"]
        if not path.exists():
            print(f"Already gone: {t['type']} '{t['name']}'")
            continue
        try:
            shutil.rmtree(path)
            print(f"Removed {t['type']} '{t['name']}' at {path}")
        except OSError as e:
            print(f"Warning: could not remove {t['name']}: {e}", file=sys.stderr)
            failures += 1
    _cleanup_empty_shelf_dirs(targets)
    return failures


def _cleanup_empty_shelf_dirs(targets):
    """Best-effort removal of now-empty shelves/ directories."""
    import shutil

    seen = set()
    for t in targets:
        if t["type"] != "shelf":
            continue
        shelves_dir = t["pantry"] / "shelves"
        if shelves_dir in seen:
            continue
        seen.add(shelves_dir)
        if shelves_dir.exists():
            try:
                if not list(shelves_dir.iterdir()):
                    shutil.rmtree(shelves_dir)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# env ensure / register / unregister  (Phase 7)
# ---------------------------------------------------------------------------


class _EnsureArgs:
    """Minimal args namespace for delegating to _cmd_env_restore."""

    def __init__(self, name: str, pantry: Optional[str] = None):
        self.name = name
        self.pantry = pantry
        self.force = False
        self.at_boot = False


def _cmd_env_ensure(args) -> int:
    """Handle ``ppe env ensure`` — idempotent ensure an env is available.

    1. If a live env exists → no-op.
    2. Else if an archive shelf exists → restore it (reuse Phase 3 restore).
    3. Else → error with create-suggestion, exit non-zero.
    """
    _ensure_config()
    config = PpeConfig()
    em = EnvironmentManager()

    # 1. Live env exists → no-op
    if em.environment_exists(args.name):
        print(f"Environment '{args.name}' is already live (idempotent skip).")
        _print_exports(args.name, config)
        return 0

    # 2. Look for a shelf to restore
    matches = _find_restore_shelf(config, _EnsureArgs(args.name, args.pantry))
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

    restore_args = _EnsureArgs(args.name, args.pantry)
    return _cmd_env_restore(restore_args)


def _cmd_env_register(args) -> int:
    """Handle ``ppe env register`` — (re)register the Jupyter kernel."""
    _ensure_config()
    em = EnvironmentManager()

    display_name = args.display_name or args.name

    if args.dry_run:
        print(f"Dry-run: would register kernel '{args.name}' as '{display_name}'")
        return 0

    success = em.register_environment(args.name, display_name, {})
    if success:
        print(f"Registered environment '{args.name}' as kernel '{display_name}'.")
        _print_exports(args.name, PpeConfig())
        return 0
    return 1


def _cmd_env_unregister(args) -> int:
    """Handle ``ppe env unregister`` — remove the Jupyter kernel spec."""
    _ensure_config()
    em = EnvironmentManager()

    if args.dry_run:
        print(f"Dry-run: would unregister kernel '{args.name}'")
        return 0

    em.unregister_environment(args.name)
    print(f"Unregistered Jupyter kernel '{args.name}' (if it existed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
