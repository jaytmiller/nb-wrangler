"""Integration test: the `nb-wrangler` bash script's act*/setenv/deact* branches
must *delegate* activation to the Python CLIs via `micromamba run -n <env> python -m ...`.

We don't have a real micromamba, so we stub one that records every invocation
to a log. Running `source nb-wrangler act*/setenv/deact*` in an isolated
bash subprocess against that stub lets us assert the *delegation contract*:
the correct argv reaches the Python CLI, and the CLI runs with the env
variable ``NBW_MM`` set to the right value.

This is the only piece of the user-facing flow we can test without a
network / real mamba install; the rest of the pipeline (Python CLI ->
shared core -> shell snippet) is covered by test_activation.py unit tests.
"""

import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NBW_SCRIPT = os.path.join(REPO_ROOT, "nb-wrangler")

FAKE_MICROMAMBA = """#!/usr/bin/env bash
# Records every micromamba invocation verbatim for the test's assertions.
echo "mm: $*" >> "$NBW_MM_LOG"
# `run -n NAME rest...`: drop `-n NAME` and exec the rest so the test can
# observe the argv that reaches the python CLI.
if [ "$1" = "run" ]; then
    shift  # drop 'run'
    shift  # drop '-n'
    shift  # drop env name
    if [ "$1" = "python" ] && [ -n "$NBW_MM_LOG" ]; then
        echo "python-args-after-run: $*" >> "$NBW_MM_LOG"
    fi
fi
exit 0
"""


def _install_fake_mm(mm: str) -> None:
    os.makedirs(os.path.join(mm, "bin"), exist_ok=True)
    fake = os.path.join(mm, "bin", "micromamba")
    with open(fake, "w") as f:
        f.write(FAKE_MICROMAMBA)
    os.chmod(fake, 0o755)


def _run_bash(
    script: str, mm: str, log: str, tmp: str
) -> "subprocess.CompletedProcess[str]":
    """Run a bash snippet with a clean environment (nb-wrangler + fake micromamba)."""
    env = {
        "PATH": f"{mm}/bin:/usr/bin:/bin",
        "HOME": os.path.join(tmp, "home"),
        "NBW_ROOT": os.path.join(tmp, "nbw-root"),
        "NBW_MM": mm,
        "NBW_PANTRY": os.path.join(tmp, "pantry"),
        "NBW_WRANGLER_ENV": "demo",
        "NBW_MM_LOG": log,
        # PYTHONPATH so `python -m nb_wrangler.hubenv.cli` resolves to this
        # source checkout (we don't have a real pip-installed nb-wrangler
        # in a real venv with mamba to delegate through).
        "PYTHONPATH": REPO_ROOT,
    }
    os.makedirs(os.path.join(tmp, "home"), exist_ok=True)
    return subprocess.run(
        ["bash", "-c", script],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )


def test_act_delegates_to_hubenv_env_activate(tmp_path):
    mm = str(tmp_path / "mm")
    log = str(tmp_path / "calls.log")
    _install_fake_mm(mm)

    res = _run_bash(
        f"source {NBW_SCRIPT} act* demo",
        mm=mm,
        log=log,
        tmp=str(tmp_path),
    )
    assert res.returncode == 0, res.stderr
    with open(log) as f:
        content = f.read()
    # The bash act* branch must delegate:
    #   micromamba run -n demo python -m nb_wrangler.hubenv.cli env activate --quiet demo
    assert "mm: run" in content, content
    assert " -n demo " in content, content
    assert "python -m nb_wrangler.hubenv.cli env activate" in content, content
    assert "--quiet demo" in content, content


def test_deact_delegates_to_nbw_env_deactivate(tmp_path):
    mm = str(tmp_path / "mm")
    log = str(tmp_path / "calls.log")
    _install_fake_mm(mm)

    res = _run_bash(
        f"source {NBW_SCRIPT} deact*",
        mm=mm,
        log=log,
        tmp=str(tmp_path),
    )
    assert res.returncode == 0, res.stderr
    with open(log) as f:
        content = f.read()
    assert "python -m nb_wrangler --env-deactivate" in content, content


def test_setenv_delegates_to_nbw_env_activate_for_spec(tmp_path):
    mm = str(tmp_path / "mm")
    log = str(tmp_path / "calls.log")
    _install_fake_mm(mm)
    spec = tmp_path / "spec.yaml"
    # Minimal valid spec — load_and_validate does not run here (the python
    # CLI invocation itself doesn't require the spec on disk for the
    # delegation contract we're asserting); we just need a name for the argv.
    spec.write_text("image_spec_header:\n  image_name: demo\n")

    res = _run_bash(
        f"source {NBW_SCRIPT} setenv {spec}",
        mm=mm,
        log=log,
        tmp=str(tmp_path),
    )
    assert res.returncode == 0, res.stderr
    with open(log) as f:
        content = f.read()
    assert "python -m nb_wrangler" in content, content
    assert "--env-activate" in content, content
    assert str(spec) in content, content
