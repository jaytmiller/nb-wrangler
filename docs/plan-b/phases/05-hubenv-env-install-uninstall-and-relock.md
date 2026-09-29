# Phase 5 — `hubenv env install` / `uninstall` + `hubenv env relock`

> Deliverable: `hubenv env install/uninstall NAME PACKAGE... [--using=mamba|pip|uv]
> [--no-relock] [--dry-run]` and `hubenv env relock NAME [--dry-run]`. Depends on
> Phase 1 (and 4 for `ls`/`info` to inspect results).

## Goal

Let users update a live environment's package set *without* silently triggering
a multi-minute re-curate/re-lock loop. Install/uninstall update the live env +
record the change in the implicit spec; relock is a separate, explicit command.

## Scope

**In:**
- `hubenv env install NAME PACKAGE... [--using=mamba|pip|uv] [--no-relock] [--dry-run]`
- `hubenv env uninstall NAME PACKAGE... [--using=mamba|pip|uv] [--no-relock] [--dry-run]`
  - Delegate to the chosen installer on the live env (must be active/restored).
  - Record the new package list in the implicit spec (the in-memory/temp spec
    associated with `NAME`; for now, persist a small package list alongside the
    shelf or a temp spec — see "Design notes").
  - **Do not auto-trigger re-curate/re-lock.** Print:
    *"Spec updated. Run `hubenv env relock NAME` to re-curate locks and validate."*
  - `--no-relock` suppresses even that suggestion.
  - `--dry-run` previews the install plan.
- `hubenv env relock NAME [--dry-run]`
  - Explicitly re-curates the implicit wrangler spec (resolve dependencies,
    update lock files), mirroring `cli.py`'s `--curate`/`--packages-compile` +
    `--packages-install`.
  - `--dry-run` shows the resolved plan without writing.

**Out:**
- Actual notebook testing (`--test-notebooks`) — reuse wrangler's tests
  directly; not a `hubenv` command here. `--test-imports` can be offered as a
  relock option later.

## Design notes

- **`--using` default:** prefer the platform/uv convention (`NBW_PIP_CMD` for
  pip, `NBW_MAMBA_CMD` for mamba); `--using=uv` is just pip-via-uv. Picking
  explicitly per command avoids ambiguity.
- **Implicit spec persistence:** for a *live* env created by `hubenv env create`,
  the "implicit wrangler spec" is a temp/in-memory spec. To support `install`/
  `relock`, persist the seed spec + a package delta under the live env dir
  (e.g. `NBW_ROOT/envs/<NAME>/.hubenv-spec.yaml`) so relock has something to work
  on. Phase 1's `create` should write this. (If `create` is later reworked to
  use a full wrangler spec.yaml, wire `install`/`relock` to that instead.)
- **Honest cost:** install/uninstall are fast (single installer op); relock is
  the slow one. Keeping them separate prevents the "I typed install, why is it
  curating for 5 minutes?" surprise flagged in the original critique.
- **Reuse:** call `cli.py`'s package-install/relock routines or the
  `compiler.py`/`environment.py` equivalents, not a new resolver.

## Prerequisites / dependencies

- Phase 1 (`create` writing an implicit spec for the live env).
- `nb_wrangler/compiler.py` (package compile) + `environment.py` (install) for
  relock's internals.

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py` — replace `install`/`uninstall`/`relock`
  stubs.
- **Create** `tests/hubenv/test_install_relock.py` — fakes for install/relock;
  `--no-relock` suppression; `--dry-run` output.

## Tasks

- [ ] `install`/`uninstall`: resolve `--using`; run the installer on the live
      env (reuse existing env-exec + subprocess routine); error if live env
      missing.
- [ ] Update the implicit spec's package list (add for install, remove for
      uninstall) in `NBW_ROOT/envs/<NAME>/.hubenv-spec.yaml`.
- [ ] Print the relock suggestion unless `--no-relock`.
- [ ] `--dry-run` prints the installer command + spec delta, exits 0.
- [ ] `relock`: load the implicit spec for `NAME`, re-curate (resolve deps,
      update locks) via wrangler's compile path; `--dry-run` shows resolved
      set without writing.
- [ ] Tests: install adds package to spec + prints suggestion; `--no-relock`
      suppresses message; uninstall removes; relock dry-run parses.

## Testing / validation

```sh
make unit-test
make lint/flake8 && make lint/black && make lint/mypy
hubenv env install demo numpy pandas
hubenv env install demo numpy --no-relock
hubenv env relock demo
hubenv env relock demo --dry-run
```

## Acceptance criteria

- `hubenv env install demo numpy` installs numpy into the live env and records it
  in the implicit spec.
- It prints *"Run `hubenv env relock NAME`..."* unless `--no-relock`.
- `--dry-run` changes nothing and prints the planned action.
- `hubenv env relock demo` re-curates locks and validates (reusing wrangler).
- `install`/`uninstall` never kick off a relock automatically.