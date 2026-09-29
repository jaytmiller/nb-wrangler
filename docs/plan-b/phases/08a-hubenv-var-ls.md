# Phase 8a — `hubenv var ls` (read env vars from the spec)

> Deliverable: `hubenv var ls NAME [GLOB...] [--export] [--format table|json]`.
> Depends on Phase 1. *Not* Phase 7 — reads the spec only; no kernel refresh.

## Goal

Read the environment variables a PPE environment declares and render them for
humans or machines. Source of truth is the implicit wrangler spec's
`environment_vars` section — a *curated subset*, never a dump of `printenv`.

## Scope

**In:**
- `hubenv var ls NAME [GLOB...] [--export] [--format table|json]`
  - Reads `environment_vars` from the implicit spec for `NAME`.
  - No positional `GLOB...`: show all declared vars.
  - `GLOB...` positional: filter by variable name glob.
  - Default output: two-column table (`VAR`, `VALUE`), vars in sorted order.
  - `--export`: print `export VAR=VALUE` lines (suitable for
    `eval "$(hubenv var ls NAME --export)"`).
  - `--format table|json`. JSON shape:
    `{"name": NAME, "environment_vars": {"VAR": "VALUE", ...}}` (sorted keys).
  - A name with no spec / no `environment_vars` key: prints a helpful
    `(no environment variables defined for '<name>')` line and exits 0.

**Out:**
- Mutations (`add`/`rm`) — deferred to Phase 8b.
- Managing vars via shell dotfiles ("var exports rc") — explicitly *not* done.
- Kernel refresh — not needed for a read.

## Design notes

- **Read-only.** Loads the spec via the existing `_load_ppe_spec` helper; if
  the spec file is absent it falls back to a base empty spec and reads an
  empty `environment_vars` dict — no crash.
- **`ls` scope = spec-declared vars only.** Matches the consolidated spec's
  "very limited subset" design note.
- **Sorted, deterministic output** so `eval` output is stable across runs.

## Prerequisites / dependencies

- Phase 1 (implicit spec for `NAME`).
- The `var` top-level group exists (wired in `build_parser`).
- Does **not** require Phase 7 (`register`).

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py`:
  - Add `_add_var_subcommands` (or extend it) so `ls` parses `name`,
    `globs`, `--export`, `--format`.
  - Add `_dispatch_var` routing `ls` → `_cmd_var_ls`.
  - Add `_cmd_var_ls`, `_filter_vars_by_glob`, `_print_var_ls_table`,
    `_print_var_ls_export`, `_print_var_ls_json`.
- **Create** `tests/hubenv/test_var.py` (ls subset):
  - Helpers: `_write_spec` / `_read_spec` writing a minimal spec with an
    `environment_vars` dict to `NBW_ROOT/envs/<NAME>/.hubenv-spec.yaml`;
    `NBW_ROOT` patched via `patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path)`.
  - Tests: table default; sorted order; `--export`; `--format json`; glob
    filter (`API_*` excludes `DB`); empty vars message; missing spec no crash.

## Tasks

- [x] `var ls`: load spec; default two-column table; sorted output.
- [x] `var ls --export`: print `export VAR=VALUE` lines.
- [x] `var ls --format json`: print JSON object with sorted keys.
- [x] `var ls NAME GLOB...`: filter by glob.
- [x] Empty / missing-spec handling: helpful message, exit 0.
- [x] Tests for all of the above (fakes for the spec file).

## Testing / validation

```sh
make unit-test TESTS=tests/hubenv/test_var.py
make lint/flake8 && make lint/black && make lint/mypy
hubenv var ls demo
hubenv var ls demo --export | head
hubenv var ls demo API_*
hubenv var ls demo --format json
```

## Acceptance criteria

- `hubenv var ls demo` lists the spec-declared vars (table by default, sorted).
- `--export` prints `export VAR=VALUE` lines.
- `--format json` prints a JSON object with `name` + `environment_vars`.
- `hubenv var ls demo GLOB` filters vars by name glob.
- No crash / helpful message when the env has no spec or no vars.
- No spec or kernel is modified by `ls`.