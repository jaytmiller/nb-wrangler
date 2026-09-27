"""Pantry configuration and read-only detection for the ppe CLI.

Provides :class:`PantryConfig` which classifies each pantry directory in
``NBW_PANTRY_DIRS`` as read/write or read-only, and resolves target pantries
and shelf lookups across the (PATH-like) colon-separated pantry list.
"""

import os
from pathlib import Path
from typing import Optional

from ..constants import NBW_PANTRY_DIRS


class ReadOnlyPantryError(Exception):
    """Raised when a command tries to write to a read-only pantry."""


class NoWritablePantryError(Exception):
    """Raised when no writable pantry is available."""


class MultiMatchError(Exception):
    """Raised when a name matches shelves in multiple pantries."""

    def __init__(self, name: str, matches: list[tuple[Path, Path]]):
        self.name = name
        self.matches = matches
        locations = ", ".join(str(p) for p, _ in matches)
        super().__init__(
            f"'{name}' matches shelves in multiple pantries:\n  {locations}\n"
            f"Use --pantry PATH to disambiguate."
        )


class PantryConfig:
    """Manages pantry paths and read-only classification.

    Each pantry directory in ``NBW_PANTRY_DIRS`` is classified as writable
    or read-only using ``os.access(path, os.W_OK)`` at first access.
    """

    def __init__(self, paths: Optional[list[Path]] = None):
        """Initialise with *paths* (defaults to ``NBW_PANTRY_DIRS``)."""
        if paths is None:
            paths = list(NBW_PANTRY_DIRS)
        paths = [Path(p) for p in paths if str(p)]
        self.paths: list[Path] = paths
        self._writable_cache: dict[Path, bool] = {}

    def is_writable(self, pantry: Path) -> bool:
        """Return *True* if *pantry* is writable."""
        pantry = Path(pantry)
        if pantry not in self._writable_cache:
            self._writable_cache[pantry] = os.access(pantry, os.W_OK)
        return self._writable_cache[pantry]

    def writable_pantries(self) -> list[Path]:
        """Return the list of writable pantries (in priority order)."""
        return [p for p in self.paths if self.is_writable(p)]

    def target_pantry(self, path: Optional[str] = None) -> Path:
        """Resolve the target pantry for writes.

        If *path* is given and writable, return it.  Otherwise return the
        first writable pantry.  Raises :class:`ReadOnlyPantryError` if the
        given path is read-only, or :class:`NoWritablePantryError` if no
        writable pantry exists.
        """
        if path is not None:
            pantry = Path(path)
            pantry.mkdir(parents=True, exist_ok=True)
            if not self.is_writable(pantry):
                raise ReadOnlyPantryError(
                    f"Pantry '{pantry}' is read-only. "
                    f"Use --pantry <writable-path> to specify a writable pantry."
                )
            return pantry
        writable = self.writable_pantries()
        if not writable:
            raise NoWritablePantryError(
                "No writable pantry found in NBW_PANTRY_DIRS. "
                "Set NBW_PANTRY to a writable path or use --pantry."
            )
        return writable[0]

    def find_shelves(self, name: str) -> list[tuple[Path, Path]]:
        """Return all ``(pantry, shelf)`` pairs for *name*.

        Searches every pantry in priority order.  Returns matches in the
        order they appear (highest-priority first).
        """
        matches: list[tuple[Path, Path]] = []
        for pantry in self.paths:
            shelf = pantry / "shelves" / name
            if shelf.exists():
                matches.append((pantry, shelf))
        return matches

    def resolve_shelf(
        self,
        name: str,
        pantry_path: Optional[str] = None,
    ) -> tuple[Path, Path]:
        """Resolve a single shelf for *name*.

        If *pantry_path* is given, search only that pantry.  Otherwise search
        all pantries; if more than one match is found, raise
        :class:`MultiMatchError`.  Raises ``FileNotFoundError`` if no match
        is found.
        """
        if pantry_path is not None:
            shelf = Path(pantry_path) / "shelves" / name
            if not shelf.exists():
                raise FileNotFoundError(
                    f"No shelf '{name}' in pantry '{pantry_path}'."
                )
            return (Path(pantry_path), shelf)

        matches = self.find_shelves(name)
        if not matches:
            raise FileNotFoundError(
                f"No shelf '{name}' found in any pantry."
            )
        if len(matches) > 1:
            raise MultiMatchError(name, matches)
        return matches[0]