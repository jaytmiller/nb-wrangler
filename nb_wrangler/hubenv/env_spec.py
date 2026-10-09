"""Implicit spec loading, saving, and package-list manipulation.

These helpers manage the shelf spec — the canonical per-environment YAML
at ``<pantry>/shelves/<name>/nbw-wrangler-spec.yaml`` — as the source of
truth for a hubenv-managed environment's pinned dependencies.

``hubenv`` commands interact with a *mamba-spec view* of this file
(``name`` / ``channels`` / ``dependencies`` / optional
``environment_vars``).  The conversions happen transparently in
:func:`load_hubenv_spec` and :func:`save_hubenv_spec`.

The file on disk is always a **full valid wrangler spec** that passes
``SpecManager.load_and_validate``.  This is what lets ``hubenv data`` (and
any nbw step that resolves the same shelf spec) consume the file unchanged.
"""

import datetime
from nb_wrangler.constants import WRANGLER_SPEC_VERSION
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.seeds import seed_from_empty
from nb_wrangler.utils import get_yaml, yaml_dumps

# ---------------------------------------------------------------------------
# mamba-view <-> full-wrangler-spec conversions
# ---------------------------------------------------------------------------


def _split_conda_pip(deps: list) -> tuple[list, list[str]]:
    """Split a mamba ``dependencies`` list into (conda strings, pip list)."""
    conda: list = []
    pip: list[str] = []
    for dep in deps or []:
        if isinstance(dep, dict) and "pip" in dep:
            pip.extend(dep.get("pip") or [])
        else:
            conda.append(dep)
    return conda, pip


def _python_version(conda: list) -> str | None:
    """Return the pinned python version string from a conda list, or None."""
    for pkg in conda:
        if isinstance(pkg, str) and pkg.startswith("python="):
            return pkg.split("=", 1)[1]
    return None


def _required_image_header(name: str, python_version: str | None) -> dict:
    """Scaffold the required ``image_spec_header`` fields for a valid spec."""
    header = {
        "image_name": name,
        "kernel_name": name,
        "display_name": name,
        "deployment_name": "wrangler",
        "valid_on": "1970-01-01",
        "expires_on": "2099-12-31",
    }
    if python_version:
        header["python_version"] = str(python_version)
    return header


def _required_system() -> dict:
    """Scaffold the required ``system`` section for a valid spec."""
    return {
        "spec_version": str(WRANGLER_SPEC_VERSION),
        "spec_sha256": None,
        "spi": {
            "repo": "https://github.com/spacetelescope/science-platform-images.git"
        },
        "nb-wrangler": {"repo": "https://github.com/spacetelescope/nb-wrangler.git"},
        "date_updated": datetime.datetime.now().isoformat(),
    }


def mamba_to_wrangler(name: str, mamba_spec: dict) -> dict:
    """Convert a hubenv mamba-view dict to a full valid wrangler spec.

    ``name/channels/dependencies/environment_vars`` from the view map
    onto ``image_spec_header``, ``extra_mamba_packages``,
    ``extra_pip_packages``, ``environment_vars`` respectively.
    All validator-required scaffolding (``image_spec_header`` keys,
    ``repositories``, ``system.spi``) is filled in.
    """
    conda, pip = _split_conda_pip(mamba_spec.get("dependencies") or [])
    py = _python_version(conda)
    mamba_clean = [
        d
        for d in conda
        if not (isinstance(d, str) and d.startswith("python=")) and d != "pip"
    ]
    header = _required_image_header(name, py)
    # When a real python version was not pinned, simple-definition mode
    # requires one; fall back to an empty pin so validation passes.
    if py is None:
        header["python_version"] = ""
    wspec: dict = {
        "image_spec_header": header,
        "repositories": {},
        "system": _required_system(),
    }
    if mamba_clean:
        wspec["extra_mamba_packages"] = mamba_clean
    if pip:
        wspec["extra_pip_packages"] = pip
    env_vars = mamba_spec.get("environment_vars")
    if env_vars:
        wspec["environment_vars"] = dict(env_vars)
    return wspec


def wrangler_to_mamba(name: str, wspec: dict) -> dict:
    """Convert a shelf wrangler spec back to the mamba-view hubenv shows.

    The result carries at least ``name``, ``channels`` (default
    ``conda-forge``), and ``dependencies``.  When the source spec has
    ``environment_vars``, they are carried into the view unchanged.
    """
    header = wspec.get("image_spec_header") or {}
    deps: list = []
    if header.get("python_version"):
        deps.append(f"python={header['python_version']}")
    for dep in wspec.get("extra_mamba_packages") or []:
        deps.append(dep)
    pip_pkgs = wspec.get("extra_pip_packages") or []
    if pip_pkgs:
        deps.append("pip")
        deps.append({"pip": list(pip_pkgs)})
    view: dict = {
        "name": header.get("image_name") or name,
        "channels": ["conda-forge"],
        "dependencies": deps,
    }
    if wspec.get("environment_vars") is not None:
        view["environment_vars"] = dict(wspec["environment_vars"])
    return view


