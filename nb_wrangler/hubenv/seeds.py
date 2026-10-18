"""Seed-spec builders for ``hubenv create``.

Each builder accepts the common ``name``/``python`` arguments plus a
source-specific argument, and returns a mamba-spec dict suitable for
serialization with ``nb_wrangler.utils.yaml_dumps``.
"""

import subprocess
from pathlib import Path

from nb_wrangler.constants import NBW_MAMBA_CMD, TARGET_PACKAGES
from nb_wrangler.utils import get_yaml


def _base_spec(name: str, python: str | None = None) -> dict:
    """Return a minimal mamba-spec skeleton with conda-forge channel."""
    deps: list = []
    if python:
        deps.append(f"python={python}")
    deps.append("pip")
    return {
        "name": name,
        "channels": ["conda-forge"],
        "dependencies": deps,
    }


def _find_pip_section(deps: list) -> dict | None:
    """Return the first ``{"pip": [...]}`` sub-dict in *deps*, else None."""
    for dep in deps or []:
        if isinstance(dep, dict) and "pip" in dep:
            return dep
    return None


def _merge_packages(existing, required) -> list:
    """Return *existing* + *required* de-duplicated, order-preserved."""
    seen: set = set()
    merged: list = []
    for pkg in list(existing) + list(required):
        if pkg not in seen:
            seen.add(pkg)
            merged.append(pkg)
    return merged


def _ensure_target_packages(spec: dict) -> dict:
    """Ensure *spec* installs all ``TARGET_PACKAGES`` as pip packages.

    Guarantees the ``pip`` conda package is a dependency and that the
    spec's ``pip`` section (created if absent) contains every
    ``TARGET_PACKAGES`` entry merged with any existing pip packages.
    Returns *spec* for chaining.
    """
    deps = spec.setdefault("dependencies", [])
    if not any(isinstance(d, str) and d == "pip" for d in deps):
        # Insert the pip conda package before the first sub-dict, else append.
        idx = next((i for i, d in enumerate(deps) if isinstance(d, dict)), len(deps))
        deps.insert(idx, "pip")
    section = _find_pip_section(deps)
    existing = section["pip"] if section is not None and section.get("pip") else []
    if section is None:
        deps.append({"pip": _merge_packages(existing, TARGET_PACKAGES)})
    else:
        section["pip"] = _merge_packages(existing, TARGET_PACKAGES)
    return spec


def seed_from_empty(name: str, python: str | None = None) -> dict:
    """Build a mamba spec for an empty environment.

    Always installs the minimum ``TARGET_PACKAGES`` (e.g. ``ipykernel``
    for kernel registration) as pip dependencies so the created
    environment can support hubenv functions.
    """
    spec = _base_spec(name, python)
    _ensure_target_packages(spec)
    return spec


def _read_requirements(path: str | Path) -> list[str]:
    """Read non-comment, non-blank lines from a requirements file."""
    packages: list[str] = []
    with open(path) as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                packages.append(stripped)
    return packages


def seed_from_requirements(
    name: str, files: list[str], python: str | None = None
) -> dict:
    """Build a mamba spec from one or more requirements files.

    Merges the baseline ``TARGET_PACKAGES`` (e.g. ``ipykernel`` for kernel
    registration) alongside the requested requirements so the created
    environment can support hubenv functions.
    """
    spec = _base_spec(name, python)
    pip_packages: list[str] = []
    for f in files:
        pip_packages.extend(_read_requirements(f))
    spec["dependencies"].append({"pip": pip_packages})
    _ensure_target_packages(spec)
    return spec


def seed_from_mamba_spec(name: str, path: str | Path) -> dict:
    """Load a mamba spec YAML, override the name, and add baseline pip pkgs.

    Preserves the source spec's channels and dependencies as-is, but always
    guarantees ``TARGET_PACKAGES`` are installed as pip packages so the
    created environment can support hubenv functions regardless of what the
    source spec lists.
    """
    yaml = get_yaml()
    with open(path) as fh:
        spec = yaml.load(fh)
    spec["name"] = name
    _ensure_target_packages(spec)
    return spec


