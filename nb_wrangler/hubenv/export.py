"""Export environment specs in various formats.

Handles ``hubenv export NAME [--to-mamba-spec|--to-requirements|--to-wrangler-spec]``.
"""

from pathlib import Path
from typing import Optional

from nb_wrangler.hubenv._common import get_logger
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import load_hubenv_spec
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
        return yaml_dumps(spec_to_wrangler(spec))
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
    from nb_wrangler.hubenv.env_spec import extract_pip_packages

    packages = extract_pip_packages(spec.get("dependencies", []))
    if not packages:
        return ""
    return "\n".join(packages) + "\n"


def spec_to_wrangler(spec: dict) -> dict:
    """Convert a mamba spec to a minimal wrangler spec dict."""
    name = spec.get("name", "unnamed")
    conda, pip = split_conda_pip(spec.get("dependencies", []))
    py_ver = extract_python_version(conda)
    conda_clean = [p for p in conda if not str(p).startswith("python") and p != "pip"]
    return {
        "image_spec_header": {
            "image_name": name,
            "kernel_name": name,
            "display_name": name,
            "python_version": py_ver,
        },
        "extra_mamba_packages": conda_clean,
        "extra_pip_packages": pip,
    }


def split_conda_pip(deps: list) -> tuple[list, list[str]]:
    """Split dependencies into conda packages and pip packages."""
    conda: list = []
    pip: list[str] = []
    for dep in deps:
        if isinstance(dep, dict) and "pip" in dep:
            pip.extend(dep["pip"])
        else:
            conda.append(dep)
    return conda, pip


def extract_python_version(conda: list) -> Optional[str]:
    """Extract the python version from conda package list."""
    for pkg in conda:
        if isinstance(pkg, str) and pkg.startswith("python="):
            return pkg.split("=", 1)[1]
    return None
