"""env create subcommand: seed, build, and persist environments.

Every ``hubenv env create`` invocation (all five ``--from-*`` sources) now
performs the essentials of bringing an environment into a usable state:

1. Build the live environment (``mamba create``), or verify an already-installed
   environment exists for ``--from-existing-env``.
2. Persist the essentials — write the canonical shelf spec and register the
   Jupyter kernel — so the environment is fully set up for a future session.

Users who only need a throwaway live environment (CI, scratch) pass
``--ephemeral`` to skip step 2 entirely.

The heavy, potentially slow steps remain explicit and separate:
* ``hubenv env save``   — archive the live env into a pantry ``can``
* ``hubenv env relock`` — re-curate the spec / refresh lock files
"""

import tempfile
from pathlib import Path
from typing import Optional

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.hubenv._common import (
    get_logger,
    print_exports,
    print_no_writable_pantry,
)
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import save_hubenv_spec
from nb_wrangler.hubenv.seeds import (
    seed_from_empty,
    seed_from_existing_env,
    seed_from_mamba_spec,
    seed_from_requirements,
    seed_from_wrangler_spec,
)
from nb_wrangler.utils import yaml_dumps


def cmd_env_create(args) -> int:
    """Handle ``hubenv env create``: build the live env, then persist essentials."""
    seed = build_seed_dict(args)

    if args.dry_run:
        print(yaml_dumps(seed))
        return 0

    if args.from_existing_env:
        rc = _onboard_existing_env(args)
    else:
        rc = install_environment(args.name, yaml_dumps(seed))
    if rc != 0:
        return rc

    if args.ephemeral:
        get_logger().info(
            f"Environment '{args.name}' is ready (ephemeral). "
            "No shelf spec was written and no kernel was registered."
        )
        return 0

    return _persist_essentials(args, seed)


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
    if args.from_existing_env:
        return seed_from_existing_env(name, args.from_existing_env, python)
    # Should not reach here due to mutually-exclusive required group
    raise ValueError("No seed source specified")


def _onboard_existing_env(args) -> int:
    """Verify the source environment already exists in mamba. No side effects."""
    em = EnvironmentManager()
    if not em.environment_exists(args.from_existing_env):
        get_logger().error(
            f"Environment '{args.from_existing_env}' not found in mamba."
        )
        return 1
    return 0


def _persist_essentials(args, seed) -> int:
    """Write the shelf spec, register the kernel, and print exports.

    Shared by all five sources so the default is a complete, usable, and
    restorable environment.
    """
    store = _build_store(args)
    if store is None:
        return 1
    save_hubenv_spec(store, args.name, seed)

    em = EnvironmentManager()
    display_name = args.display_name or args.name
    em.register_environment(args.name, display_name, {})

    print_exports(args.name, store)
    get_logger().info(
        f"Environment '{args.name}' is ready. Kernel '{display_name}' "
        f"registered. Shelf spec: {store.shelf_spec_path(args.name)}"
    )
    return 0


def _build_store(args) -> Optional[PantryStore]:
    """Resolve a writable :class:`PantryStore`, honoring ``--pantry``.

    Returns ``None`` (after printing a clear error) when no writable pantry
    is available, so the caller can exit non-zero.
    """
    if args.pantry:
        store = PantryStore(paths=[Path(args.pantry)])
    else:
        store = PantryStore()
    if store.target_pantry(None) is None:
        print_no_writable_pantry(args.pantry)
        return None
    return store


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