def _coerce_to_wrangler(name: str, spec: dict) -> dict:
    """Coerce *spec* (mamba view or already-full wrangler) to a valid wrangler spec.

    A dict that already carries an ``image_spec_header`` is treated as a
    hand-authored wrangler spec and left untouched.  Anything else is
    assumed to be a mamba view and converted.
    """
    if isinstance(spec, dict) and "image_spec_header" in (spec or {}):
        return spec
    return mamba_to_wrangler(name, spec)


# ---------------------------------------------------------------------------
# Public load / save API (used by hubenv commands)
# ---------------------------------------------------------------------------


def shelf_spec_path(config: PantryStore, name: str):
    """Return the path to the shelf spec for *name* (see PantryStore)."""
    return config.shelf_spec_path(name)


def load_hubenv_spec(config: PantryStore, name) -> dict:
    """Return the mamba-view for *name*.

    When the shelf spec exists on disk in full-wrangler form, convert it
    back to the mamba view.  When no shelf spec exists yet (e.g. a first
    ``var ls`` on an uncreated env), fall back to the base empty view so
    downstream handlers have a well-typed seed to mutate.
    """
    spec_path = config.shelf_spec_path(name)
    if spec_path.exists():
        yaml = get_yaml()
        with open(spec_path) as f:
            wspec = yaml.load(f) or {}
        return wrangler_to_mamba(name, wspec)
    return seed_from_empty(name, None)


def save_hubenv_spec(config: PantryStore, name, spec) -> None:
    """Persist *spec* to the shelf.

    *spec* may be the mamba-view (the typical hubenv call site) or an
    already-full wrangler spec.  The on-disk representation is always the
    full-wrangler form so the file validates under ``SpecManager``.
    """
    spec_path = config.shelf_spec_path(name)
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    wspec = _coerce_to_wrangler(name, spec)
    spec_path.write_text(yaml_dumps(wspec))


def update_and_save_spec(config, name, packages, action, using) -> None:
    """Load, update, and persist the implicit spec (mamba view)."""
    spec = load_hubenv_spec(config, name)
    update_spec_packages(spec, packages, action, using)
    save_hubenv_spec(config, name, spec)


# -- spec package list manipulation (mamba view) ----------------------------


def update_spec_packages(spec, packages, action, using) -> None:
    """Update the spec's package list for the given action and installer."""
    deps = spec.setdefault("dependencies", [])
    if using != "mamba":
        pip_list = get_or_create_pip_section(deps)
        if action == "install":
            add_to_list(pip_list, packages)
        else:
            remove_from_list(pip_list, packages)
    else:
        if action == "install":
            add_conda_packages(deps, packages)
        else:
            remove_conda_packages(deps, packages)


def get_or_create_pip_section(deps) -> list:
    """Get or create the pip section list in dependencies."""
    for dep in deps:
        if isinstance(dep, dict) and "pip" in dep:
            return dep["pip"]
    pip_section: dict = {"pip": []}
    deps.append(pip_section)
    return pip_section["pip"]


def add_to_list(lst, items) -> None:
    """Add items to a list if not already present."""
    for item in items:
        if item not in lst:
            lst.append(item)


def remove_from_list(lst, items) -> None:
    """Remove items from a list by base name."""
    to_remove = {i.strip().lower() for i in items}
    lst[:] = [x for x in lst if pkg_base_name(x) not in to_remove]


def pkg_base_name(pkg: str) -> str:
    """Extract the base package name (without version constraints)."""
    for sep in ("=", "<", ">", "!", "~"):
        pkg = pkg.split(sep)[0]
    return pkg.strip().lower()


def add_conda_packages(deps, packages) -> None:
    """Add conda packages to dependencies, before any pip section."""
    for pkg in packages:
        if pkg not in deps:
            idx = pip_section_index(deps)
            deps.insert(idx, pkg)


def pip_section_index(deps) -> int:
    """Return the index of the first dict in deps, or len(deps)."""
    for i, d in enumerate(deps):
        if isinstance(d, dict):
            return i
    return len(deps)


def remove_conda_packages(deps, packages) -> None:
    """Remove conda packages from dependencies by base name."""
    to_remove = {p.strip().lower() for p in packages}
    deps[:] = [
        d for d in deps if not (isinstance(d, str) and pkg_base_name(d) in to_remove)
    ]


def extract_pip_packages(deps: list) -> list[str]:
    """Return pip packages from the dependencies list."""
    for dep in deps:
        if isinstance(dep, dict) and "pip" in dep:
            return dep["pip"]
    return []
