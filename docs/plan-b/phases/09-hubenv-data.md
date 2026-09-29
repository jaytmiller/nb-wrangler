# Phase 9 — `hubenv data` (data management)

> Deliverable: `hubenv data ls/download/unpack/pack/clean NAME [...]`. Depends on
> Phase 1; mirrors wrangler's existing `--data-*` flags.

## Goal

Data is a first-class concern on the science platform, so it gets its own
command group (rather than being an afterthought with no commands, as in the
original plan). These wrap the existing `nb_wrangler/cli.py` `--data-*` flags.

## Scope

**In:**
- `hubenv data ls NAME [--format table|json]` — list data archives for `NAME`.
- `hubenv data download NAME [--select REGEX] [--no-validate]` — download data
  archives to the pantry.
- `hubenv data unpack NAME [--no-unpack-existing] [--symlinks|--no-symlinks]` —
  unpack archives to live data dirs.
- `hubenv data pack NAME` — pack live data dirs back into archive files.
- `hubenv data clean NAME [archived|unpacked|both]` — delete data archives and/or
  unpacked files.

**Out:**
- Refdata spec editing (`refdata_dependencies.yaml`) — handled by wrangler's
  curation; not a `hubenv` command.

## Design notes

- **Direct delegation:** these are thin wrappers over `cli.py`'s
  `--data-list`/`--data-download`/`--data-unpack`/`--data-pack`/`--data-delete`
  flags (and `data_manager.py`). Don't reimplement download/symlink logic.
- **Location:** data archives live in the env's shelf
  (`${pantry}/shelves/<NAME>/archives/<data>*`), unpacked data under
  `NBW_ROOT/data/<NAME>/` (or the spec's configured data dir). Mirror
  `plan-b-flow.md`'s layout.
- **`--select REGEX`:** pick specific archives (from `--data-select`).

## Prerequisites / dependencies

- Phase 1 (pantry/shelf paths, `NBW_ROOT`).
- `nb_wrangler/data_manager.py` (the data subsystem).

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py` — replace `data` stub subcommands.
- **Create** `tests/hubenv/test_data.py` — fakes for list/download/unpack/pack/clean.

## Tasks

- [ ] `data ls`: list archives for `NAME` (from shelf + spec).
- [ ] `data download`: invoke wrangler download (optionally `--select`ed).
- [ ] `data unpack`: invoke wrangler unpack (`--symlinks` toggle).
- [ ] `data pack`: invoke wrangler pack.
- [ ] `data clean`: invoke wrangler delete (`archived|unpacked|both`).
- [ ] Tests: each subcommand invokes the right wrangler routine with the right
      flags (fakes).

## Testing / validation

```sh
make unit-test
make lint/flake8 && make lint/black && make lint/mypy
hubenv data ls demo
hubenv data download demo --select 'roman_.*'
hubenv data unpack demo
hubenv data clean demo archived
```

## Acceptance criteria

- `hubenv data ls demo` lists the archives for `demo`.
- `download`/`unpack`/`pack`/`clean` dispatch to the matching wrangler
  `--data-*` routine with the requested options.
- `--select REGEX` filters downloads to matching archives.
- `--symlinks|--no-symlinks` is forwarded to unpack.