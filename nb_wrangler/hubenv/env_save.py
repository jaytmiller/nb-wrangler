"""env save subcommand: pack a live environment into a pantry archive."""

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

    target = config.target_pantry(args.pantry)
    if target is None:
        print_no_writable_pantry(args.pantry)
        return 1

    em = EnvironmentManager()
    env_path = em.env_live_path(args.name)
    if not env_path.exists():
        return get_logger().error(
            f"Live environment '{args.name}' not found at {env_path}"
        )

    shelf = NbwShelf(target / "shelves" / args.name, pantry_path=target)
    can_path = shelf.env_archive_path(args.name, DEFAULT_ARCHIVE_FORMAT)

    if args.dry_run:
        print(f"shelf: {shelf.path}")
        print(f"can: {can_path}")
        print(f"live env: {env_path}")
        return 0

    if can_path.exists() and not args.force:
        return get_logger().error(
            f"Archive already exists at {can_path}. Use --force to overwrite."
        )

    success = shelf.pack_environment(args.name, args.name, DEFAULT_ARCHIVE_FORMAT)
    if not success:
        return 1

    persist_save_hash(shelf, can_path)
    print(f"Saved environment '{args.name}' to {can_path}")
    return 0


def persist_save_hash(shelf: NbwShelf, can_path) -> None:
    """Compute and persist a save-hash for idempotency checks."""
    save_hash = sha256_file(can_path)
    hash_file = shelf.archive_root / "last-save.sha256"
    shelf.archive_root.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(save_hash + "\n")
