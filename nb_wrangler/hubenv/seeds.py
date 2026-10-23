"""Seed-spec builders for ``hubenv create``.

Each builder accepts the common ``name``/``python`` arguments plus a
source-specific argument, and returns a mamba-spec dict suitable for
serialization with ``nb_wrangler.utils.yaml_dumps``.
"""

import subprocess
from pathlib import Path

from nb_wrangler.constants import NBW_MAMBA_CMD, TARGET_PACKAGES
from nb_wrangler.hubenv._common import get_logger
from nb_wrangler.utils import get_yaml

# Internal marker in a hubenv mamba-view dict: ``True`` when the view derives
# from a wrangler spec that carries an inline mamba seed (second YAML document).
# Stripped before any dict is handed to mamba or written as doc 2.
INLINE_FLAG = "_hubenv_inline"


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


# -- inline wrangler-seed helpers (option 1: override name/python, keep recipe) --


def _strip_internal_flags(spec: dict) -> dict:
    """Return *spec* minus hubenv-internal keys (safe to hand to mamba)."""
    if not isinstance(spec, dict):
        return spec
    return {
        k: v
        for k, v in spec.items()
        if not isinstance(k, str) or not k.startswith("_hubenv_")
    }


def _python_from_spec(spec: dict) -> str | None:
    """Return the pinned python version from a mamba spec's dependencies."""
    for dep in spec.get("dependencies") or []:
        if isinstance(dep, str) and dep.startswith("python="):
            return dep.split("=", 1)[1].strip()
    return None


def _clear_python_dep(deps: list) -> None:
    """Remove any ``python``/``python3.x`` string dependency from *deps*."""
    deps[:] = [d for d in deps if not (isinstance(d, str) and d.startswith("python"))]


def _is_compiled_pip(pkg: str) -> bool:
    """Heuristic: is *pkg* a compiled/locked pip entry (python-version specific)?"""
    if not isinstance(pkg, str):
        return False
    lowered = pkg.lower()
    return (
        "sha256" in lowered
        or "cp3." in lowered
        or "py3." in lowered
        or ("manylinux" in lowered or "file://" in lowered)
    )


def _apply_name_python(
    spec: dict, name: str, python: str | None, old_python: str | None
) -> None:
    """Record CLI overrides on the seed: name, python dep, and clear stale lock.

    The seed's name/python are set to *name*/the resolved *python*; when the
    python changes the stale pin and any compiled pip lock are cleared, each
    with a descriptive log line.
    """
    old_name = spec.get("name")
    if old_name and old_name != name:
        get_logger().info(f"Overriding seed name from '{old_name}' to '{name}' (CLI).")
    spec["name"] = name
    if python:
        python = str(python).strip()
        if python != old_python:
            _clear_python_dep(spec["dependencies"])
            spec["dependencies"].insert(0, f"python={python}")
            get_logger().info(
                f"Overriding seed python from '{old_python}' to '{python}' "
                "(CLI); cleared stale python pin."
            )
            _clear_stale_pip_lock(spec, old_python, python)


def _apply_header_extras(spec: dict, header: dict) -> None:
    """Merge the wrangler header's lists into the seed (wrangler lists win)."""
    deps = spec.setdefault("dependencies", [])
    insert_at = next((i for i, d in enumerate(deps) if isinstance(d, dict)), len(deps))
    for pkg in header.get("extra_mamba_packages") or []:
        if isinstance(pkg, dict) or pkg == "pip" or pkg in deps:
            continue
        deps.insert(insert_at, pkg)
        insert_at += 1
    section = _find_pip_section(deps)
    if section is None:
        section = {"pip": []}
        deps.append(section)
    for pkg in header.get("extra_pip_packages") or []:
        if pkg not in section["pip"]:
            section["pip"].append(pkg)


def _clear_stale_pip_lock(spec: dict, old_python: str | None, new_python: str) -> None:
    """Drop compiled (python-version-specific) pip entries; log what was cleared.

    Plain (uncompiled) package names are python-independent and preserved.
    """
    section = _find_pip_section(spec.get("dependencies") or [])
    if section is None:
        return
    pip = section.get("pip")
    if not pip:
        return
    compiled = [p for p in pip if _is_compiled_pip(p)]
    if not compiled:
        return
    section["pip"] = [p for p in pip if not _is_compiled_pip(p)]
    get_logger().info(
        f"Cleared {len(compiled)} stale compiled pip lock entries for python "
        f"'{old_python}'; seed now targets python '{new_python}'."
    )


def _build_inline_seed(doc2: dict, name: str, python: str | None, doc1: dict) -> dict:
    """Build the inline seed from the mamba seed + doc1's extra package lists.

    doc1 is the wrangler spec's first document (top-level
    ``extra_mamba_packages`` / ``extra_pip_packages`` are merged in).
    """
    spec = dict(doc2 or {})
    spec.setdefault("dependencies", [])
    _apply_name_python(spec, name, python, _python_from_spec(spec))
    _apply_header_extras(spec, doc1)
    _ensure_target_packages(spec)
    return spec


