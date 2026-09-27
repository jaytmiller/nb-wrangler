"""Seed-spec builders for ``ppe env create``.

Each builder accepts the common ``name``/``python`` arguments plus a
source-specific argument, and returns a mamba-spec dict suitable for
serialization with ``nb_wrangler.utils.yaml_dumps``.
"""

import json
import re
from pathlib import Path

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


def seed_from_empty(name: str, python: str | None = None) -> dict:
    """Build a mamba spec for an empty environment."""
    return _base_spec(name, python)


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
    """Build a mamba spec from one or more requirements files."""
    spec = _base_spec(name, python)
    pip_packages: list[str] = []
    for f in files:
        pip_packages.extend(_read_requirements(f))
    spec["dependencies"].append({"pip": pip_packages})
    return spec


def seed_from_mamba_spec(name: str, path: str | Path) -> dict:
    """Load a mamba spec YAML and override the environment name."""
    yaml = get_yaml()
    with open(path) as fh:
        spec = yaml.load(fh)
    spec["name"] = name
    return spec


def _extract_imports(code: str) -> list[str]:
    """Extract top-level import package names from a code string."""
    import_names: list[str] = []
    # Match: import <pkg>  /  import <pkg> as ...  /  from <pkg> import ...
    patterns = [
        r"^\s*import\s+([\w.]+)",
        r"^\s*from\s+([\w.]+)\s+import",
    ]
    for line in code.splitlines():
        for pat in patterns:
            match = re.match(pat, line)
            if match:
                pkg = match.group(1).split(".")[0]
                if pkg not in import_names:
                    import_names.append(pkg)
    return import_names


def _extract_notebook_imports(path: str | Path) -> list[str]:
    """Extract import package names from a local .ipynb file."""
    with open(path) as fh:
        notebook = json.load(fh)
    imports: list[str] = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        for src in cell.get("source", []):
            imports.extend(_extract_imports(src))
    return imports


def seed_from_notebooks(
    name: str, paths: list[str], python: str | None = None
) -> dict:
    """Build a mamba spec from imports found in notebook files."""
    spec = _base_spec(name, python)
    imports: list[str] = []
    for p in paths:
        imports.extend(_extract_notebook_imports(p))
    spec["dependencies"].append({"pip": sorted(set(imports))})
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

    # Add extra pip packages
    extra_pip = wspec.get("extra_pip_packages", []) or []
    spec["dependencies"].append({"pip": list(extra_pip)})

    return spec