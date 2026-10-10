"""Shared shell-activation helpers for ``nbw`` and ``hubenv``.

A Python process cannot mutate its parent shell, so activation is achieved
by emitting a snippet that the caller ``eval``s (or sources) in the user's
shell.  Both CLIs build on this single implementation, producing *equivalent*
activation for a spec (``nbw``) and a named environment (``hubenv``).

The snippet activates by **absolute path** and pins ``MAMBA_ROOT_PREFIX`` so
it works even when the user's shell runs a different mamba/micromamba (a
"foreign" environment) whose ``MAMBA_ROOT_PREFIX`` has no visibility into the
nb-wrangler env directory.

These functions are pure: no logging, no config, no import-time reads of
``NBW_MM``/``NBW_MAMBA_CMD`` (which are evaluated at import time in
:mod:`nb_wrangler.constants`).  Paths and commands are passed in explicitly
so the output is deterministic and testable.
"""

import os
import shlex
from typing import Optional, Iterable, Mapping

SUPPORTED_SHELLS = ("bash", "zsh", "fish")


def detect_shell(env: Optional[Mapping[str, str]] = None) -> str:
    """Detect the current shell, returning ``bash``/``zsh``/``fish``.

    Uses ``NBW_SHELL`` if set, otherwise the shell version globals it may
    have exported, then falls back to ``$SHELL``/``$0``; defaults to bash.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    if source.get("NBW_SHELL"):
        return source["NBW_SHELL"]
    if source.get("ZSH_VERSION"):
        return "zsh"
    if source.get("BASH_VERSION"):
        return "bash"
    if source.get("FISH_VERSION"):
        return "fish"
    for key in ("SHELL", "0"):
        basename = os.path.basename(source.get(key, ""))
        if basename in SUPPORTED_SHELLS:
            return basename
    return "bash"


def _q(value: str) -> str:
    """Quote a value for inclusion in the emitted snippet."""
    return shlex.quote(str(value))


def _export_line(var: str, value: str, shell: str) -> str:
    """Emit a shell-appropriate ``VAR=value`` assignment line."""
    if shell == "fish":
        return f"set -gx {var} {_q(value)}"
    return f"export {var}={_q(value)}"


def _hook_line(mamba_cmd: str, shell: str) -> str:
    """Emit a shell-appropriate line that installs the mamba activate hook."""
    if shell == "fish":
        return f"eval ({_q(mamba_cmd)} shell hook)"
    return f'eval "$({_q(mamba_cmd)} shell hook 2>/dev/null)"'


def activation_lines(
    nbw_mm: str, mamba_cmd: str, shell: str, env_path: str
) -> list[str]:
    """Common activation snippet lines: pin root prefix, hook, activate by path."""
    return [
        _export_line("MAMBA_ROOT_PREFIX", nbw_mm, shell),
        _hook_line(mamba_cmd, shell),
        f"{_q(mamba_cmd)} activate {_q(env_path)}",
    ]


def emit_activation(
    nbw_mm: str,
    mamba_cmd: str,
    shell: str,
    env_path: str,
    *,
    name: Optional[str] = None,
    extra_exports: Optional[Iterable[str]] = None,
) -> str:
    """Build a complete activation snippet for a mamba environment.

    Mirrors the ``nb-wrangler`` script's ``setup_env``/activate block but
    activates by absolute path so a foreign mamba/micromamba can still find
    the environment.
    """
    lines: list[str] = []
    if name:
        lines.append(_export_line("NBW_ACTIVE_ENV", name, shell))
        lines.append(_export_line("NBW_ENV_ROOT", env_path, shell))
    lines.extend(activation_lines(nbw_mm, mamba_cmd, shell, env_path))
    if extra_exports:
        lines.extend(extra_exports)
    return "\n".join(lines) + "\n"


def emit_deactivate(mamba_cmd: str, shell: str) -> str:
    """Build a deactivate snippet (install hook if needed, then deactivate)."""
    return (
        "\n".join([_hook_line(mamba_cmd, shell), f"{_q(mamba_cmd)} deactivate"]) + "\n"
    )
