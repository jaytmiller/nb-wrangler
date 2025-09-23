# nb_wrangler/spec_generator.py
"""Interactive spec file generator for nb-wrangler."""

import argparse
import os
import sys
import yaml
from pathlib import Path

from .constants import __version__


def get_user_input(prompt, default=None, required=True):
    """Get user input with optional default and required validation."""
    if default:
        prompt = f"{prompt} (default: {default}): "
    else:
        prompt = f"{prompt}: "

    while True:
        try:
            value = input(prompt).strip()
            if not value and default:
                return default
            if required and not value:
                print("This field is required.")
                continue
            return value
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            sys.exit(1)
        except EOFError:
            print("\nUnexpected end of input.")
            sys.exit(1)


def generate_spec():
    """Generate a spec file interactively."""
    print("=== nb-wrangler Spec Generator ===")
    print(f"Version: {__version__}")
    print()

    # Image header information
    image_spec_header = {}
    image_spec_header["image_name"] = get_user_input(
        "Image name", default="My Notebook Environment"
    )
    image_spec_header["deployment_name"] = get_user_input(
        "Deployment name", default="tike"
    )
    image_spec_header["kernel_name"] = get_user_input("Kernel name", default="tess")
    image_spec_header["display_name"] = get_user_input("Display name", default="TESS")
    image_spec_header["description"] = get_user_input(
        "Description", default="A notebook environment for analysis."
    )
    image_spec_header["valid_on"] = get_user_input(
        "Valid on (YYYY-MM-DD)", default="2025-07-02"
    )
    image_spec_header["expires_on"] = get_user_input(
        "Expires on (YYYY-MM-DD)", default="2025-10-02"
    )
    image_spec_header["python_version"] = get_user_input(
        "Python version", default="3.11.13"
    )
    image_spec_header["nb_repo"] = get_user_input(
        "Notebook repository URL",
        default="https://github.com/spacetelescope/tike_content",
    )
    image_spec_header["nb_root_directory"] = get_user_input(
        "Notebook root directory", default="content/notebooks/"
    )

    # Selected notebooks
    selected_notebooks = []

    # Main notebook repo
    main_repo = {}
    main_repo["include_subdirs"] = []
    include_dirs = get_user_input(
        "Include subdirectories for main repo (comma-separated)",
        default="data-access/,lcviz-tutorial/,tglc/,zooniverse_view_lightcurve/",
    ).split(",")
    main_repo["include_subdirs"] = [d.strip() for d in include_dirs if d.strip()]
    selected_notebooks.append(main_repo)

    # Add additional repos
    add_more = get_user_input(
        "Add additional notebook repositories? (y/n)", default="n"
    ).lower()
    if add_more.startswith("y"):
        while True:
            repo_entry = {}
            repo_entry["nb_repo"] = get_user_input("Repository URL", required=True)
            repo_entry["nb_root_directory"] = get_user_input(
                "Root directory", default="notebooks/"
            )
            repo_entry["include_subdirs"] = []
            include_dirs = get_user_input(
                "Include subdirectories (comma-separated)", default=""
            ).split(",")
            repo_entry["include_subdirs"] = [
                d.strip() for d in include_dirs if d.strip()
            ]
            selected_notebooks.append(repo_entry)

            more = get_user_input("Add another repository? (y/n)", default="n").lower()
            if not more.startswith("y"):
                break

    # Extra packages
    extra_mamba_packages = []
    mamba_input = get_user_input(
        "Extra mamba packages (comma-separated, e.g. pip,conda)", default=""
    )
    if mamba_input:
        extra_mamba_packages = [p.strip() for p in mamba_input.split(",") if p.strip()]

    extra_pip_packages = []
    pip_input = get_user_input(
        "Extra pip packages (comma-separated, e.g. boto3,requests)", default="boto3"
    )
    if pip_input:
        extra_pip_packages = [p.strip() for p in pip_input.split(",") if p.strip()]

    # System configuration
    system = {}
    system["spec_version"] = get_user_input("Spec version", default="1.0")
    system["archive_format"] = get_user_input("Archive format", default=".tar")
    system["spi_url"] = get_user_input(
        "SPI URL", default="https://github.com/jaytmiller/science-platform-images.git"
    )

    # Build the spec
    spec = {
        "image_spec_header": image_spec_header,
        "selected_notebooks": selected_notebooks,
        "extra_mamba_packages": extra_mamba_packages,
        "extra_pip_packages": extra_pip_packages,
        "system": system,
    }

    return spec


def main():
    """Main entry point for the spec generator."""
    parser = argparse.ArgumentParser(
        description="Generate a nb-wrangler spec file interactively."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path (default: spec.yaml)",
        default="spec.yaml",
    )

    args = parser.parse_args()

    try:
        spec = generate_spec()

        output_path = Path(args.output)
        if output_path.exists():
            overwrite = get_user_input(
                f"File {output_path} already exists. Overwrite? (y/n)", default="n"
            ).lower()
            if not overwrite.startswith("y"):
                print("Operation cancelled.")
                return 1

        with open(output_path, "w") as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

        print(f"\nSpec file generated successfully: {output_path}")
        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 1
    except Exception as e:
        print(f"Error generating spec: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
