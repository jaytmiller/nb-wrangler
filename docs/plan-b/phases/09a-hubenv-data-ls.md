# Phase 9a — `hubenv data ls` (list data archives)

> Deliverable: `hubenv data ls NAME [--format table|json]`. Depends on
> Phase 1; reads the shelf + spec only. *Not* download/unpack/pack/clean.

## Goal

List the data archives a PPE environment declares — a read-only inspection of
the env's shelf and spec. Mirrors wrangler's `--data-list` flag; does not fetch
or modify anything on disk.

## Scope

**In:**
- `hubenv data ls NAME [--format table|json]`
  - Reads the archives for `NAME` from the env's shelf
    (`${pantry}/shelves/<NAME>/archives/<data>*`) and the implicit spec's data
    section.
  - Default output: two-column table (`ARCHIVE`, `SIZE`).
  - `--format table|json`. JSON shape:
    `{"name": NAME, "archives": ["<data>", ...]}` (sorted).
  - A name with no spec / no archives: prints a helpful
    `(no data archives defined for '<name>')` line and exits 0.

**Out:**
- Fetching archives (`download`), extracting (`unpack`), bundling (`pack`),
  deleting (`clean`) — deferred to Phase 9b/9c.
- Refdata spec editing (`refdata_dependencies.yaml`) — handled by wrangler's
  curation; not a `hubenv` command.

## Design notes

- **Read-only.** Loads the spec via `_load_ppe_spec` (shared with Phase 7);
  iterates the shelf's `archives/` dir for present files. No network, no
  writes to the pantry or live data dirs.
- **`ls` scope = archives the spec declares that are present on disk.** Matches
  `plan-b-flow.md`'s layout (archives under
  `${pantry}/shelves/<NAME>/archives/`, unpacked under
  `NBW_ROOT/data/<NAME>/`).
- **Deterministic output** (sorted) so JSON output is stable across runs.

## Prerequisites / dependencies

- Phase 1 (pantry/shelf paths, `NBW_ROOT`).
- `nb_wrangler/data_manager.py` (the data subsystem) — read path.
- The `data` top-level group exists (wired in `build_parser`, Phase 1).

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py` — add `_add_data_subcommands` (or extend
  it) so `ls` parses `name` + `--format`; add `_dispatch_data` routing `ls` →
  `_cmd_data_ls`. Add `_cmd_data_ls`, `_print_data_ls_table`,
  `_print_data_ls_json`.
- **Create** `tests/hubenv/test_data.py` (ls subset):
  - Helpers: `_write_spec` / `_read_spec` writing a minimal spec with a data
    section to `NBW_ROOT/envs/<NAME>/.hubenv-spec.yaml`;
    `NBW_ROOT` patched via `patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path)`.
  - Tests: table default; sorted order; `--format json`; empty archives message;
    missing spec no crash.

## Tasks

- [x] `data ls`: load spec + enumerate shelf archives for `NAME`.
- [x] `data ls`: default two-column table (sorted).
- [x] `data ls --format json`: print JSON object with `name` + `archives`.
- [x] Empty / missing-spec handling: helpful message, exit 0.
- [x] Tests: table vs json; sorted order; empty message; missing spec no crash
      (fakes for spec + shelf dir).

## Testing / validation

```sh
make unit-test TESTS=tests/hubenv/test_data.py
make lint/flake8 && make lint/black && make lint/mypy
hubenv data ls demo
hubenv data ls demo --format json
```

## Acceptance criteria

- `hubenv data ls demo` lists the archives for `demo` (table by default, sorted).
- `--format json` prints a JSON object with `name` + `archives`.
- A name with no archives prints a helpful message and exits 0.
- No spec, pantry, or live data dir is modified by `ls`.