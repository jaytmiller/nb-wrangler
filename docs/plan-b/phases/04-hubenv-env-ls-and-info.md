# Phase 4 — `hubenv env ls` + `info` + shadowing disambiguation

> Deliverable: `hubenv env ls [NAME-or-glob...] [--all] [--pantry PATH]
> [--format table|json]` and `hubenv env info NAME [--pantry PATH]`. Depends on
> Phase 1.

## Goal

Let users see what environments exist where (live + every pantry), and surface
shadowing clearly — the core safety feature for multi-pantry PATH-like lookups.

## Scope

**In:**
- `hubenv env ls`:
  - Finds `pantry@NAME` shelves across all `NBW_PANTRY_DIRS`.
  - Lists live envs under `NBW_ROOT/envs/*` (marked with `*`).
  - `--all`: list every match (don't collapse to first).
  - `--pantry PATH`: restrict search to one pantry.
  - `--format table|json`.
  - Reports r/w vs r/o per pantry and per shelf.
- `hubenv env info NAME [--pantry PATH]`:
  - Disambiguates a name: shows which pantry each match lives in, the
    live/restore hash pairing, kernel registration state, and the source spec
    used to seed it.
- **Shadowing warnings:** in `ls` and `info`, warn when one name is present in a
  higher-priority pantry than a lower-priority one (so users notice a personal
  copy shadowing a team copy).

**Out:**
- `restore`/`save` already pick the first match; this phase only adds
  visibility + `--pantry`/`--all` to override that. (No change to save/restore
  behavior — they gain safety via the visibility here.)

## Design notes

- **Live envs:** scan `NBW_ROOT/envs/*/` directories.
- **Shelves:** scan `${pantry}/shelves/*/` per `NBW_PANTRY_DIRS`.
- **Disambiguation contract (reused by restore):** a `NAME` resolving in >1
  pantry is *warned* in `ls`, *listed* in `info`, and *errors* in `restore`
  unless `--pantry` is given (see Phase 3). `ls` defaults to first-match for
  readability but `--all` shows all.
- **r/o:** reuse Phase 1's `is_writable()`; show a column `(r/o)`.

## Prerequisites / dependencies

- Phase 1 (`hubenv/config.py` with `NBW_PANTRY_DIRS`, r/o detection).

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py` — replace `ls`/`info` stubs.
- **Modify** `nb_wrangler/hubenv/config.py` — add `list_shelves(name_or_glob=None,
  pantry=None)` and `list_live_envs()`.
- **Create** `tests/hubenv/test_ls_info.py` — multi-pantry fakes; shadowing warning;
  `--all`; `--format json`; r/o column.

## Tasks

- [ ] `list_shelves(glob=None, pantry=None)` → list of (pantry, shelf, r/o, save-hash).
- [ ] `list_live_envs()` → list of live env names under `NBW_ROOT/envs/`.
- [ ] `hubenv env ls`: merge live + shelves; mark live with `*`; first-match
      collapse by default; `--all` disables; `--pantry` filters; `--format
      table|json`; print r/o status.
- [ ] Shadowing detection: for each name present in >1 pantry, emit a warning
      line naming the pantries in priority order.
- [ ] `hubenv env info NAME`: show all matches with full metadata + kernel state.
- [ ] Tests: two-pantry fake; shadowing warning present; `--all` shows both;
      r/o column correct; json parses.

## Testing / validation

```sh
make unit-test
make lint/flake8 && make lint/black && make lint/mypy
hubenv env ls
hubenv env ls --all
hubenv env ls --pantry /teams/admin/nbw-pantry
hubenv env info demo --format json
```

## Acceptance criteria

- `hubenv env ls` lists live envs and pantry shelves, marking live with `*`.
- A name present in multiple pantries produces a shadowing warning in `ls`.
- `--all` shows every match; without it, reads are first-match (documented).
- r/o pantries appear with an `(r/o)` column.
- `hubenv env info NAME` lists all matching `pantry@NAME` pairs with hash +
  kernel state.