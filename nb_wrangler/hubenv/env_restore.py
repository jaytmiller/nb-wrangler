"""env restore subcommand: unpack a saved environment and register kernel."""

from pathlib import Path
from typing import Optional

from nb_wrangler.constants import DEFAULT_ARCHIVE_FORMAT
from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.pantry import NbwShelf
from nb_wrangler.hubenv._common import get_logger, print_exports
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import spec_display_name


def cmd_env_restore(args) -> int:
    """Handle ``hubenv restore``.

    Unpack a saved can into NBW_MM/envs and register a Jupyter kernel.
    Supports idempotency (skip if restored hash matches save hash).
    """
    config = PantryStore()

    matches = find_restore_shelf(config, args)
    if matches is None:
        return 1
    if not matches:
        get_logger().error(f"No shelf '{args.name}' found in any pantry.")
        return 1

    pantry_path, shelf_path = matches[0]
    shelf = NbwShelf(shelf_path, pantry_path=pantry_path)
    can_path = shelf.env_archive_path(args.name, DEFAULT_ARCHIVE_FORMAT)

    if _check_archive_exists(shelf, args.name, can_path):
        return 1

    if not args.force:
        if _check_idempotent_skip(shelf, config, args.name):
            print_exports(args.name, config)
            return 0

    if not _do_restore_unpack(shelf, args.name):
        return 1

    save_hash = read_save_hash(shelf) or ""
    record_restore_hash(config, args.name, save_hash)

    em = EnvironmentManager()
    display_name = (
        getattr(args, "display_name", None)
        or spec_display_name(shelf.spec_path)
        or args.name
    )
    em.register_environment(args.name, display_name, {})

    print_exports(args.name, config)

    if args.at_boot:
        write_at_boot_snippet(args.name)

    return 0


def _check_archive_exists(shelf, name: str, can_path) -> bool:
    """Validate can-path exists; print error if missing. Returns True on error.

    Distinctly names the "spec-only" state (a shelf + spec exist but no can
    has been packed yet) so the user knows to run ``hubenv save NAME``.
    """
    if can_path.exists():
        return False
    get_logger().error(
        f"Environment '{name}' has a shelf spec at {shelf.path} but no archive "
        f"(can) at {can_path}."
    )
    get_logger().info(f"Run: hubenv save {name}   to create the restoreable can.")
    return True


def _check_idempotent_skip(shelf, config, name) -> bool:
    """Idempotency hash comparison; prints skip message if already restored."""
    save_hash = read_save_hash(shelf)
    restore_hash = read_restore_hash(config, name)
    if save_hash and restore_hash and save_hash == restore_hash:
        print(
            f"Environment '{name}' already restored (idempotent skip). "
            f"Use --force to re-unpack."
        )
        return True
    return False


def _do_restore_unpack(shelf, name) -> bool:
    """Unpack the environment; return True on success."""
    success = shelf.unpack_environment(name, name, DEFAULT_ARCHIVE_FORMAT)
    return success


def find_restore_shelf(config: PantryStore, args) -> Optional[list[tuple[Path, Path]]]:
    """Find shelf(s) for restore, handling --pantry and multi-match."""
    if args.pantry:
        forced = Path(args.pantry)
        shelf_path = forced / "shelves" / args.name
        if shelf_path.exists():
            return [(forced, shelf_path)]
        get_logger().error(f"No shelf '{args.name}' found in pantry {forced}.")
        return None

    matches = config.find_shelves(args.name)
    if len(matches) > 1:
        get_logger().error(f"'{args.name}' found in multiple pantries:")
        for pantry, shelf_path in matches:
            get_logger().info(f"  {shelf_path}")
        get_logger().info("Use --pantry to select a specific one.")
        return None
    return matches


def read_save_hash(shelf: NbwShelf) -> Optional[str]:
    """Read the save-hash from the shelf."""
    hash_file = shelf.archive_root / "last-save.sha256"
    if hash_file.exists():
        return hash_file.read_text().strip()
    return None


def read_restore_hash(config: PantryStore, name: str) -> Optional[str]:
    """Read the restore-hash for *name* from the live store."""
    hash_file = config.restore_hash_path(name)
    if hash_file.exists():
        return hash_file.read_text().strip()
    return None


def record_restore_hash(config: PantryStore, name: str, save_hash: str) -> None:
    """Persist the restore-hash for future idempotency checks."""
    hash_file = config.restore_hash_path(name)
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(save_hash + "\n")


def write_at_boot_snippet(name: str) -> None:
    """Write a guarded, idempotent snippet for startup restore.

    Writes the snippet file and prints the manual ``source`` instruction; it
    never edits the shell's rc file (user decides where to source from).
    """
    snippet_dir = Path.home() / ".hubenv"
    snippet_dir.mkdir(parents=True, exist_ok=True)
    snippet_path = snippet_dir / f"env-{name}.sh"

    snippet = (
        f"# hubenv ensure {name} - idempotent restore at boot\n"
        f'if [ -z "${{NBW_ACTIVE_ENV+set}}" ]; then\n'
        f'    export NBW_ACTIVE_ENV="{name}"\n'
        f"    hubenv ensure {name} 2>/dev/null || true\n"
        f"fi\n"
    )
    snippet_path.write_text(snippet)

    print(f"At-boot snippet written to {snippet_path}")
    print("To use it at shell startup, add this line to your rc file:")
    print(f"    source {snippet_path}")


def remove_at_boot_snippet(name: str) -> None:
    """Remove a startup snippet if present. Logs one line to stderr."""
    snippet_path = Path.home() / ".hubenv" / f"env-{name}.sh"
    snippet_path.unlink(missing_ok=True)
    get_logger().info(f"Removed at-boot snippet {snippet_path} (if present).")


# Silence unused import warnings
_ = DEFAULT_ARCHIVE_FORMAT
