"""env install/uninstall subcommand: install or remove packages."""

from nb_wrangler.constants import NBW_MAMBA_CMD, NBW_PIP_CMD
from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.hubenv._common import get_logger
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import update_and_save_spec


def cmd_env_install(args) -> int:
    """Handle ``hubenv env install``."""
    return cmd_env_pkg_action(args, "install")


def cmd_env_uninstall(args) -> int:
    """Handle ``hubenv env uninstall``."""
    return cmd_env_pkg_action(args, "uninstall")


def cmd_env_pkg_action(args, action: str) -> int:
    """Shared install/uninstall handler."""
    config = PantryStore()
    em = EnvironmentManager()

    if not em.environment_exists(args.name):
        get_logger().error(f"Live environment '{args.name}' not found.")
        return 1

    if args.dry_run:
        return pkg_dry_run(args, action)

    return do_pkg_action(em, config, args, action)


def do_pkg_action(em, config, args, action) -> int:
    """Execute the install/uninstall and update the implicit spec."""
    using = args.using
    if not run_pkg_action(em, args.name, using, action, args.packages):
        return 1
    update_and_save_spec(config, args.name, args.packages, action, using)
    print_relock_suggestion(args.name, args.no_relock)
    return 0


def run_pkg_action(em, name, using, action, packages) -> bool:
    """Run the installer command in the live env."""
    if using == "mamba":
        return run_mamba_action(em, name, action, packages)
    return run_pip_action(em, name, using, action, packages)


def run_mamba_action(em, name, action, packages) -> bool:
    """Run a mamba install/remove action."""
    verb = "install" if action == "install" else "remove"
    cmd = f"{NBW_MAMBA_CMD} {verb} -n {name} -y {' '.join(packages)}"
    result = em.wrangler_run(cmd, check=False)
    return em.handle_result(result, f"Failed to {action} packages in '{name}': ")


def run_pip_action(em, name, using, action, packages) -> bool:
    """Run a pip/uv install/uninstall action."""
    installer = build_installer_str(using)
    verb = "install" if action == "install" else "uninstall"
    cmd = f"{installer} {verb} {' '.join(packages)}"
    result = em.env_run(name, cmd, check=False)
    return em.handle_result(result, f"Failed to {action} packages in '{name}': ")


def build_installer_str(using) -> str:
    """Build the installer command prefix string for pip/uv operations."""
    if using == "uv":
        return "uv pip"
    if using == "pip":
        return "pip"
    return str(NBW_PIP_CMD)  # default (None)


# -- dry-run helpers ---------------------------------------------------------


def pkg_dry_run(args, action) -> int:
    """Print dry-run output for install/uninstall."""
    cmd = build_pkg_cmd(args, action)
    delta = format_spec_delta(args.packages, action)
    print(f"Dry-run: would run: {cmd}")
    print(f"Spec delta: {delta}")
    return 0


def build_pkg_cmd(args, action) -> str:
    """Build the planned installer command string."""
    verb = "install" if action == "install" else "uninstall"
    using = args.using
    if using == "mamba":
        return f"{NBW_MAMBA_CMD} {verb} -n {args.name} -y {' '.join(args.packages)}"
    installer = build_installer_str(using)
    return f"{installer} {verb} {' '.join(args.packages)}"


def format_spec_delta(packages, action) -> str:
    """Format the package delta for display."""
    sign = "+" if action == "install" else "-"
    return ", ".join(f"{sign} {p}" for p in packages)


def print_relock_suggestion(name, no_relock) -> None:
    """Print the relock suggestion unless suppressed."""
    if not no_relock:
        print(
            f"Spec updated. Run `hubenv env relock {name}` "
            f"to re-curate locks and validate."
        )
