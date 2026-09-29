# Phase 6 — `hubenv env rm`

> Deliverable: `hubenv env rm NAME... [--live | --archived | --both] [--yes]
> [--dry-run]`. Deletes envs from live and/or archive storage. Depends on
> Phases 1, 4.

## Goal

Safe cleanup of environments, with confirmations that account for env globbing
(which can match many shared envs). This is the explicit exception you
requested: **interactive by default, `--yes`/`-y` to skip** (apt/package
installer model), not opt-in.

## Scope

**In:**
- `hubenv env rm NAME... [--live | --archived | --both] [--yes] [--dry-run]`
  - `NAME...` accepts names or globs (e.g. `team-*`); resolves against live
    envs (`NBW_ROOT/envs/*`) and/or shelves (`NBW_PANTRY_DIRS/shelves/*`).
  - `--live` / `--archived` / `--both` select the target (default `--both`).
  - **Interactive by default:** for each matched env, print what will be
    removed (live path / shelf path) and confirm (y/N) before deleting.
  - `--yes`/`-y`: skip confirmation (scripts/automation).
  - `--dry-run`: print what would be removed without deleting.
  - After deleting a shelf's live env, optionally remove the now-empty shelf
    dir (best-effort; don't fail if non-empty due to data archives).

**Out:**
- Kernel unregistration is *not* automatic here — tell users to run
  `hubenv env unregister` separately (Phase 7), to avoid surprising notebook
  behavior. (A future `--unregister` flag could be added, but keep this phase
  focused on storage deletion.)

## Design notes

- **Globbing caution:** globs can match shared/team envs; that's exactly why
  confirmation is the default. Print the resolved list *before* prompting and
  require a final `y` to proceed.
- **r/o protection:** refuse to delete from a read-only pantry (clear message).
- **Live deletion:** remove `NBW_ROOT/envs/<NAME>/`. Best-effort; warn if the
  dir is in use (don't force-kill kernels — leave that to the user).
- **Safety:** never `rm -rf /` — validate that resolved paths are under
  `NBW_ROOT/envs/` or a `shelves/` dir, and reject anything that escapes.

## Prerequisites / dependencies

- Phase 1 (r/o detection, `NBW_ROOT`/`NBW_PANTRY_DIRS`).
- Phase 4 (`list_shelves`, `list_live_envs` for resolution).

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py` — replace `rm` stub.
- **Create** `tests/hubenv/test_rm.py` — fakes for globs, r/o refusal, `--yes`,
  `--dry-run`, path-escape safety.

## Tasks

- [x] Resolve `NAME...` (names + globs) against live envs and shelves.
- [x] Apply `--live/--archived/--both` filter.
- [x] Refuse r/o pantry targets with an actionable message.
- [x] Safety: validate every resolved path is under `NBW_ROOT/envs/` or a
      `shelves/` dir; reject escapes.
- [x] Confirmation prompt (y/N) by default; `--yes`/`-y` skips.
- [x] `--dry-run` prints the resolved targets and exits 0.
- [x] Delete selected; best-effort remove empty shelf dirs.
- [x] Tests: glob resolution, r/o refusal, `--yes` fast path, `--dry-run`
      no-op, path-escape rejection.

## Testing / validation

```sh
make unit-test
make lint/flake8 && make lint/black && make lint/mypy
hubenv env rm --dry-run 'demo-*'
hubenv env rm --yes demo
hubenv env rm team-*            # interactive; confirm then delete
hubenv env rm --pantry /ro/pantry --yes demo   # r/o -> error
```

## Acceptance criteria

- `hubenv env rm demo --dry-run` prints planned deletions and changes nothing.
- `hubenv env rm demo --yes` deletes without prompting.
- Without `--yes`, `hubenv env rm demo` prompts per env; `n` aborts.
- Globs resolve to all matches and are listed before prompting.
- Deleting from an r/o pantry fails with an actionable error.
- Path-escape targets are rejected (no deleting outside `NBW_ROOT`/`shelves`).