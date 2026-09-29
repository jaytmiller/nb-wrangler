# Phase 3 — `hubenv env restore`

> Deliverable: `hubenv env restore NAME [--pantry PATH] [--force] [--at-boot]`
> unpacks a saved "can" to a live env and registers it as a Jupyter kernel.
> Depends on Phases 1–2.

## Goal

Make a previously archived environment usable again: unpack it from a pantry
into `NBW_ROOT` (fast, ~20–30s, vs. multi-minute reinstall), register the
Jupyter kernel, and print `eval`-able shell exports. This is the core
"persistent environment" value proposition.

## Scope

**In:**
- `hubenv env restore NAME`:
  1. Finds the shelf in `NBW_PANTRY_DIRS` (first writable match, or `--pantry`).
  2. Idempotency: if `pantry last-save-hash` == `live last-restore-hash`, skip
     unpack (unless `--force`).
  3. Unpacks the can into `NBW_ROOT/envs/<NAME>`.
  4. Registers the Jupyter kernel (so notebooks can select `<NAME>`).
  5. Prints `eval`-able exports (live env activation) to stdout.
- `--pantry PATH`: force source pantry.
- `--force`: skip the idempotency skip and re-unpack.
- `--at-boot`: registers a non-interactive, idempotent restore for startup
  (`.bashrc`/spawn hook) — replaces the "edit your dotfiles" workaround from
  the original plan. Implementation: append a guarded line to `.bashrc` (or a
  marker file) that runs `hubenv env ensure NAME` on shell start.
- Refuses to read from an r/o pantry? No — r/o read is fine; only writes to
  `NBW_ROOT` matter (and `NBW_ROOT` is live/container storage, normally w/r).

**Out:**
- Kernel unregistration, `hubenv env rm`, full disambiguation (Phase 4 adds
  multi-match warnings; here `restore` errors if a name matches multiple
  pantries unless `--pantry` is given).

## Design notes

- **Unpack reuse:** call/parallel `environment.py`'s unpack routine (the
  counterpart to Phase 2's pack). The can is a tarball assumed rooted at the
  env install dir; unpack into `NBW_ROOT/envs/<NAME>`.
- **Kernel registration:** reuse `nb_wrangler/registry.py` (kernel JSON
  management). The kernel `argv` must point at the restored env's python/kernel.
- **Eval-able exports:** mirror the existing `nb-wrangler setenv` hook
  (hook mamba shell, set env vars for the live env path so `mamba activate
  NAME` works and PPE env vars are present). Print lines like
  `export NBW_ACTIVE_ENV=NAME` and the mamba hook activation.
- **`--at-boot` safety:** write a *guarded*, idempotent snippet (check
  `NBW_ACTIVE_ENV` / a marker so we don't restore twice) and tell the user
  what was appended; never clobber `.bashrc`.
- **Multi-match:** if `NAME` resolves in >1 pantry without `--pantry`, error
  with the list of matches (Phase 4 will offer `--all`/selection; restore is
  single-target by nature).

## Prerequisites / dependencies

- Phases 1–2 (`hubenv` scaffold, r/o detection, can layout + save-hash).
- `nb_wrangler/environment.py` unpack routine.
- `nb_wrangler/registry.py` kernel registration.

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py` — implement `restore` (replace Phase 1
  stub).
- **Modify** `nb_wrangler/hubenv/config.py` — add `find_shelves(name)` returning
  all matching `(pantry, shelf)` pairs across `NBW_PANTRY_DIRS`.
- **Modify** `nb_wrangler/hubenv/cli.py` — add `--at-boot` snippet writer.
- **Create** `tests/hubenv/test_restore.py` — fakes for unpack + kernel reg;
  idempotency; multi-match error; `--at-boot` snippet content.

## Tasks

- [ ] `find_shelves(NAME)` across `NBW_PANTRY_DIRS`; error if >1 match and no
      `--pantry`.
- [ ] Idempotency check: compare shelf save-hash vs. live restore-hash; skip
      unpack if equal (unless `--force`).
- [ ] Unpack the can into `NBW_ROOT/envs/<NAME>` via wrangler unpack.
- [ ] Register the Jupyter kernel for `<NAME>` (registry.py).
- [ ] Record live restore-hash for the next idempotency check.
- [ ] Print `eval`-able exports (mamba hook + env activation + PPE vars).
- [ ] `--at-boot`: append a guarded idempotency snippet to `.bashrc` (or
      `~/.hubenv/env-<NAME>.sh`) and report what was added.
- [ ] `--force` skips idempotency and re-unpacks.
- [ ] Tests: happy path (fakes), idempotency skip, multi-match error,
      `--at-boot` snippet correctness.

## Testing / validation

```sh
make unit-test
make lint/flake8 && make lint/black && make lint/mypy
# end-to-end (requires a saved can from Phase 2):
hubenv env save demo
hubenv env restore demo            # second call should be idempotent (skip)
hubenv env restore demo --force
eval "$(hubenv env restore demo)"  # should activate in current shell
jupyter kernelspec list         # should show 'demo'
```

## Acceptance criteria

- `hubenv env restore demo` unpacks the can and registers a `demo` Jupyter kernel.
- A second `hubenv env restore demo` (with no changes) skips unpack (idempotent).
- `--force` re-unpacks regardless of hash match.
- `eval "$(hubenv env restore demo)"` activates the env in the current shell.
- `--at-boot` writes a guarded, idempotent snippet to `.bashrc` and reports it.
- A name matching multiple pantries (without `--pantry`) errors with the
  list of matches instead of silently picking the first.