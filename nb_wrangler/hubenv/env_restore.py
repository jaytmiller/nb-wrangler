"""env restore subcommand: unpack a saved environment and register kernel."""

import sys
from pathlib import Path
from typing import Optional

from nb_wrangler.constants import DEFAULT_ARCHIVE_FORMAT
from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.pantry import NbwShelf
from nb_wrangler.hubenv._common import ensure_config, print_exports
from nb_wrangler.hubenv.config import HubenvConfig


def cmd_env_restore(args) -> int:
    """Handle ``hubenv env restore``.

    Unpack a saved can into NBW_ROOT and register a Jupyter kernel.
    Supports idempotency (skip if restored hash matches save hash).
    """
    ensure_config()
    config = HubenvConfig()

    matches = find_restore_shelf(config, args)
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

    if _check_archive_exists(can_path):
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
    em.register_environment(args.name, args.name, {})

    print_exports(args.name, config)

    if args.at_boot:
        write_at_boot_snippet(args.name)

    return 0


def _check_archive_exists(can_path) -> bool:
    """Validate can-path exists; print error if missing. Returns True on error."""
    if not can_path.exists():
        print(f"Error: no archive (can) found at {can_path}", file=sys.stderr)
        return True
    return False


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


def find_restore_shelf(config: HubenvConfig, args) -> Optional[list[tuple[Path, Path]]]:
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


def read_save_hash(shelf: NbwShelf) -> Optional[str]:
    """Read the save-hash from the shelf."""
    hash_file = shelf.archive_root / "last-save.sha256"
    if hash_file.exists():
        return hash_file.read_text().strip()
    return None


def read_restore_hash(config: HubenvConfig, name: str) -> Optional[str]:
    """Read the restore-hash for *name* from the live store."""
    hash_file = config.restore_hash_path(name)
    if hash_file.exists():
        return hash_file.read_text().strip()
    return None


def record_restore_hash(config: HubenvConfig, name: str, save_hash: str) -> None:
    """Persist the restore-hash for future idempotency checks."""
    hash_file = config.restore_hash_path(name)
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(save_hash + "\n")


def write_at_boot_snippet(name: str) -> None:
    """Write a guarded, idempotent snippet for startup restore."""
    snippet_dir = Path.home() / ".hubenv"
    snippet_dir.mkdir(parents=True, exist_ok=True)
    snippet_path = snippet_dir / f"env-{name}.sh"

    snippet = (
        f"# hubenv env ensure {name} - idempotent restore at boot\n"
        f'if [ -z "${{NBW_ACTIVE_ENV+set}}" ]; then\n'
        f'    export NBW_ACTIVE_ENV="{name}"\n'
        f"    hubenv env ensure {name} 2>/dev/null || true\n"
        f"fi\n"
    )
    snippet_path.write_text(snippet)

    # Append source line to .bashrc if not already present
    bashrc = Path.home() / ".bashrc"
    marker = f"source ~/.hubenv/env-{name}.sh"
    if not bashrc.exists() or marker not in bashrc.read_text():
        with bashrc.open("a") as f:
            f.write(f"\n# Added by hubenv\n{marker}\n")
        print(f"Appended to {bashrc}: {marker}")
    print(f"At-boot snippet written to {snippet_path}")


# Backward-compat re-exports


def _cmd_env_restore(args) -> int:
    """Backward-compat alias for ``cmd_env_restore``."""
    return cmd_env_restore(args)


def _find_restore_shelf(config, args):
    """Backward-compat alias for ``find_restore_shelf``."""
    return find_restore_shelf(config, args)


def _read_save_hash(shelf):
    """Backward-compat alias for ``read_save_hash``."""
    return read_save_hash(shelf)


def _read_restore_hash(config, name):
    """Backward-compat alias for ``read_restore_hash``."""
    return read_restore_hash(config, name)


def _record_restore_hash(config, name, save_hash):
    """Backward-compat alias for ``record_restore_hash``."""
    return record_restore_hash(config, name, save_hash)


def _write_at_boot_snippet(name):
    """Backward-compat alias for ``write_at_boot_snippet``."""
    write_at_boot_snippet(name)


# Silence unused import warnings
_ = DEFAULT_ARCHIVE_FORMAT
