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
        return ""

    # Booleans that should be strings come out as True/False
    if isinstance(value, bool):
        return str(value)

    # Dates/times that should be strings -- produce ISO format
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    # Floats/integers that should be strings (e.g., python_version: 3.12)
    if isinstance(value, float):
        # Avoid turning `1.0` into `"1"` -- preserve decimal point
        s = str(value)
        if "." not in s:
            s += ".0"
        return s

    # Plain integers that should be strings
    if isinstance(value, int):
        return str(value)

    return value


def normalize_dict_values(d, *, path=""):
    """Recursively traverse a loaded YAML dict and coerce values to types consistent
    with the wrangler codebase's string expectations.

    Leaves lists intact (only normalizes the scalar values within them).
    Returns `d` mutated in place for convenience.
    """
    if not isinstance(d, dict):
        return d or d == 0 or d is False

    for key, value in list(d.items()):
        if isinstance(value, dict):
            normalize_dict_values(value, path=f"{path}.{key}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, (dict, list)):
                    normalize_dict_values(item, path=f"{path}[{i}]")
                else:
                    normalized = normalize_value(item)
                    value[i] = normalized
        else:
            d[key] = normalize_value(value)

    return d


def normalize_header(header):
    """Normalize the image_spec_header specifically, applying fields that are known
    to always be string-valued in the codebase but may be parsed as other types."""
    # The header fields that get coerced by normalize_dict_values already cover it,
    # but we document them explicitly here for clarity:
    #   python_version  -> str (was float e.g. 3.12)
    #   valid_on        -> str (was datetime.date)
    #   expires_on      -> str (was datetime.date)
    return normalize_dict_values(header or {})
