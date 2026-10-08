"""env relock subcommand: re-curate locks and validate the implicit spec."""

import sys

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.hubenv._common import get_logger
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import (
    get_or_create_pip_section,
    load_hubenv_spec,
    save_hubenv_spec,
)
from nb_wrangler.utils import writelines


def cmd_env_relock(args) -> int:
    """Handle ``hubenv env relock``."""
    config = PantryStore()
    em = EnvironmentManager()

    if not em.environment_exists(args.name):
        get_logger().error(f"Live environment '{args.name}' not found.")
        return 1

    return do_relock(config, em, args.name, args.dry_run)


def do_relock(config, em, name, dry_run) -> int:
    """Perform the relock operation."""
    spec = load_hubenv_spec(config, name)
    pip_list = get_or_create_pip_section(spec.get("dependencies", []))

    if not pip_list:
        print(f"No pip packages to relock in '{name}'.")
        return 0

    compiled = compile_pip_packages(em, name, pip_list)
    if compiled is None:
        return 1

    if dry_run:
        print_relock_dry_run(name, compiled)
        return 0

    apply_relock(config, name, spec, compiled)
    return 0


def compile_pip_packages(em, name, packages):
    """Compile pip packages using uv pip compile. Returns resolved versions."""
    req_path = writelines(packages, em.nbw_temp_dir / f"relock_reqs_{name}.txt")
    output_path = em.nbw_temp_dir / f"relock_compiled_{name}.txt"

    cmd = (
        f"uv pip compile --output-file {output_path} "
        f"--python {sys.executable} --no-header --annotate {req_path}"
    )
    result = em.wrangler_run(cmd, check=False)

    if not em.handle_result(
        result, f"Failed to compile packages for relock of '{name}': "
    ):
        return None

    return read_compiled_versions(output_path)


def read_compiled_versions(filepath) -> list[str]:
    """Read compiled package versions from a requirements file."""
    if not filepath.exists():
        return []
    packages = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith(("#", "--")):
                packages.append(line)
    return packages


def print_relock_dry_run(name, compiled) -> None:
    """Print dry-run output for relock."""
    print(f"Dry-run: would re-curate {len(compiled)} packages for '{name}':")
    for pkg in compiled:
        print(f"  {pkg}")


def apply_relock(config, name, spec, compiled) -> None:
    """Persist the relocked spec."""
    pip_section = get_or_create_pip_section(spec.get("dependencies", []))
    pip_section[:] = compiled
    save_hubenv_spec(config, name, spec)
    print(f"Relocked {len(compiled)} packages for '{name}'.")
