"""env relock subcommand: re-curate locks and validate the implicit spec."""

from nb_wrangler.compiler import RequirementsCompiler
from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.hubenv._common import get_logger
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import (
    get_or_create_pip_section,
    load_hubenv_spec,
    save_hubenv_spec,
)


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
    """Delegate to the shared RequirementsCompiler. Returns resolved versions."""
    compiler = RequirementsCompiler(spec_manager=None, repo_manager=None)
    return compiler.compile_packages_for_env(packages, em.nbw_temp_dir)


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
