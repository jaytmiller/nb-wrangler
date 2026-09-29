"""Seed-spec builders for ``hubenv env create``.

Each builder accepts the common ``name``/``python`` arguments plus a
source-specific argument, and returns a mamba-spec dict suitable for
serialization with ``nb_wrangler.utils.yaml_dumps``.
"""

import json
import re
import subprocess
from pathlib import Path

from nb_wrangler.constants import NBW_MAMBA_CMD
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


def seed_from_notebooks(name: str, paths: list[str], python: str | None = None) -> dict:
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

    Raises ``ValueError`` if the environment cannot be found or the
    required subcommands fail.
    """
    yaml_text = _run_mamba_export(env_name)
    spec = _parse_env_export(yaml_text, name, python)
    pip_packages = _run_pip_freeze(env_name)
    if pip_packages:
        _add_pip_section(spec, pip_packages)
    return spec
