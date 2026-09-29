# Phase 9c — `hubenv data pack` / `hubenv data clean` (retire data)

> Deliverable: `hubenv data pack NAME` and `hubenv data clean NAME
> [archived|unpacked|both]`. Depends on Phase 9b (`data` group + shelf/spec
> helpers) and Phase 1.

## Goal

Retire data from a PPE environment: pack live data dirs back into archive
files in the shelf, and/or clean (delete) archives and/or unpacked files. These
are thin wrappers over wrangler's `--data-pack` / `--data-delete` flags.

## Scope

**In:**
- `hubenv data pack NAME`
  - Packs live data dirs (`NBW_ROOT/data/<NAME>/`) back into archive files in
    the shelf (`${pantry}/shelves/<NAME>/archives/<data>*`).
- `hubenv data clean NAME [archived|unpacked|both]`
  - `archived`: delete data archives in the shelf.
  - `unpacked`: delete unpacked files in the live data dir.
  - `both`: delete both (default).
  - No matching mode → error to stderr, exit 1.

**Out:**
- Refdata spec editing (`refdata_dependencies.yaml`) — handled by wrangler's
  curation; not a `hubenv` command.
- `download` / `unpack` — deferred to Phase 9b.

## Design notes

- **Direct delegation.** Thin wrappers over `cli.py`'s
  `--data-pack` / `--data-delete` flags (and `data_manager.py`).
- **Reuse helpers** from Phase 9a/9b (spec loader + shelf paths).
- **Destructive op:** `clean` is irreversible; forward the mode string verbatim
  to wrangler's delete routine.

## Prerequisites / dependencies

- Phase 1 (pantry/shelf paths, `NBW_ROOT`).
- Phase 9a (`data` group, spec + shelf helpers).
- Phase 9b (shared `data` subcommand scaffolding).
- `nb_wrangler/data_manager.py` (the data subsystem).

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py`:
  - Extend `_add_data_subcommands` so `pack`/`clean` parse `name` + mode.
  - Extend `_dispatch_data` routing `pack` → `_cmd_data_pack`,
    `clean` → `_cmd_data_clean`.
  - Add `_cmd_data_pack`, `_cmd_data_clean` (forward to `data_manager`).
- **Extend** `tests/hubenv/test_data.py` (pack/clean subset):
  - Patch `data_manager.pack_data` / `delete_data` (or the cli.py routines)
    with fakes returning bool.
  - Tests: pack forwards to wrangler pack; clean `archived`/`unpacked`/`both`
    forwarded; invalid mode errors, exit 1.

## Tasks

- [ ] `data pack`: invoke wrangler pack routine.
- [ ] `data clean`: invoke wrangler delete with `archived|unpacked|both` mode.
- [ ] Tests: each subcommand invokes the right wrangler routine with the right
      mode (fakes).

## Testing / validation

```sh
make unit-test TESTS=tests/hubenv/test_data.py
make lint/flake8 && make lint/black && make lint/mypy
hubenv data pack demo
hubenv data clean demo archived
```

## Acceptance criteria

- `hubenv data pack demo` dispatches to wrangler's data pack routine.
- `hubenv data clean demo archived` (and `unpacked`/`both`) dispatches to
  wrangler's data delete routine with the right mode.
- No spec or kernel is modified by `pack`/`clean`.