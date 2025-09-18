# nb_wrangler/cli.py
"""Command line interface for nb-wrangler."""

import sys
import argparse
import cProfile
import pstats

from . import wrangler
from . import utils
from . import config as config_mod
from .constants import (
    VALID_LOG_TIME_MODES,
    DEFAULT_LOG_TIMES_MODE,
    VALID_COLOR_MODES,
    DEFAULT_COLOR_MODE,
    REPOS_DIR,
    NOTEBOOK_TEST_MAX_SECS,
    NOTEBOOK_TEST_JOBS,
    VALID_ARCHIVE_FORMATS,
)


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
        "--curate",
        dest="workflow",
        action="store_const",
        const="curation",
        help="Execute the curation workflow for spec development to add compiled requirements.",
    )
    parser.add_argument(
        "--submit-for-build",
        dest="workflow",
        action="store_const",
        const="submit-for-build",
        help="Submit fully elaborated requirements for image building.",
    )
    parser.add_argument(
        "--reinstall",
        dest="workflow",
        action="store_const",
        const="reinstall",
        help="Install requirements defined by a pre-compiled spec.",
    )
    parser.add_argument(
        "-t",
        "--test",
        dest="test_all",
        action="store_true",
        help="Test both imports and all notebooks.",
    )
    parser.add_argument(
        "--test-imports",
        action="store_true",
        help="Attempt to import every package explicitly imported by one of the spec'd notebooks.",
    )
    parser.add_argument(
        "--test-notebooks",
        default=None,
        const=".*",
        nargs="?",
        type=str,
        help="Test spec'ed notebooks matching patterns (comma-separated regexes) in target environment. Default regex: .*",
    )
    parser.add_argument(
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
        "--profile",
        action="store_true",
        help="Run with cProfile and output profiling results to console.",
    )
    parser.add_argument(
        "--log-times",
        type=str,
        choices=VALID_LOG_TIME_MODES,
        default=DEFAULT_LOG_TIMES_MODE,
        help="Include timestamps in log messages, either as absolute/normal or elapsed times, both, or none.",
    )
    parser.add_argument(
        "--color",
        choices=VALID_COLOR_MODES,
        default=DEFAULT_COLOR_MODE,
        help="Colorize the log.",
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
        help="Pack the target environment into an archive file for distribution or archival.",
    )
    parser.add_argument(
        "--unpack-env",
        action="store_true",
        help="Unpack a previously packed archive file into the target environment directory.",
    )
    parser.add_argument(
        "--register-env",
        action="store_true",
        help="Register the target environment with Jupyter as a kernel.",
    )
    parser.add_argument(
        "--unregister-env",
        action="store_true",
        help="Unregister the target environment from Jupyter.",
    )

    parser.add_argument(
        "--archive-format",
        default="",
        type=str,
        help="Format for pack/unpack, nominally one of: " + str(VALID_ARCHIVE_FORMATS),
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact the wrangler installation by deleting package caches, etc.",
    )
    parser.add_argument(
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
        "--reset-spec",
        action="store_true",
        help="Reset spec to its original state by deleting output fields.",
    )
    parser.add_argument(
        "--validate-spec",
        action="store_true",
        help="Validate the specification file without performing any curation actions.",
    )
    parser.add_argument(
        "--ignore-spec-hash",
        action="store_true",
        help="Spec SHA256 hashes will not be added or verified upon re-installation.",
    )
    parser.add_argument(
        "--add-pip-hashes",
        action="store_true",
        help="Record PyPi hashes of requested packages for easier verification during later installs.",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point for the CLI."""
    args = parse_args()

    if args.profile:
        with cProfile.Profile() as pr:
            success = _main(args)
            pstats.Stats(pr).sort_stats("cumulative").print_stats(50)
    else:
        success = _main(args)

    return success


def _main(args):
    """Main entry point for the CLI."""
    try:
        # Create configuration using simplified factory method
        config = config_mod.WranglerConfig.from_args(args)
        config.spec_file = spec = utils.uri_to_local_path(args.spec_uri)
        if not spec:
            config.logger.error("Failed reading URI:", args.spec_uri)
            exit_code = 1
        else:
            notebook_wrangler = wrangler.NotebookWrangler(config)
            exit_code = notebook_wrangler.main()
            notebook_wrangler.logger.print_log_counters()
    except KeyboardInterrupt:
        return config.logger.error("Operation cancelled by user")
    except Exception as e:
        exit_code = config.logger.exception(e, "Failed:")
    return 1 if not exit_code else 0


if __name__ == "__main__":
    sys.exit(int(main()))
