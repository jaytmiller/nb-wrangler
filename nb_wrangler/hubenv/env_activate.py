"""env activate/deactivate subcommands (equivalent to ``nbw --env-activate``).

Both activate and deactivate are pure: they emit a shell snippet to stdout
for the caller to ``eval``/source, with no writes to stdout beyond the
snippet, so the output is safely consumed via command substitution.
"""

import sys

from nb_wrangler import activation
from nb_wrangler.environment import EnvironmentManager
from nb_wrangler.hubenv._common import get_logger, var_export_lines
from nb_wrangler.hubenv.config import PantryStore


def cmd_env_activate(args) -> int:
    """Emit a shell snippet that activates ``args.name`` by absolute path."""
    em = EnvironmentManager()
    if not em.environment_exists(args.name):
        get_logger().error(
            f"Environment '{args.name}' does not exist locally "
            f"(looked under {em.nbw_mm_dir / 'envs'}). "
            f"Restore it first with `hubenv env ensure {args.name}`."
        )
        return 1
    env_path = em.env_live_path(args.name)
    extra = var_export_lines(args.name, PantryStore())
    snippet = activation.emit_activation(
        str(em.nbw_mm_dir),
        em.mamba_command,
        activation.detect_shell(),
        str(env_path),
        name=args.name,
        extra_exports=extra,
    )
    sys.stdout.write(snippet)
    return 0


def cmd_env_deactivate(args) -> int:
    """Emit a shell snippet that deactivates the current mamba environment."""
    em = EnvironmentManager()
    snippet = activation.emit_deactivate(em.mamba_command, activation.detect_shell())
    sys.stdout.write(snippet)
    return 0
