"""Compatibility layer for hubenv's pantry store.

The single shared store lives in :mod:`nb_wrangler.pantry` on
:class:`nb_wrangler.pantry.NbwPantrySet` — one object both ``nbw`` and
``hubenv`` use for pantry paths, writability, shelf lookups, live-env
listing, restore hashes, and the canonical shelf-spec location.

This module keeps the historical ``PantryStore`` / ``HubenvConfig`` names
importable for existing call sites.  It's a thin subclass that anchors
``NBW_PANTRY_DIRS`` and ``NBW_ROOT`` to *this* module's namespace, so that
tests patching ``nb_wrangler.hubenv.config.NBW_ROOT`` /
``nb_wrangler.hubenv.config.NBW_PANTRY_DIRS`` continue to see their mocks.
All store logic is inherited from :class:`NbwPantrySet` — zero logic is
duplicated here.
"""

from pathlib import Path
from typing import Optional

from nb_wrangler.constants import NBW_ROOT, NBW_PANTRY_DIRS
from nb_wrangler.pantry import NbwPantrySet


class PantryStore(NbwPantrySet):
    """Thin alias for :class:`NbwPantrySet` with ``hubenv`` defaults.

    Exists purely so historical call sites
    (``from nb_wrangler.hubenv.config import PantryStore``) keep working
    and so existing test patches of
    ``nb_wrangler.hubenv.config.NBW_ROOT`` /
    ``nb_wrangler.hubenv.config.NBW_PANTRY_DIRS`` are honoured.
    """

    def __init__(
        self,
        paths: Optional[list[Path]] = None,
        nbw_root: Optional[Path] = None,
    ):
        if paths is None:
            paths = list(NBW_PANTRY_DIRS)
        if nbw_root is None:
            nbw_root = NBW_ROOT
        super().__init__(paths=paths, nbw_root=nbw_root)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<PantryStore pantries={[str(p) for p in self.pantries]} "
            f"root={self.nbw_root}>"
        )


# Backwards-compat alias: existing hubenv code may import ``HubenvConfig``.
HubenvConfig = PantryStore
