# nb_wrangler/config.py
"""Configuration management for nb-wrangler."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import argparse

if TYPE_CHECKING:  # avoid circular import at module load; only resolved for type-checkers
    from .logger import get_configured_logger
from .constants import (
    NBW_ROOT,
    NBW_MAMBA_CMD,
    NBW_PIP_CMD,
    NOTEBOOK_TEST_MAX_SECS,
    NOTEBOOK_TEST_JOBS,
    NOTEBOOK_TEST_EXCLUDE,
    DEFAULT_LOG_TIMES_MODE,
    DEFAULT_COLOR_MODE,
    REPOS_DIR,
    DEFAULT_DATA_ENV_VARS_MODE,
)

args_config = None  # Singleton instance of WranglerConfig


def set_args_config(config: "WranglerConfig"):
    """Set the global args_config variable to a singleton."""
    assert isinstance(
        config, WranglerConfig
    ), "config should only be an instance of WranglerConfig."
    global args_config
    args_config = config


def get_args_config():
    """Return the singleton config object based on WranglerConfig.from_args()
    instantiated from a CLI / argparse object.
    """
    assert args_config is not None, "Premature fetch of global args_config variable."
    return args_config


@dataclass
class WranglerConfig:
    """Configuration class for NotebookWrangler."""

    workflows: list[str]

    spec_file: str = ""

    mamba_command_override_by_cli: Optional[str] = None
    pip_command_override_by_cli: Optional[str] = None
    favor_commands: str | None = None

    # These are the _resolved_ values, starting from defaults
    mamba_command: str = NBW_MAMBA_CMD
    pip_command: str = NBW_PIP_CMD

    output_dir: Path = NBW_ROOT / "temps"
    verbose: bool = False
    quiet: bool = False
    debug: bool = False
    log_times: str = DEFAULT_LOG_TIMES_MODE
    reset_log: bool = False
    color: str = DEFAULT_COLOR_MODE

    repos_dir: Path = Path(REPOS_DIR)
    clone_repos: bool = False
    delete_repos: bool = False
    repos_clean: Optional[list[str]] = None
    overwrite_local_changes: bool = False
    stash_local_changes: bool = False
    use_dirty_repos: bool = False

    env_init: bool = False
    env_pack: bool = False
    env_unpack: bool = False
    env_delete: bool = False
    env_archive_delete: bool = False
    env_register: bool = False
    env_unregister: bool = False
    env_compact: bool = False
    packages_ignore_versions: bool = False
    env_archive_format: str = ""
    env_print_name: bool = False
    env_kernel_cleanup: bool = False

    packages_compile: bool = False
    packages_install: bool = False
    packages_uninstall: bool = False

    packages_omit_spi: bool = False

    test_notebooks: str | None = None
    test_notebooks_exclude: str = NOTEBOOK_TEST_EXCLUDE
    test_imports: str | None = None
    test_all: str | None = None
    test_copy_shared: str = ""
    test_isolate_notebook: bool = False

    jobs: int = NOTEBOOK_TEST_JOBS
    timeout: int = NOTEBOOK_TEST_MAX_SECS

    inject_spi: bool = False
    dev: bool = False
    _dev_explicitly_set: bool = False
    prod: bool = False
    submit_for_build: bool = False

    spec_reset: bool = False
    spec_validate: bool = False
    spec_ignore_hash: bool = False
    spec_update_hash: bool = False
    spec_disable_dev_overrides: bool = False

    data_env_vars_mode: str = DEFAULT_DATA_ENV_VARS_MODE
    data_print_exports: bool = False
    data_env_vars_no_auto_add: bool = False
    data_reset_spec: bool = False
    data_collect: bool = False
    data_list: bool = False
    data_download: bool = False
    data_validate: bool = False
    data_update: bool = False
    data_unpack: bool = False
    data_pack: bool = False
    data_delete: str = ""
    data_select: str = ".*"
    data_no_validation: bool = False
    data_no_unpack_existing: bool = False
    data_no_symlinks: bool = False
    data_symlinks: bool = False
    data_clean_symlinks: bool = False

    spec_select: str | None = None
    spec_name: bool = False
    print_wrangler_repo: bool = False
    print_wrangler_ref: bool = False
    print_repo_tags: bool = False
    spec_list: bool = False
    spec_add: bool = False

    spi_branch: str = ""
    spi_commit_message: str = ""
    spi_inject_reqs: bool = False
    spi_build_image: bool = False
    spi_prune_docker: bool = False
    spi_push_branch: bool = False
    spi_pr: bool = False
    spi_image_name: bool = False

    docker_pull: Optional[str] = None
    docker_cat: Optional[str] = None
    docker_list: Optional[str] = None

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "WranglerConfig":
        """Create WranglerConfig from argparse Namespace and spec file."""
        global args_config
        mamba_val = getattr(args, "mamba_cmd", None)
        pip_val = getattr(args, "pip_command", None)
        favor_val = getattr(args, "favor_commands", None)

        args_config = cls(
            spec_file=args.spec_uri,
            workflows=args.workflows,
            repos_dir=args.repos_dir,
            clone_repos=args.clone_repos,
            delete_repos=args.delete_repos,
            repos_clean=args.repos_clean,
            overwrite_local_changes=args.overwrite_local_changes,
            stash_local_changes=args.stash_local_changes,
            use_dirty_repos=args.use_dirty_repos,
            spec_disable_dev_overrides=getattr(
                args, "spec_disable_dev_overrides", False
            ),
            env_init=args.env_init,
            env_pack=args.env_pack,
            env_unpack=args.env_unpack,
            env_delete=args.env_delete,
            env_archive_delete=args.env_archive_delete,
            env_register=args.env_register,
            env_unregister=args.env_unregister,
            env_archive_format=args.env_archive_format,
            env_compact=args.env_compact,
            packages_ignore_versions=args.packages_ignore_versions,
            env_print_name=args.env_print_name,
            env_kernel_cleanup=args.env_kernel_cleanup,
            packages_compile=args.packages_compile,
            packages_install=args.packages_install,
            packages_uninstall=args.packages_uninstall,
            packages_omit_spi=args.packages_omit_spi,
            test_notebooks=args.test_notebooks,
            test_notebooks_exclude=args.test_notebooks_exclude,
            test_imports=args.test_imports,
            test_all=args.test_all,
            test_copy_shared=args.test_copy_shared,
            test_isolate_notebook=args.test_isolate_notebook,
            jobs=args.jobs,
            timeout=args.timeout,
            inject_spi=args.inject_spi,
            dev=args.dev,
            _dev_explicitly_set=args.dev,
            prod=args.prod,
            spec_reset=args.spec_reset,
            spec_validate=args.spec_validate,
            spec_ignore_hash=args.spec_ignore_hash,
            spec_update_hash=args.spec_update_hash,
            data_reset_spec=args.data_reset_spec,
            data_collect=args.data_collect,
            data_list=args.data_list,
            data_download=args.data_download,
            data_validate=args.data_validate,
            data_update=args.data_update,
            data_unpack=args.data_unpack,
            data_pack=args.data_pack,
            data_delete=args.data_delete,
            data_env_vars_mode=args.data_env_vars_mode,
            data_print_exports=args.data_print_exports,
            data_env_vars_no_auto_add=args.data_env_vars_no_auto_add,
            data_select=args.data_select,
            data_no_validation=args.data_no_validation,
            data_no_unpack_existing=args.data_no_unpack_existing,
            data_no_symlinks=args.data_no_symlinks,
            data_symlinks=args.data_symlinks,
            data_clean_symlinks=args.data_clean_symlinks,
            spec_select=args.spec_select,
            spec_name=args.spec_name,
            print_wrangler_repo=args.print_wrangler_repo,
            print_wrangler_ref=args.print_wrangler_ref,
            print_repo_tags=args.print_repo_tags,
            spec_list=args.spec_list,
            spec_add=args.spec_add,
            spi_branch=args.spi_branch,
            spi_commit_message=" ".join(args.spi_commit_message),
            spi_inject_reqs=args.spi_inject_reqs,
            spi_build_image=args.spi_build_image,
            spi_prune_docker=args.spi_prune_docker,
            spi_push_branch=args.spi_push_branch,
            spi_pr=args.spi_pr,
            spi_image_name=args.spi_image_name,
            docker_pull=args.docker_pull,
            docker_cat=args.docker_cat,
            docker_list=args.docker_list,
            verbose=args.verbose,
            quiet=args.quiet,
            debug=args.debug,
            log_times=args.log_times,
            reset_log=args.reset_log,
            color=args.color,
            mamba_command_override_by_cli=mamba_val,
            pip_command_override_by_cli=pip_val,
            favor_commands=favor_val,
        )
        return args_config

    def resolve_commands_from_spec(self, spec_manager):
        """Resolve mamba_command and pip_command after the spec file is loaded.

        Constants assign default CMD values when neither env vars nor spec vars are specified.
        The 'favor' field in system.commands discriminates between using env vars or CLI switches
        when both are defined.

        Value precedence per command (mamba/pip separately):
          1. CLI switch -- overrides spec and environment and defaults.
          2. Spec system.commands.<command> -- wins IFF system.favor is missing or set to 'spec'
          3. Env var NBW_XXX_CMD - wins IFF system.favor is set to 'environment'
        """
        if not hasattr(spec_manager, "commands"):
            return

        cmds = spec_manager.commands or {}
        # Handle both dict and YAML-typed-values objects
        if not isinstance(cmds, dict):
            return

        self._resolve_cmd(
            field_name="mamba_command",
            cli_key="mamba_command_override_by_cli",
            env_or_default=NBW_MAMBA_CMD,
            spec_val=cmds.get("mamba"),
        )
        self._resolve_cmd(
            field_name="pip_command",
            cli_key="pip_command_override_by_cli",
            env_or_default=NBW_PIP_CMD,
            spec_val=cmds.get("pip"),
        )

    def _resolve_cmd(self, field_name, cli_key, env_or_default, spec_val):
        """Resolve a single mamba/pip command per the precedence rules."""
        cli_val = getattr(self, cli_key, None)
        if cli_val is not None:
            setattr(self, field_name, cli_val)
            return  # CLI overrides all

        match self.favor_commands:
            case "environment":
                if env_or_default:
                    setattr(self, field_name, env_or_default)
                else:
                    setattr(self, field_name, spec_val)
            case "spec" | None:
                if spec_val:
                    setattr(self, field_name, spec_val)
                else:
                    setattr(self, field_name, env_or_default)
            case _:
                raise ValueError(
                    f"favor_commands has an invalid value: '{self.favor_commands}'"
                )
        from .logger import get_configured_logger  # deferred to avoid circular import at load time
        logger = get_configured_logger()
        logger.debug(f"{field_name} is set to {getattr(self, field_name)}.")


class WranglerConfigurable:
    """Mixin which reslts in self.config being defined for subclasses."""

    def __init__(self):
        # print("WranglerConfigurable")
        super().__init__()
        self.config = get_args_config()
