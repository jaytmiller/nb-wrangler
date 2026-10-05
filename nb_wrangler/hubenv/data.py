"""data subcommand: manage data archives for PPE environments."""

import fnmatch
import json

from nb_wrangler import data_manager
from nb_wrangler.hubenv._common import ensure_config
from nb_wrangler.hubenv.config import HubenvConfig


def cmd_data_ls(args) -> int:
    """Handle ``hubenv data ls NAME [--format table|json]``."""
    ensure_config()
    config = HubenvConfig()
    archives = list_data_archives(config, args.name)
    if args.format == "json":
        print_data_ls_json(archives, args.name)
    else:
        print_data_ls_table(archives, args.name)
    return 0


def cmd_data_download(args) -> int:
    """Handle ``hubenv data download NAME [--select REGEX] [--no-validate]``."""
    ensure_config()
    success = data_manager.download_data(
        args.name,
        select=args.select,
        validate=not args.no_validate,
    )
    if not success:
        return 1
    print(f"Downloaded data archives for '{args.name}'.")
    return 0


def cmd_data_unpack(args) -> int:
    """Handle ``hubenv data unpack``."""
    ensure_config()
    success = data_manager.unpack_data(
        args.name,
        symlinks=args.symlinks,
        no_unpack_existing=args.no_unpack_existing,
    )
    if not success:
        return 1
    print(f"Unpacked data archives for '{args.name}'.")
    return 0


def cmd_data_pack(args) -> int:
    """Handle ``hubenv data pack NAME`` — pack live data dirs into archive files."""
    ensure_config()
    success = data_manager.pack_data(args.name)
    if not success:
        return 1
    print(f"Packed data archives for '{args.name}'.")
    return 0


def cmd_data_clean(args) -> int:
    """Handle ``hubenv data clean NAME [archived|unpacked|both]`` — delete data."""
    ensure_config()
    success = data_manager.delete_data(args.name, mode=args.mode)
    if not success:
        return 1
    print(f"Cleaned data for '{args.name}' (mode: {args.mode}).")
    return 0


def list_data_archives(config, name: str) -> list[tuple[str, int]]:
    """Return sorted list of ``(filename, size)`` for data archives of *name*.

    Scans the env's shelf ``archives/`` dir for files matching ``data-*``,
    excluding internal files such as ``last-save.sha256``.
    """
    results: list[tuple[str, int]] = []
    for _, shelf_path in config.find_shelves(name):
        archive_dir = shelf_path / "archives"
        if not archive_dir.is_dir():
            continue
        for entry in archive_dir.iterdir():
            if entry.is_file() and fnmatch.fnmatch(entry.name, "data-*"):
                results.append((entry.name, entry.stat().st_size))
    results.sort(key=lambda x: x[0])
    return results


def print_data_ls_table(archives: list[tuple[str, int]], name: str) -> None:
    """Print a two-column ARCHIVE/SIZE table."""
    print(f"{'ARCHIVE':<30} SIZE")
    print("-" * 70)
    if not archives:
        print(f"(no data archives defined for '{name}')")
        return
    for fname, size in archives:
        print(f"{fname:<30} {size}")


def print_data_ls_json(archives: list[tuple[str, int]], name: str) -> None:
    """Print ls results as JSON."""
    result = {
        "name": name,
        "archives": [fname for fname, _ in archives],
    }
    print(json.dumps(result, indent=2))
