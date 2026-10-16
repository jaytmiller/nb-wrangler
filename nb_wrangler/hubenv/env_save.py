"""env save subcommand: pack a live environment into a pantry archive."""

from typing import Optional

from nb_wrangler.constants import DEFAULT_ARCHIVE_FORMAT
from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.pantry import NbwShelf
from nb_wrangler.hubenv._common import get_logger, print_no_writable_pantry
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.utils import sha256_file


def cmd_env_save(args) -> int:
    """Handle ``hubenv env save``.

    Pack an installed environment into a pantry archive. Uses wrangler's
    NbwShelf.pack_environment routine for tarball creation.
    """
    config = PantryStore()
    return _do_save(
        config, args.name, args.pantry, force=args.force, dry_run=args.dry_run
    )


def _do_save(
    config: PantryStore,
    name: str,
    pantry: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    """Pack the live env *name* into a pantry can, writing the save hash.

    Shared by ``env save`` and ``env create --save``.  Returns the exit code:
    0 on success, 1 on any failure (no writable pantry, live env missing,
    existing can without *force*, or pack failure).
    """
    target = config.target_pantry(pantry)
    if target is None:
        print_no_writable_pantry(pantry)
        return 1

    em = EnvironmentManager()
    env_path = em.env_live_path(name)
    if not env_path.exists():
        get_logger().error(f"Live environment '{name}' not found at {env_path}")
        return 1

    shelf = NbwShelf(target / "shelves" / name, pantry_path=target)
    can_path = shelf.env_archive_path(name, DEFAULT_ARCHIVE_FORMAT)

    if dry_run:
        print(f"shelf: {shelf.path}")
        print(f"can: {can_path}")
        print(f"live env: {env_path}")
        return 0

    if can_path.exists() and not force:
        get_logger().error(
            f"Archive already exists at {can_path}. Use --force to overwrite."
        )
        return 1

    success = shelf.pack_environment(name, name, DEFAULT_ARCHIVE_FORMAT)
    if not success:
        return 1

    persist_save_hash(shelf, can_path)
    print(f"Saved environment '{name}' to {can_path}")
    return 0


def persist_save_hash(shelf: NbwShelf, can_path) -> None:
    """Compute and persist a save-hash for idempotency checks."""
    save_hash = sha256_file(can_path)
    hash_file = shelf.archive_root / "last-save.sha256"
    shelf.archive_root.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(save_hash + "\n")
