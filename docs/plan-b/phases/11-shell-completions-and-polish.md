# Phase 11 — Shell completions + polish + end-to-end validation

> Deliverable: bash/zsh/fish completions, an end-to-end test of the full MVP
> (create → save → restore → install → relock → rm), and any final polish.
> Depends on all prior phases.

## Goal

Make `ppe` pleasant to use interactively (completions), prove the whole MVP
works as a unit, and leave the implementation in a shippable state.

## Scope

**In:**
- Shell completions for bash, zsh, and fish (ship as a generated script +
  instructions to source it; optionally install into the user's shell rc via a
  `ppe completions install` sub-helper or just document it).
- End-to-end test: `ppe env create` → `ppe env save` → `ppe env restore` →
  `ppe env install` → `ppe env relock` → `ppe env rm`, against a temp
  `NBW_ROOT`/`NBW_PANTRY` (fakes for the heavy install/unpack should be used so
  the test is fast and needs no network; assert the command flow + state
  transitions).
- Final polish pass: ensure every subcommand has `--help`, errors are clean
  (no tracebacks), and `make lint/flake8` + `make lint/black` + `make lint/mypy`
  pass across the new `nb_wrangler/ppe/` package.
- Update the consolidated `docs/plan-b/plan-b-cli.md` "Relationship to existing
  modules" / validation section if anything drifted (it shouldn't by now).

**Out:**
- A Jupyter labextension kernel picker (out of scope, per Phase 10).

## Design notes

- **Completions:** argparse can render its own completions via
  `argcomplete` (already a common choice) or generate `ppe`'s help for
  shellcomp; if `argcomplete` isn't a dependency, emit a static completion
  script for the known subcommand trees. Static is simpler and dependency-free.
- **E2E test isolation:** set `NBW_ROOT`/`NBW_PANTRY` to temp paths; use fakes
  for micromamba/venv creation so the test doesn't actually install Python
  packages. The test asserts: env appears in `ppe env ls` after create, shelf
  + can exist after save, kernel registered after restore, package recorded
  after install, locks updated after relock, env gone after rm.
- **No tracebacks:** wrap `main()` in a try/except that maps known errors to
  exit codes + messages.

## Prerequisites / dependencies

- All prior phases (the full `ppe` surface exists).

## Files to create / modify

- **Create** `nb_wrangler/ppe/completions.py` — generate bash/zsh/fish
  completion scripts (static).
- **Create** `tests/ppe/test_e2e.py` — the end-to-end flow with fakes.
- **Modify** `nb_wrangler/ppe/cli.py` — final polish (help text, error
  mapping, no tracebacks).
- **Modify** `pyproject.toml` — ensure `ppe` script entry is present (Phase 1
  should have done this; verify).

## Tasks

- [ ] Static completion script generator for bash/zsh/fish; `ppe completions
      bash|zsh|fish` prints the script.
- [ ] End-to-end test with temp `NBW_ROOT`/`NBW_PANTRY` + fakes for install.
- [ ] Final polish: consistent `--help`, clean error messages, exit codes.
- [ ] `main()` try/except wraps all commands (no raw tracebacks to users).
- [ ] `make lint/flake8`, `make lint/black`, `make lint/mypy` pass on the
      whole `nb_wrangler/ppe/` package.
- [ ] `make unit-test` includes `tests/ppe/`.
- [ ] Verify `docs/plan-b/plan-b-cli.md` still matches implementation.

## Testing / validation

```sh
make unit-test            # includes tests/ppe/ (unit + e2e)
make lint/flake8 && make lint/black && make lint/mypy
ppe completions bash      # print bash completion script
# manual smoke:
eval "$(ppe env restore demo)"
jupyter kernelspec list   # shows demo
```

## Acceptance criteria

- `ppe completions bash|zsh|fish` prints a working completion script.
- The end-to-end test passes (create→save→restore→install→relock→rm) with
  fakes, using temp paths.
- No `ppe` command exits with a raw traceback on expected errors.
- `make lint/flake8`, `make lint/black`, `make lint/mypy` pass across
  `nb_wrangler/ppe/`.
- `docs/plan-b/plan-b-cli.md` accurately describes the final implemented CLI.