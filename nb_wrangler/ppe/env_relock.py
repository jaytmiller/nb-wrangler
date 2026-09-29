"""env relock subcommand: re-curate locks and validate the implicit spec."""

import sys

from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.ppe._common import ensure_config
from nb_wrangler.ppe.config import PpeConfig
from nb_wrangler.ppe.env_spec import (
    get_or_create_pip_section,
    load_ppe_spec,
    save_ppe_spec,
)
from nb_wrangler.utils import writelines


def cmd_env_relock(args) -> int:
    """Handle ``ppe env relock``."""
    ensure_config()
    config = PpeConfig()
    em = EnvironmentManager()

    if not em.environment_exists(args.name):
        print(f"Error: live environment '{args.name}' not found.", file=sys.stderr)
        return 1

    return do_relock(config, em, args.name, args.dry_run)


def do_relock(config, em, name, dry_run) -> int:
    """Perform the relock operation."""
    spec = load_ppe_spec(config, name)
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
    save_ppe_spec(config, name, spec)
    print(f"Relocked {len(compiled)} packages for '{name}'.")


# Backward-compat re-exports


def _cmd_env_relock(args) -> int:
    """Backward-compat alias for ``cmd_env_relock``."""
    return cmd_env_relock(args)


def _do_relock(config, em, name, dry_run) -> int:
    """Backward-compat alias for ``do_relock``."""
    return do_relock(config, em, name, dry_run)


def _compile_pip_packages(em, name, packages):
    """Backward-compat alias for ``compile_pip_packages``."""
    return compile_pip_packages(em, name, packages)


def _read_compiled_versions(filepath) -> list[str]:
    """Backward-compat alias for ``read_compiled_versions``."""
    return read_compiled_versions(filepath)


def _print_relock_dry_run(name, compiled) -> None:
    """Backward-compat alias for ``print_relock_dry_run``."""
    print_relock_dry_run(name, compiled)


def _apply_relock(config, name, spec, compiled) -> None:
    """Backward-compat alias for ``apply_relock``."""
    apply_relock(config, name, spec, compiled)
