"""env create subcommand: seed, install, and register environments."""

import tempfile
from pathlib import Path

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.hubenv._common import get_logger, print_exports
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import save_hubenv_spec
from nb_wrangler.hubenv.seeds import (
    seed_from_empty,
    seed_from_existing_env,
    seed_from_mamba_spec,
    seed_from_notebooks,
    seed_from_requirements,
    seed_from_wrangler_spec,
)
from nb_wrangler.utils import yaml_dumps


def cmd_env_create(args) -> int:
    """Handle ``hubenv env create``."""
    seed = build_seed_dict(args)
    spec_yaml = yaml_dumps(seed)

    if args.dry_run:
        print(spec_yaml)
        return 0

    if args.from_existing_env:
        return import_existing_env(args, seed)

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


def import_existing_env(args, seed) -> int:
    """Onboard an existing mamba env into the PPE lifecycle.

    The env is already installed; we do *not* call
    ``EnvironmentManager.create_environment``.  Instead we persist the
    shelf spec (the canonical ``nbw-wrangler-spec.yaml`` in the shelf),
    register the kernel, and print activation exports.
    """
    config = PantryStore()
    em = EnvironmentManager()

    if not em.environment_exists(args.from_existing_env):
        get_logger().error(
            f"Environment '{args.from_existing_env}' not found in mamba."
        )
        return 1

    save_hubenv_spec(config, args.name, seed)

    display_name = args.display_name or args.name
    em.register_environment(args.name, display_name, {})

    print_exports(args.name, config)
    print(f"Imported environment '{args.from_existing_env}' as '{args.name}'.")
    return 0


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