def _build_simple_seed(name: str, python: str | None, wspec: dict) -> dict:
    """Build the simple-form seed from a wrangler spec's header + lists."""
    spec = _base_spec(name, python)
    for pkg in wspec.get("extra_mamba_packages") or []:
        if pkg != "pip":
            spec["dependencies"].insert(-1, pkg)
    spec["dependencies"].append({"pip": list(wspec.get("extra_pip_packages") or [])})
    _ensure_target_packages(spec)
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


def seed_from_mamba_spec(name: str | None, path: str | Path) -> dict:
    """Load a mamba spec YAML, default the name, and add baseline pip pkgs.

    Preserves the source spec's channels and dependencies as-is, but always
    guarantees ``TARGET_PACKAGES`` are installed as pip packages so the
    created environment can support hubenv functions regardless of what the
    source spec lists.

    When *name* is ``None`` (no ``--name``), it defaults to the source spec's
    own ``name`` field, or the spec file's stem if absent.
    """
    yaml = get_yaml()
    with open(path) as fh:
        spec = yaml.load(fh) or {}
    if name is None:
        name = spec.get("name") or Path(path).stem
    spec["name"] = name
    _ensure_target_packages(spec)
    return spec


def seed_from_wrangler_spec(
    name: str | None, path: str | Path, python: str | None = None
) -> dict:
    """Build a mamba spec from a wrangler spec YAML file.

    *name* (``None`` when no ``--name``) resolves as CLI > header
    ``kernel_name``/``image_name`` > inline spec ``name`` > file stem.
    *python* (``None`` when no ``--python``) resolves as CLI > header
    ``python_version`` > inline spec python.  In the simple form a Python pin is
    required: if it is absent from every source, a ``ValueError`` is raised
    (wrapped in ``HubenvError`` on the ``create`` path).  When the source carries
    a second YAML document (inline mamba seed) the seed is built from it with the
    CLI name/python overrides applied and recorded (option 1); otherwise it is
    derived from the header package lists.
    """
    yaml = get_yaml()
    with open(path) as fh:
        docs = list(yaml.load_all(fh)) or [{}]
    wspec, inline_doc2 = docs[0], docs[1] if len(docs) > 1 else None
    header = wspec.get("image_spec_header", {}) or {}
    inline = inline_doc2 is not None
    if name is None:
        name = (
            header.get("kernel_name")
            or header.get("image_name")
            or (inline_doc2.get("name") if inline_doc2 else None)
            or Path(path).stem
        )
    if python is None:
        python = header.get("python_version") or (
            _python_from_spec(inline_doc2) if inline_doc2 else None
        )
    if python:
        python = str(python).strip()
    if inline_doc2 is None and not python:
        raise ValueError(
            f"No Python pin for simple-form wrangler spec '{name}' "
            f"({path}): pass --python or set "
            "'image_spec_header.python_version' in the spec."
        )
    if inline_doc2 is not None:
        spec = _build_inline_seed(inline_doc2, name, python, wspec)
    else:
        spec = _build_simple_seed(name, python, wspec)
    spec[INLINE_FLAG] = inline
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

    Overrides the environment name, strips the ``pip:`` sub-dict from
    conda dependencies.  When no *python* override is given, the source
    env's own python pin (first conda dep starting with ``python``) is
    preserved instead of being dropped.
    """
    yaml = get_yaml()
    export = yaml.load(yaml_text) or {}
    channels = export.get("channels") or ["conda-forge"]
    deps: list = []
    source_python: str | None = None
    for dep in export.get("dependencies", []):
        if isinstance(dep, dict) and "pip" in dep:
            continue
        if isinstance(dep, str) and dep.startswith("python"):
            if source_python is None:
                source_python = dep
            continue
        deps.append(dep)
    if python:
        deps.insert(0, f"python={python}")
    elif source_python:
        deps.insert(0, source_python)
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


def seed_from_existing_env(
    name: str | None, env_name: str, python: str | None = None
) -> dict:
    """Build a mamba-spec dict from an existing mamba environment.

    Exports the package set of *env_name*; when *name* is ``None``
    (no ``--name``) it defaults to *env_name* so the import is seamless.
    Returns a spec dict suitable for serialization with ``yaml_dumps``.

    The baseline ``TARGET_PACKAGES`` are always merged into the pip
    section (even when the source environment has none) so the target
    can support hubenv functions.

    Raises ``ValueError`` if the environment cannot be found or the
    required subcommands fail.
    """
    yaml_text = _run_mamba_export(env_name)
    if name is None:
        name = env_name
    spec = _parse_env_export(yaml_text, name, python)
    pip_packages = _run_pip_freeze(env_name)
    if pip_packages:
        _add_pip_section(spec, pip_packages)
    _ensure_target_packages(spec)
    return spec
