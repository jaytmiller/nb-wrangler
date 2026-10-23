"""Export environment specs in various formats.

Handles ``hubenv export NAME [--to-mamba-spec|--to-requirements|--to-wrangler-spec]``.
"""

from pathlib import Path

from nb_wrangler.hubenv._common import get_logger, store_for
from nb_wrangler.hubenv.env_spec import (
    extract_pip_packages,
    load_hubenv_spec,
    to_wrangler_yaml,
)
from nb_wrangler.utils import yaml_dumps


def cmd_export(args) -> int:
    """Handle ``hubenv export NAME [--to-mamba-spec|--to-requirements|--to-wrangler-spec] [-o FILE|-]``."""
    config = store_for(args)
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
        output = spec_to_requirements(spec)
        if not output:
            get_logger().warning(
                f"spec for '{args.name}' has no pip packages; "
                "empty requirements output"
            )
        return output
    if args.to_wrangler_spec:
        return to_wrangler_yaml(spec["name"], spec)
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
