"""Export environment specs in various formats.

Handles ``hubenv export NAME [--to-mamba-spec|--to-requirements|--to-wrangler-spec]``.
"""

from pathlib import Path

from nb_wrangler.hubenv._common import get_logger
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import (
    extract_pip_packages,
    load_hubenv_spec,
    mamba_to_wrangler,
)
from nb_wrangler.utils import yaml_dumps


def cmd_export(args) -> int:
    """Handle ``hubenv export NAME [--to-mamba-spec|--to-requirements|--to-wrangler-spec] [-o FILE|-]``."""
    config = PantryStore()
    spec_path = config.shelf_spec_path(args.name)
    if not spec_path.exists():
        get_logger().error(f"No spec found for env '{args.name}'.")
        return 1
    spec = load_hubenv_spec(config, args.name)
    output = format_export(spec, args)
    write_export_output(output, args.output, args.name)
    return 0


def format_export(spec: dict, args) -> str:
    """Format the spec according to the chosen export flags."""
    if args.to_requirements:
        return spec_to_requirements(spec)
    if args.to_wrangler_spec:
        return yaml_dumps(mamba_to_wrangler(spec["name"], spec))
    return yaml_dumps(spec)  # default: mamba spec


def write_export_output(output: str, output_path: str, name: str) -> None:
    """Write export output to file or stdout."""
    if output_path == "-":
        print(output, end="")
    else:
        Path(output_path).write_text(output)
        print(f"Exported spec for '{name}' to {output_path}")


def spec_to_requirements(spec: dict) -> str:
    """Extract pip packages from spec as requirements lines."""
    packages = extract_pip_packages(spec.get("dependencies", []))
    if not packages:
        return ""
    return "\n".join(packages) + "\n"
