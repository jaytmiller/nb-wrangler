# Phase 9b — `ppe data download` / `ppe data unpack` (populate the environment)

> Deliverable: `ppe data download NAME [--select REGEX] [--no-validate]` and
> `ppe data unpack NAME [--no-unpack-existing] [--symlinks|--no-symlinks]`.
> Depends on Phase 9a (`data` group + shelf/spec helpers) and Phase 1.

## Goal

Bring data into a PPE environment: download archives from their source into the
env's shelf pantry, then unpack them to the live data dir. These are thin
wrappers over wrangler's `--data-download` / `--data-unpack` flags and share the
same shelf→live data dir pipeline.

## Scope

**In:**
- `ppe data download NAME [--select REGEX] [--no-validate]`
  - Invokes wrangler download for `NAME`'s declared archives into the shelf
    (`${pantry}/shelves/<NAME>/archives/<data>*`).
  - `--select REGEX`: pick specific archives (from `--data-select`).
  - `--no-validate`: skip post-download checksum/manifest validation.
- `ppe data unpack NAME [--no-unpack-existing] [--symlinks|--no-symlinks]`
  - Unpacks downloaded archives to live data dirs
    (`NBW_ROOT/data/<NAME>/` or the spec's configured data dir).
  - `--symlinks|--no-symlinks`: toggle symlink-based unpacking.
  - `--no-unpack-existing`: skip archives already unpacked.
- Download/unpack report warnings on stderr for failed operations but do not
  revert prior successful steps.

**Out:**
- Refdata spec editing (`refdata_dependencies.yaml`) — handled by wrangler's
  curation; not a `ppe` command.
- `pack` / `clean` — deferred to Phase 9c.

## Design notes

- **Direct delegation.** These are thin wrappers over `cli.py`'s
  `--data-download` / `--data-unpack` flags (and `data_manager.py`). Don't
  reimplement download/symlink logic.
- **Shared helpers.** Reuse the spec loader + shelf path helpers from Phase 9a.
  `--select`/`--symlinks`/`--no-validate`/`--no-unpack-existing` flags are
  forwarded verbatim to wrangler.

## Prerequisites / dependencies

- Phase 1 (pantry/shelf paths, `NBW_ROOT`).
- Phase 9a (`data` group, spec + shelf helpers).
- `nb_wrangler/data_manager.py` (the data subsystem).

## Files to create / modify

- **Modify** `nb_wrangler/ppe/cli.py`:
  - Extend `_add_data_subcommands` so `download`/`unpack` parse `name` + flags.
  - Extend `_dispatch_data` routing `download` → `_cmd_data_download`,
    `unpack` → `_cmd_data_unpack`.
  - Add `_cmd_data_download`, `_cmd_data_unpack` (forward to `data_manager`).
- **Extend** `tests/ppe/test_data.py` (download/unpack subset):
  - Patch `data_manager.download_data` / `unpack_data` (or the cli.py flag
    routines) with fakes returning bool.
  - Tests: download with/without `--select`; `--no-validate` forwarded;
    unpack default symlinks; `--no-symlinks` forwarded; `--no-unpack-existing`
    forwarded.

## Tasks

- [x] `data download`: invoke wrangler download with `--select` / `--no-validate`
      forwarded.
- [x] `data unpack`: invoke wrangler unpack with `--symlinks`/`--no-symlinks` /
      `--no-unpack-existing` forwarded.
- [x] Tests: each subcommand invokes the right wrangler routine with the right
      flags (fakes).

## Testing / validation

```sh
make unit-test TESTS=tests/ppe/test_data.py
make lint/flake8 && make lint/black && make lint/mypy
ppe data download demo --select 'roman_.*'
ppe data unpack demo
```

## Acceptance criteria

- `ppe data download demo` dispatches to wrangler's data download routine.
- `--select REGEX` filters downloads to matching archives.
- `ppe data unpack demo` dispatches to wrangler's data unpack routine.
- `--symlinks|--no-symlinks` / `--no-unpack-existing` / `--no-validate` are
  forwarded to the matching wrangler routine.