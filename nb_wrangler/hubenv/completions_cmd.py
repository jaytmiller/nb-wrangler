"""completions subcommand: print shell completion scripts."""

import sys

from nb_wrangler.hubenv import completions as completions_mod


def cmd_completions(args) -> int:
    """Handle ``hubenv completions bash|zsh|fish``."""
    script = completions_mod.generate_completion(args.shell)
    if script is None:
        print(
            f"Unknown shell '{args.shell}'. "
            f"Supported: {', '.join(completions_mod.get_supported_shells())}",
            file=sys.stderr,
        )
        return 1
    print(script, end="")
    return 0


# Backward-compat re-export


def _cmd_completions(args) -> int:
    """Backward-compat alias for ``cmd_completions``."""
    return cmd_completions(args)
