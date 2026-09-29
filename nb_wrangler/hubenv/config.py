"""Pantry configuration and read-only detection for hubenv.

Thin wrapper over ``nb_wrangler.constants`` that classifies each pantry
directory as writable or read-only using ``os.access``.
"""

import os
from pathlib import Path
from typing import Optional

from nb_wrangler.constants import NBW_PANTRY_DIRS, NBW_ROOT
from nb_wrangler.logger import WranglerLoggable


class HubenvConfig(WranglerLoggable):
    """Pantry configuration with read-only detection.

    Wraps ``NBW_PANTRY_DIRS`` (a colon-separated, PATH-like list) and
    exposes writable-pantry lookups used by every ``hubenv`` command.
    """

    def __init__(self):
        super().__init__()
        self.pantry_dirs: list[Path] = list(NBW_PANTRY_DIRS)
        self.nbw_root: Path = NBW_ROOT

    def is_writable(self, pantry: str | Path) -> bool:
        """Return True if *pantry* exists and the user can write to it."""
        p = Path(pantry)
        if not p.exists():
            return False
        return os.access(p, os.W_OK)

    def writable_pantries(self) -> list[Path]:
        """Return writable pantry directories in priority order."""
        return [p for p in self.pantry_dirs if self.is_writable(p)]

    def first_writable_pantry(self) -> Optional[Path]:
        """Return the first writable pantry, or None if all are read-only."""
        writable = self.writable_pantries()
        return writable[0] if writable else None

    def target_pantry(self, forced_path: Optional[str | Path] = None) -> Optional[Path]:
        """Resolve the pantry to write to.

        If *forced_path* is given, validate it is writable and return it.
        Otherwise return the first writable pantry from ``NBW_PANTRY_DIRS``.

        Returns None when no writable pantry is available.
        """
        if forced_path is not None:
            p = Path(forced_path)
            if not self.is_writable(p):
                self.logger.error(
                    f"Pantry '{p}' is read-only or does not exist. "
                    f"Use --pantry <writable-path>."
                )
                return None
            return p
        return self.first_writable_pantry()

    def find_shelves(self, name: str) -> list[tuple[Path, Path]]:
        """Return all ``(pantry_path, shelf_path)`` pairs where a shelf named
        *name* exists across ``NBW_PANTRY_DIRS``.

        Used by ``hubenv env restore`` to detect multi-match shadowing.
        """
        matches: list[tuple[Path, Path]] = []
        for pantry in self.pantry_dirs:
            shelf_path = pantry / "shelves" / name
            if shelf_path.exists():
                matches.append((pantry, shelf_path))
        return matches

    def restore_hash_path(self, name: str) -> Path:
        """Return the path to the live restore-hash marker for *name*."""
        return self.nbw_root / ".hubenv-restore" / f"{name}.sha256"

    def list_shelves(
        self, glob_expr: Optional[str] = None, pantry: Optional[Path] = None
    ) -> list[dict]:
        """Return metadata for shelves across pantries.

        Each entry: ``{pantry, name, path, writable, save_hash}``.
        If *glob_expr* is given, filter by matching shelf name.
        If *pantry* is given, restrict to that single pantry directory.
        """
        import fnmatch

        results: list[dict] = []
        search_pantries = [pantry] if pantry else self.pantry_dirs
        for p in search_pantries:
            shelves_dir = p / "shelves"
            if not shelves_dir.exists():
                continue
            for shelf_path in sorted(shelves_dir.iterdir()):
                if not shelf_path.is_dir():
                    continue
                if glob_expr and not fnmatch.fnmatch(shelf_path.name, glob_expr):
                    continue
                hash_file = shelf_path / "archives" / "last-save.sha256"
                save_hash = (
                    hash_file.read_text().strip() if hash_file.exists() else None
                )
                results.append(
                    {
                        "pantry": p,
                        "name": shelf_path.name,
                        "path": shelf_path,
                        "writable": self.is_writable(p),
                        "save_hash": save_hash,
                    }
                )
        return results

    def list_live_envs(self) -> list[dict]:
        """Return metadata for live environments under ``NBW_ROOT/envs``.

        Each entry: ``{name, path}``.
        """
        envs_dir = self.nbw_root / "envs"
        if not envs_dir.exists():
            return []
        results: list[dict] = []
        for env_path in sorted(envs_dir.iterdir()):
            if env_path.is_dir():
                results.append({"name": env_path.name, "path": env_path})
        return results

    def hubenv_spec_path(self, name: str) -> Path:
        """Return the path to the implicit spec file for *name*.

        The spec lives at ``NBW_ROOT/envs/<NAME>/.hubenv-spec.yaml`` and stores
        the seed spec + package delta so ``install``/``relock`` have state.
        """
        return self.nbw_root / "envs" / name / ".hubenv-spec.yaml"
