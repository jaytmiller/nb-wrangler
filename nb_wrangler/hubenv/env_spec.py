"""Implicit spec loading, saving, and package-list manipulation.

These helpers manage the per-environment YAML spec that hubenv keeps as
the 'source of truth' for each environment's pinned dependencies.
"""

from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.seeds import seed_from_empty
from nb_wrangler.utils import get_yaml, yaml_dumps


def load_hubenv_spec(config: PantryStore, name) -> dict:
    """Load the implicit spec, or create a base spec if none exists."""
    spec_path = config.hubenv_spec_path(name)
    if spec_path.exists():
        yaml = get_yaml()
        with open(spec_path) as f:
            return yaml.load(f)
    return seed_from_empty(name, None)


def save_hubenv_spec(config: PantryStore, name, spec) -> None:
    """Persist the implicit spec to disk."""
    spec_path = config.hubenv_spec_path(name)
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(yaml_dumps(spec))


def update_and_save_spec(config, name, packages, action, using) -> None:
    """Load, update, and persist the implicit spec."""
    spec = load_hubenv_spec(config, name)
    update_spec_packages(spec, packages, action, using)
    save_hubenv_spec(config, name, spec)


# -- spec package list manipulation ------------------------------------------


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
