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
from nb_wrangler.constants import DEFAULT_ARCHIVE_FORMAT
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
from nb_wrangler.utils import yaml_dumps, sha256_file

# env subcommands implemented vs. stubbed for later phases
_ENV_CREATE = "create"
_ENV_SAVE = "save"
_ENV_RESTORE = "restore"
_ENV_NOT_IMPLEMENTED = [
    "ls",
    "info",
    "rm",
    "install",
    "uninstall",
    "relock",
    "ensure",
    "register",
    "unregister",
]

# top-level groups (only env has real subcommands in Phases 1-3)
_TOP_LEVEL_STUBS = ["var", "data", "export", "status", "doctor"]


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

    for cmd in _ENV_NOT_IMPLEMENTED:
        env_sub.add_parser(cmd, help=f"({cmd} -- not yet implemented)")


def _add_stub_groups(subparsers) -> None:
    """Add top-level stub groups for future phases."""
    for group in _TOP_LEVEL_STUBS:
        subparsers.add_parser(group, help=f"({group} -- not yet implemented)")


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


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _dispatch_env(args, parser) -> int:
    """Route ``ppe env`` subcommands."""
    if not args.env_command:
        print(
            "ppe env: sub-command required. Use one of: "
            + ", ".join([_ENV_CREATE, _ENV_SAVE, _ENV_RESTORE] + _ENV_NOT_IMPLEMENTED)
        )
        return 0
    if args.env_command == _ENV_CREATE:
        return _cmd_env_create(args)
    if args.env_command == _ENV_SAVE:
        return _cmd_env_save(args)
    if args.env_command == _ENV_RESTORE:
        return _cmd_env_restore(args)
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


if __name__ == "__main__":
    sys.exit(main())
