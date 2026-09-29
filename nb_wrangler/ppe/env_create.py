"""env create subcommand: seed, install, and register environments."""

import sys
import tempfile
from pathlib import Path
from typing import Optional

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.pantry import NbwShelf
from nb_wrangler.ppe._common import (
    ensure_config,
    print_exports,
    print_no_writable_pantry,
)
from nb_wrangler.ppe.config import PpeConfig
from nb_wrangler.ppe.env_spec import save_ppe_spec
from nb_wrangler.ppe.seeds import (
    seed_from_empty,
    seed_from_existing_env,
    seed_from_mamba_spec,
    seed_from_notebooks,
    seed_from_requirements,
    seed_from_wrangler_spec,
)
from nb_wrangler.utils import yaml_dumps

from nb_wrangler.constants import DEFAULT_ARCHIVE_FORMAT


def cmd_env_create(args) -> int:
    """Handle ``ppe env create``."""
    ensure_config()

    seed = build_seed_dict(args)
    spec_yaml = yaml_dumps(seed)

    if args.dry_run:
        print(spec_yaml)
        return 0

    if args.from_existing_env:
        return import_existing_env(args, seed, spec_yaml)

    return install_environment(args.name, spec_yaml)


def build_seed_dict(args) -> dict:
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
    if args.from_existing_env:
        return seed_from_existing_env(name, args.from_existing_env, python)
    # Should not reach here due to mutually-exclusive required group
    raise ValueError("No seed source specified")


def import_existing_env(args, seed, spec_yaml) -> int:
    """Onboard an existing mamba env into the PPE lifecycle.

    The env is already installed; we do *not* call
    ``EnvironmentManager.create_environment``.  Instead we persist the
    shadow spec, register the kernel, and write a shelf spec so that
    ``save``/``restore``/``ls`` work immediately.
    """
    config = PpeConfig()
    em = EnvironmentManager()

    if not em.environment_exists(args.from_existing_env):
        print(
            f"Error: environment '{args.from_existing_env}' " f"not found in mamba.",
            file=sys.stderr,
        )
        return 1

    save_ppe_spec(config, args.name, seed)

    display_name = args.display_name or args.name
    em.register_environment(args.name, display_name, {})

    write_shelf_spec(config, args.name, spec_yaml, args.pantry)

    print_exports(args.name, config)
    print(f"Imported environment '{args.from_existing_env}' as '{args.name}'.")
    return 0


def write_shelf_spec(
    config: PpeConfig, name: str, spec_yaml: str, pantry: Optional[str]
) -> None:
    """Write the wrangler spec into the first writable pantry shelf.

    A friendly error is printed (and nothing happens) when no pantry
    is writable; onboarding still succeeds because the shadow spec was
    already persisted.
    """
    target = config.target_pantry(pantry)
    if target is None:
        print_no_writable_pantry(pantry)
        return
    shelf = NbwShelf(target / "shelves" / name, pantry_path=target)
    shelf.path.mkdir(parents=True, exist_ok=True)
    shelf.spec_path.write_text(spec_yaml)


def install_environment(name: str, spec_yaml: str) -> int:
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


# Backward-compat re-exports


def _cmd_env_create(args) -> int:
    """Backward-compat alias for ``cmd_env_create``."""
    return cmd_env_create(args)


def _build_seed_dict(args) -> dict:
    """Backward-compat alias for ``build_seed_dict``."""
    return build_seed_dict(args)


def _import_existing_env(args, seed, spec_yaml) -> int:
    """Backward-compat alias for ``import_existing_env``."""
    return import_existing_env(args, seed, spec_yaml)


def _write_shelf_spec(config, name, spec_yaml, pantry) -> None:
    """Backward-compat alias for ``write_shelf_spec``."""
    write_shelf_spec(config, name, spec_yaml, pantry)


def _install_environment(name: str, spec_yaml: str) -> int:
    """Backward-compat alias for ``install_environment``."""
    return install_environment(name, spec_yaml)


# Silence unused warnings
_ = DEFAULT_ARCHIVE_FORMAT
