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
from nb_wrangler.hubenv.seeds import INLINE_FLAG, _strip_internal_flags, seed_from_empty
from nb_wrangler.utils import get_yaml, sha256_str, yaml_dumps

# ---------------------------------------------------------------------------
# mamba-view <-> full-wrangler-spec conversions
# ---------------------------------------------------------------------------


def split_conda_pip(deps: list) -> tuple[list, list[str]]:
    """Split a mamba ``dependencies`` list into (conda strings, pip list)."""
    conda: list = []
    pip: list[str] = []
    for dep in deps or []:
        if isinstance(dep, dict) and "pip" in dep:
            pip.extend(dep.get("pip") or [])
        else:
            conda.append(dep)
    return conda, pip


def python_version(conda: list) -> str | None:
    """Return the pinned python version string from a conda list, or None."""
    for pkg in conda:
        if isinstance(pkg, str) and pkg.startswith("python="):
            return pkg.split("=", 1)[1]
    return None


def _required_image_header(name: str, python_version: str | None) -> dict:
    """Scaffold the required ``image_spec_header`` fields for a valid spec.

    ``kernel_name`` is always set to *name* — even in the "inline spec"
    form, where it may coexist with the inline mamba spec (second YAML doc)
    and take precedence over it.  ``python_version`` is set when a Python pin
    was resolved; it likewise may coexist with the inline form.  The caller
    adds an empty pin for simple-definition specs that lack a resolved pin.
    """
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
    """Scaffold the required ``system`` section for a valid spec.

    Key order matters: nbw's loader (_content_fp) pops ``date_updated`` and
    ``spec_sha256`` then re-appends them, so they must be last (date_updated
    then spec_sha256) for the stored hash to survive a load round-trip.
    """
    return {
        "spec_version": str(WRANGLER_SPEC_VERSION),
        "spi": {
            "repo": "https://github.com/spacetelescope/science-platform-images.git"
        },
        "nb-wrangler": {"repo": "https://github.com/spacetelescope/nb-wrangler.git"},
        "date_updated": datetime.datetime.now().isoformat(),
        "spec_sha256": None,
    }


def mamba_to_wrangler(name: str, mamba_spec: dict, inline: bool = False) -> dict:
    """Convert a hubenv mamba-view dict to a full valid wrangler spec.

    ``name/channels/dependencies/environment_vars`` from the view map onto
    ``image_spec_header``, ``extra_mamba_packages``, ``extra_pip_packages``,
    ``environment_vars`` respectively.  *inline* True builds the wrangler "
    inline spec" form (two YAML documents, the mamba view as doc 2); in both
    forms the header's ``kernel_name`` and (when resolvable) ``python_version``
    always reflect the effective values and may coexist with the inline
    mamba seed.
    """
    conda, pip = split_conda_pip(mamba_spec.get("dependencies") or [])
    py = python_version(conda)
    mamba_clean = [
        d
        for d in conda
        if not (isinstance(d, str) and d.startswith("python=")) and d != "pip"
    ]
    header = _required_image_header(name, py)
    # When a real python version was not pinned, simple-definition mode
    # requires one; fall back to an empty pin so validation passes.
    if not inline and py is None:
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


def _mamba_clean(view: dict) -> dict:
    """Return a mamba-clean doc 2: no environment_vars, no internal flags."""
    clean = _strip_internal_flags(view)
    clean.pop("environment_vars", None)
    return clean


def _write_two_docs(doc1: dict, doc2: dict | None) -> str:
    """Serialize doc1 (+ doc2) exactly as nbw's SpecManager.to_string() does."""
    out = yaml_dumps(doc1)
    if doc2 is not None:
        out += "\n---\n" + yaml_dumps(doc2)
    return out


def _compute_spec_sha256(doc1: dict, doc2: dict | None) -> None:
    """Set ``doc1['system']['spec_sha256']`` to a valid hash.

    Matches nbw's ``SpecManager.add_sha256``: blank the field, hash the
    two-document serialization, then restore.
    """
    system = doc1["system"]
    system["spec_sha256"] = ""
    content = yaml_dumps(doc1)
    if doc2 is not None:
        content += "\n---\n" + yaml_dumps(doc2)
    system["spec_sha256"] = sha256_str(content)


def to_wrangler_yaml(name: str, spec: dict) -> str:
    """Return a full valid wrangler-spec YAML for the mamba-view *spec*.

    Emits the form the source was created in (single-doc "simple", or
    two-doc "inline" mamba seed) with a valid ``spec_sha256`` and a fresh
    ``date_updated``.
    """
    inline = bool(spec.get(INLINE_FLAG, False))
    seed = _strip_internal_flags(spec)
    wspec = mamba_to_wrangler(name, seed, inline=inline)
    wspec["system"]["date_updated"] = datetime.datetime.now().isoformat()
    doc2 = _mamba_clean(seed) if inline else None
    _compute_spec_sha256(wspec, doc2)
    return _write_two_docs(wspec, doc2)


# ---------------------------------------------------------------------------
# Public load / save API (used by hubenv commands)
# ---------------------------------------------------------------------------


def shelf_spec_path(config: PantryStore, name: str):
    """Return the path to the shelf spec for *name* (see PantryStore)."""
    return config.shelf_spec_path(name)


def load_hubenv_spec(config: PantryStore, name) -> dict:
    """Return the mamba-view for *name*.

    When the shelf spec exists on disk in full-wrangler form, convert it
    back to the mamba view.  A two-document (inline mamba seed) spec yields
    a view built from the second document (the seed) so the inline form
    round-trips; ``INLINE_FLAG`` marks the form for re-save.  When no shelf
    spec exists yet, fall back to the base empty view.
    """
    spec_path = config.shelf_spec_path(name)
    if spec_path.exists():
        yaml = get_yaml()
        with open(spec_path) as f:
            docs = list(yaml.load_all(f)) or [{}]
        if len(docs) > 1:
            view = dict(docs[1])
            env_vars = docs[0].get("environment_vars") or {}
            if env_vars:
                view["environment_vars"] = dict(env_vars)
        else:
            view = wrangler_to_mamba(name, docs[0])
        view[INLINE_FLAG] = len(docs) > 1
        return view
    return seed_from_empty(name, None)


def save_hubenv_spec(config: PantryStore, name, spec) -> None:
    """Persist *spec* to the shelf.

    *spec* is the mamba-view (the typical hubenv call site).  The on-disk
    representation is always the full-wrangler form: a single document in
    "simple" form or a two-document inline-mamba-seed form matching the
    source, always with a valid ``spec_sha256`` and ``date_updated``.
    """
    spec_path = config.shelf_spec_path(name)
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(to_wrangler_yaml(name, spec))


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
