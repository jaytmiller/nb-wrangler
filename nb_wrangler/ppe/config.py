"""Pantry configuration and read-only detection for ppe.

Thin wrapper over ``nb_wrangler.constants`` that classifies each pantry
directory as writable or read-only using ``os.access``.
"""

import os
from pathlib import Path
from typing import Optional

from nb_wrangler.constants import NBW_PANTRY_DIRS, NBW_ROOT
from nb_wrangler.logger import WranglerLoggable


class PpeConfig(WranglerLoggable):
    """Pantry configuration with read-only detection.

    Wraps ``NBW_PANTRY_DIRS`` (a colon-separated, PATH-like list) and
    exposes writable-pantry lookups used by every ``ppe`` command.
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