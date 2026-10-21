"""env create subcommand: seed, build, and persist environments.

Every ``hubenv create`` invocation (all five ``--from-*`` sources) now
performs the essentials of bringing an environment into a usable state:

1. Build the live environment (``mamba create``), or verify an already-installed
   environment exists for ``--from-existing-env``.
2. Persist the essentials — write the canonical shelf spec and register the
   Jupyter kernel — so the environment is fully set up for a future session.

Users who only need a throwaway live environment (CI, scratch) pass
``--ephemeral`` to skip step 2 entirely.

Note that "persist" here means the shelf spec + kernel only — it does NOT
create an archive ``can``.  A shelf with a spec but no can is *not*
restorable and shows as "spec-only" in ``status``/``ls``/``info``.  Two ways
to archive:

* pass ``--save`` to ``env create`` to pack the can immediately, or
* run ``hubenv save NAME`` later (the suggested next step).

The heavy, potentially slow step remains explicit and separate:

* ``hubenv relock`` — re-curate the spec / refresh lock files
"""

import tempfile
from pathlib import Path
from typing import Optional

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.hubenv._common import (
    HubenvError,
    get_logger,
    print_exports,
    print_no_writable_pantry,
)
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import save_hubenv_spec
from nb_wrangler.hubenv.env_save import _do_save
from nb_wrangler.hubenv.seeds import (
    seed_from_empty,
    seed_from_existing_env,
    seed_from_mamba_spec,
    seed_from_requirements,
    seed_from_wrangler_spec,
)
from nb_wrangler.utils import yaml_dumps


def cmd_env_create(args) -> int:
    """Handle ``hubenv create``: build the live env, then persist essentials."""
    _probe_target(args)
    seed = _seed(args)
    # Source-derived name (e.g. --from-existing-env without --name) lands
    # on args.name only after the seed is built; downstream steps all
    # read it from there.
    args.name = seed["name"]

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

    rc = _persist_essentials(args, seed)
    if rc != 0:
        return rc
    if args.save:
        return _save_after_create(args)
    print_save_hint(args.name)
    return 0


def _probe_target(args) -> None:
    """Run the target existence probe before any seed work (RE-03).

    Runs even under ``--dry-run`` so the cheap probe precedes the slower
    ``mamba env export`` / ``pip freeze`` seed steps.  Skipped when the
    name is ``None`` (source-derived name flows resolve it after the
    seed build).  Non-fatal: creation proceeds and ``create_environment``
    reports the real outcome.
    """
    name = args.name
    if not name:
        return
    if EnvironmentManager().environment_exists(name):
        get_logger().info(f"Environment '{name}' already exists.")


def _seed(args) -> dict:
    """Build the seed dict, converting probe failures into a clean error.

    ``build_seed_dict`` raises ``ValueError`` / ``OSError`` when a seed source
    cannot be read (e.g. ``mamba env export`` or ``pip freeze`` fails).  Those
    are wrapped in a :class:`HubenvError` so ``cli.main()`` prints a clean
    message and exits 1 instead of leaking a raw traceback (RE-03).
    """
    try:
        return build_seed_dict(args)
    except (ValueError, OSError) as exc:
        raise HubenvError(
            f"Failed to seed spec for '{args.name}': {exc}", exit_code=1
        ) from exc


def build_seed_dict(args) -> dict:
    """Build the seeded mamba-spec dict from the chosen source."""
    name = args.name
    python = args.python
    if (args.from_empty or args.from_requirements) and name is None:
        raise HubenvError(
            "--name is required for --from-empty and --from-requirements",
            exit_code=1,
        )
    if args.from_empty:
        return seed_from_empty(name, python)
    if args.from_requirements:
        return seed_from_requirements(name, args.from_requirements, python)
    if args.from_mamba_spec:
        return seed_from_mamba_spec(name, args.from_mamba_spec)
    if args.from_wrangler_spec:
        return seed_from_wrangler_spec(name, args.from_wrangler_spec, python)
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


def _save_after_create(args) -> int:
    """Archive the just-created env into a pantry can (``--save``)."""
    rc = _do_save(PantryStore(), args.name, args.pantry, force=False)
    if rc == 0:
        print(f"Environment '{args.name}' is archived and restorable.")
    return rc


def print_save_hint(name: str) -> None:
    """Remind the user that the env is not yet archived."""
    print(
        f"Not archived yet. Run `hubenv save {name}` " f"to create the restoreable can."
    )


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
