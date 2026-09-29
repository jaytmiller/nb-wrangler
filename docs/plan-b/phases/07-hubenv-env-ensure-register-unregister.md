# Phase 7 — `hubenv env ensure` + `register` / `unregister`

> Deliverable: `hubenv env ensure NAME [--pantry PATH]`, `hubenv env register NAME`,
> `hubenv env unregister NAME`. Depends on Phases 1, 3 (restore/kernel), 4.

## Goal

Idempotent "I need this env available" semantics for startup hooks/dotfiles,
plus explicit Jupyter kernel management decoupled from restore.

## Scope

**In:**
- `hubenv env ensure NAME [--pantry PATH]`
  - Idempotent restore-or-create:
    - If a **live** env exists for `NAME` → no-op, exit 0.
    - Else if an **archive shelf** exists → restore it (calls Phase 3 restore).
    - Else → report "no live env and no archive for `<NAME>`; run
      `hubenv env create ... --name <NAME>`" and exit non-zero.
  - Safe to call from `.bashrc`/spawn hooks: never prompts, never interactive.
- `hubenv env register NAME`
  - (Re)register the Jupyter kernel for an already-restored live env, using
    `nb_wrangler/registry.py` kernel-JSON management. Useful when the kernel is
    stale but the env is fine.
- `hubenv env unregister NAME`
  - Remove the kernel spec from Jupyter's registry (does *not* delete storage).

**Out:**
- `--at-boot` for `ensure` is already handled in Phase 3's restore; this phase
  exposes `ensure` so startup hooks can call a single idempotent verb.

## Design notes

- **Idempotency contract:** `ensure` must be side-effect-free when the env is
  already live. Check `NBW_ROOT/envs/<NAME>` existence first.
- **`register`/`unregister` reuse:** `registry.py` builds the kernel `argv`
  pointing at `<NBW_ROOT>/envs/<NAME>/bin/` and writes/ removes the kernelspec
  JSON. Don't hand-roll Jupyter dirs.
- **No prompts:** `ensure` is explicitly non-interactive (the whole point).

## Prerequisites / dependencies

- Phase 3 (`restore` for the archive→live path).
- Phase 4 (`list_shelves`/`list_live_envs` for the existence checks).
- `nb_wrangler/registry.py` for kernel JSON.

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py` — replace `ensure`/`register`/
  `unregister` stubs.
- **Create** `tests/hubenv/test_ensure_register.py` — fakes: live present (no-op),
  archive present (calls restore), neither (exit non-zero); register writes
  kernelspec; unregister removes it.

## Tasks

- [ ] `ensure`: check live → no-op; else check shelf → restore; else error.
- [ ] `ensure` is fully non-interactive.
- [ ] `register`: write/update kernelspec JSON for `NAME` via registry.py.
- [ ] `unregister`: remove kernelspec for `NAME` via registry.py (no storage
      deletion).
- [ ] Tests: three ensure branches; register/unregister round-trip (fakes).

## Testing / validation

```sh
make unit-test
make lint/flake8 && make lint/black && make lint/mypy
hubenv env ensure demo           # live -> no-op; archive -> restore; neither -> error
hubenv env register demo
hubenv env unregister demo
jupyter kernelspec list       # reflect register/unregister
```

## Acceptance criteria

- `hubenv env ensure demo` is idempotent and non-interactive.
- When only an archive exists, `ensure` restores it.
- When neither live nor archive exists, `ensure` exits non-zero with a helpful
  create- suggestion.
- `register`/`unregister` add/remove the Jupyter kernel without touching
  storage.