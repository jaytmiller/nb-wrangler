"""YAML value type normalization.

ruamel.yaml silently converts certain unquoted scalar values:
  `true`/`false`     -> bool (True/False)
  `null`/`~`         -> None
  `3.12`             -> float (3.12)
  `2026-04-13`       -> datetime.date(2026, 4, 13)

But the wrangler codebase treats most spec values as opaque strings.
This module provides a normalization pass that converts non-string types
to strings for fields that should always be string-valued, making specs
tolerant of being quoted or unquoted.
"""

from datetime import date, datetime


def normalize_value(value):
    """Convert a YAML-parsed value to its intended type for wrangler spec use.

    Fields in the wrangler spec that are meant to be strings end up as
    non-string types when unquoted in YAML (e.g., `3.12` -> float,
    `2026-04-13` -> date, `true` -> bool). This function converts them
    back to strings so the rest of the codebase works regardless of quoting.

    For fields that are intentionally typed (e.g., valid_on/expires_on),
    returns a string representation compatible with the existing .isoformat() calls.
    """
    if value is None:
        return None

    # Booleans that should be strings come out as True/False
    if isinstance(value, bool):
        return str(value)

    # Dates/times that should be strings -- produce ISO format
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, (int, float)):
        return str(value)



    return value


def normalize_dict_values(d, *, path=""):
    """Recursively traverse a loaded YAML dict and coerce values to types consistent
    with the wrangler codebase's string expectations.

    Leaves lists intact (only normalizes the scalar values within them).
    Returns `d` mutated in place for convenience.
    """
    if not isinstance(d, dict):
        return d

    for key, value in list(d.items()):
        if isinstance(value, dict):
            normalize_dict_values(value, path=f"{path}.{key}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, (dict, list)):
                    normalize_dict_values(item)
                else:
                    value[i] = normalize_value(item)
        else:
            d[key] = normalize_value(value)

    return d


def normalize_header(header: dict | None) -> dict:
    """Alias kept for readability – normalises the image spec header.

    The function simply forwards to :func:`normalize_dict_values` so callers can use a
    descriptive name without re‑implementing any logic.
    """
    if isinstance(header, dict):
        normalize_dict_values(header)
    return header or {}