def seed_from_wrangler_spec(name: str, path: str | Path) -> dict:
    """Build a mamba spec from a wrangler spec YAML file."""
    yaml = get_yaml()
    with open(path) as fh:
        wspec = yaml.load(fh)

    header = wspec.get("image_spec_header", {}) or {}
    python = header.get("python_version")
    if python:
        python = str(python).strip()

    spec = _base_spec(name, python)

    # Add extra mamba packages (skip "pip" since it's already a dependency)
    extra_mamba = wspec.get("extra_mamba_packages", []) or []
    for pkg in extra_mamba:
        if pkg != "pip":
            spec["dependencies"].insert(-1, pkg)  # before "pip"

    # Add extra pip packages, then guarantee the baseline TARGET_PACKAGES.
    extra_pip = wspec.get("extra_pip_packages", []) or []
    spec["dependencies"].append({"pip": list(extra_pip)})
    _ensure_target_packages(spec)

    return spec


# ---------------------------------------------------------------------------
# --from-existing-env
# ---------------------------------------------------------------------------


def _run_mamba_export(env_name: str) -> str:
    """Run ``mamba env export`` for *env_name* and return YAML stdout.

    Raises ``ValueError`` if the environment is not found or the command
    fails.
    """
    cmd = [NBW_MAMBA_CMD, "env", "export", "-n", env_name, "--no-builds"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(
            f"mamba env export failed for '{env_name}': " f"{result.stderr.strip()}"
        )
    return result.stdout


def _run_pip_freeze(env_name: str) -> list[str]:
    """Run ``pip freeze`` inside *env_name* and return package lines.

    Raises ``ValueError`` if the command fails.
    """
    cmd = [NBW_MAMBA_CMD, "run", "-n", env_name, "pip", "freeze"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(
            f"pip freeze failed for '{env_name}': " f"{result.stderr.strip()}"
        )
    return _parse_pip_freeze(result.stdout)


def _parse_pip_freeze(text: str) -> list[str]:
    """Parse pip-freeze output into clean, non-comment package lines."""
    packages: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            packages.append(line)
    return packages


def _parse_env_export(yaml_text: str, name: str, python: str | None) -> dict:
    """Parse env-export YAML into a mamba-spec dict.

    Overrides the environment name, strips the ``pip:`` sub-dict and any
    ``python=`` entry from conda dependencies (caller may pass *python*
    to pin a specific version), and ensures ``pip`` is present as a
    conda dependency.
    """
    yaml = get_yaml()
    export = yaml.load(yaml_text) or {}
    channels = export.get("channels") or ["conda-forge"]
    deps: list = []
    for dep in export.get("dependencies", []):
        if isinstance(dep, dict) and "pip" in dep:
            continue
        if isinstance(dep, str) and dep.startswith("python"):
            continue
        deps.append(dep)
    if python:
        deps.insert(0, f"python={python}")
    if not any(isinstance(d, str) and d == "pip" for d in deps):
        deps.append("pip")
    return {
        "name": name,
        "channels": list(channels),
        "dependencies": deps,
    }


def _add_pip_section(spec: dict, pip_packages: list[str]) -> None:
    """Append a ``pip:`` sub-dict to the spec's dependency list."""
    spec["dependencies"].append({"pip": list(pip_packages)})


def seed_from_existing_env(name: str, env_name: str, python: str | None = None) -> dict:
    """Build a mamba-spec dict from an existing mamba environment.

    Exports the package set of *env_name*, overrides the target name
    with *name*, and returns a spec dict suitable for serialization
    with ``yaml_dumps``.

    The baseline ``TARGET_PACKAGES`` are always merged into the pip
    section (even when the source environment has none) so the target
    can support hubenv functions.

    Raises ``ValueError`` if the environment cannot be found or the
    required subcommands fail.
    """
    yaml_text = _run_mamba_export(env_name)
    spec = _parse_env_export(yaml_text, name, python)
    pip_packages = _run_pip_freeze(env_name)
    if pip_packages:
        _add_pip_section(spec, pip_packages)
    _ensure_target_packages(spec)
    return spec
