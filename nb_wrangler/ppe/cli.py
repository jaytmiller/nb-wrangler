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
from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.logger import WranglerLogger
from nb_wrangler.pantry import NbwPantrySet
from nb_wrangler.ppe.config import PpeConfig
from nb_wrangler.ppe.seeds import (
    seed_from_empty,
    seed_from_mamba_spec,
    seed_from_notebooks,
    seed_from_requirements,
    seed_from_wrangler_spec,
)
from nb_wrangler.utils import yaml_dumps

# env subcommands implemented in Phase 1 vs. stubbed for later phases
_ENV_CREATE = "create"
_ENV_NOT_IMPLEMENTED = [
    "ls", "info", "restore", "save", "rm",
    "install", "uninstall", "relock", "ensure",
    "register", "unregister",
]

# top-level groups (only env has real subcommands in Phase 1)
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
    """Add the ``env`` subcommand group with create + stubs."""
    env_parser = subparsers.add_parser("env", help="Environment management")
    env_sub = env_parser.add_subparsers(dest="env_command")

    create = env_sub.add_parser("create", help="Create a new environment")
    _add_create_args(create)

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
        "--from-requirements", nargs="*", metavar="FILE", default=[],
        help="Seed from one or more requirements files",
    )
    sources.add_argument(
        "--from-mamba-spec", metavar="FILE",
        help="Seed from a mamba/conda spec YAML file",
    )
    sources.add_argument(
        "--from-wrangler-spec", metavar="FILE",
        help="Seed from a wrangler spec YAML file",
    )
    sources.add_argument(
        "--from-notebooks", nargs="*", metavar="PATH", default=[],
        help="Seed from Python imports in notebook files",
    )
    p.add_argument("--name", required=True, help="Environment name")
    p.add_argument("--display-name", default=None, help="Jupyter kernel display name")
    p.add_argument("--python", default=None, help="Python version (e.g. 3.11)")
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print the seeded spec without installing",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _dispatch_env(args, parser) -> int:
    """Route ``ppe env`` subcommands."""
    if not args.env_command:
        print(
            "ppe env: sub-command required. Use one of: "
            + ", ".join([_ENV_CREATE] + _ENV_NOT_IMPLEMENTED)
        )
        return 0
    if args.env_command == _ENV_CREATE:
        return _cmd_env_create(args)
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


if __name__ == "__main__":
    sys.exit(main())