"""Command line interface for nb-curator."""

import sys
import argparse

from .config import (
    CuratorConfig,
    DEFAULT_MICROMAMBA_PATH,
    REPOS_DIR,
    NOTEBOOK_TEST_MAX_SECS,
    NOTEBOOK_TEST_JOBS,
)

from .curator import NotebookCurator
from . import utils


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process notebook image specification YAML and prepare notebook environment and tests."
    )
    parser.add_argument(
        "spec_uri",
        type=str,
        help="URI to the YAML specification file:  simple path, file:// path, https://, http://, or s3://",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG log output",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Drop into debugging with pdb on exceptions.",
    )
    parser.add_argument(
        "--log-times",
        action="store_true",
        help="Include ISO timestamps in log messages.",
    )
    parser.add_argument(
        "--init-env",
        action="store_true",
        help="Create and kernelize the target environment before curation run. See also --delete-env.",
    )
    parser.add_argument(
        "--delete-env",
        action="store_true",
        help="Completely delete the target environment after processing.",
    )
    parser.add_argument(
        "--pack-env",
        action="store_true",
        help="Pack the target environment into a compressed tarball for distribution or archival.",
    )
    parser.add_argument(
        "--unpack-env",
        action="store_true",
        help="Unpack a previously packed environment compressed tarball into the target directory.",
    )
    parser.add_argument(
        "--curate",
        action="store_true",
        help="sets options for a core nb-curator workflow: --compile --install --test-notebooks",
    )
    parser.add_argument(
        "-c",
        "--compile-packages",
        action="store_true",
        help="Compile spec and input package lists to generate pinned requirements and other metadata for target environment.",
    )
    parser.add_argument(
        "--omit-spi-packages",
        action="store_true",
        help="Include the 'common' packages used by all missions in all current SPI based and mission environments, may affect GUI capabilty.",
    )
    parser.add_argument(
        "-i",
        "--install-packages",
        action="store_true",
        help="Install compiled base and pip requirements into target/test environment.",
    )
    parser.add_argument(
        "--uninstall-packages",
        action="store_true",
        help="Remove the compiled packages from the target environment after processing.",
    )
    parser.add_argument(
        "-t",
        "--test-notebooks",
        default=None,
        const=".*",
        nargs="?",
        type=str,
        help="Test notebooks matching patterns (comma-separated regexes) in target environment.",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        default=NOTEBOOK_TEST_JOBS,
        type=int,
        help="Number of parallel jobs for notebook testing.",
    )
    parser.add_argument(
        "--timeout",
        default=NOTEBOOK_TEST_MAX_SECS,
        type=int,
        help="Timeout in seconds for notebook tests.",
    )
    parser.add_argument(
        "--inject-spi",
        action="store_true",
        help="Inject curation products into the Science Platform Images repo clone at the specified existing 'deployment'.",
    )
    parser.add_argument(
        "--submit-for-build",
        action="store_true",
        help="Submit the updated spec and curation results to the Science Platform Images GitHub repo triggering a build.",
    )
    parser.add_argument(
        "--clone-repos",
        action="store_true",
        help="Clone notebook repos to the directory indicated by --repos-dir.",
    )
    parser.add_argument(
        "--repos-dir",
        type=str,
        default=REPOS_DIR,
        help="Directory where notebook and other repos will be cloned.",
    )
    parser.add_argument(
        "--delete-repos",
        action="store_true",
        help="Delete --repo-dir and clones after processing.",
    )
    parser.add_argument(
        "--micromamba-path",
        type=str,
        default=DEFAULT_MICROMAMBA_PATH,
        help="Path to micromamba program to use for curator environment management.",
    )
    parser.add_argument(
        "--reset-spec",
        action="store_true",
        help="Reset spec to its original state by deleting output fields.",
    )
    return parser.parse_args()


def main():
    """Main entry point for the CLI."""

    args = parse_args()

    # Create configuration using simplified factory method
    config = CuratorConfig.from_args(args)

    try:
        # Convert URI to local path
        config.spec_file = utils.uri_to_local_path(args.spec_uri)

        # Create and run curator
        curator = NotebookCurator(config)
        success = curator.main()
        curator.print_log_counters()

        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        config.logger.error("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        config.logger.exception(e, "Fatal error:")
        sys.exit(1)


if __name__ == "__main__":
    main()
