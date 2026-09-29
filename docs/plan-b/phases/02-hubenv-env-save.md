# Phase 2 — `hubenv env save`

> Deliverable: `hubenv env save NAME [--pantry PATH] [--dry-run]` packs a live
> environment into a pantry "can" archive. Depends on Phase 1.

## Goal

Archive a live (installed) environment into a pantry shelf so it can be
restored later by `hubenv env restore` (Phase 3) without reinstalling from scratch.

## Scope

**In:**
- `hubenv env save NAME` finds the live env, packs it into a `can` archive inside a
  shelf in the first writable pantry (or `--pantry PATH`), and records a
  save-hash for later idempotency checks.
- `--pantry PATH` forces the target pantry.
- `--dry-run` previews the target shelf/can path and the live env path and
  exits 0 without writing.
- Refuses to write to a read-only pantry with a clear message (uses Phase 1's
  r/o detection).

**Out:**
- `hubenv env restore` (Phase 3), unpacking, kernel registration.

## Design notes

- **Shelf/ can layout** (from `docs/plan-b/plan-b-flow.md`):
  `${pantry}/shelves/${NAME}/spec.yaml`, `archives/<can>` (the env tarball),
  `archives/*repo*.tar.gz`, `archives/*data*.tar.gz`, plus unpacked data dirs.
  `save` creates/ensures `${pantry}/shelves/${NAME}/`.
- **Pack source:** the live env lives under `NBW_ROOT/envs/<NAME>` (where
  wrangler installs envs). Reuse wrangler's pack mechanism — `cli.py`'s
  `--env-pack` maps to `environment.py` pack/tarball logic. Don't reimplement
  tarball creation; call/parallel the same routine.
- **Save-hash:** store a hash (e.g. SHA-256 of the produced can, or a content
  hash of the env) in the shelf metadata so `restore` can detect "live
  env matches an already-restored archive" and skip. Persist in the shelf's
  spec/metadat a small file (e.g. `archives/last-save.<hash>`).
- **Idempotency/safety:** refuse if the live env doesn't exist; refuse to
  overwrite a can unless `--force` (add `--force` here too for safety, even
  though it's not in the MVP summary — it's cheap and prevents data loss).

## Prerequisites / dependencies

- Phase 1 (the `hubenv` scaffold, r/o detection, `NBW_ROOT`/`NBW_PANTRY_DIRS`,
  `nb_wrangler/hubenv/config.py`).
- `nb_wrangler/environment.py` pack/tarball routine.

## Files to create / modify

- **Modify** `nb_wrangler/hubenv/cli.py` — implement the `save` env subcommand
  (replace the Phase 1 stub).
- **Modify** `nb_wrangler/hubenv/config.py` — add `target_pantry(path)` helper that
  resolves/warns on r/o.
- **Create** `tests/hubenv/test_save.py` — fakes for pack; r/o refusal; `--dry-run`.

## Tasks

- [ ] Resolve target pantry (first writable in `NBW_PANTRY_DIRS`, or `--pantry`).
- [ ] Verify the live env exists under `NBW_ROOT/envs/<NAME>`; error clearly if not.
- [ ] Ensure the shelf dir `${pantry}/shelves/<NAME>/` exists.
- [ ] Pack the live env into `${pantry}/shelves/<NAME>/archives/<NAME>.tar[.xz]`
      via wrangler's pack routine (not a hand-rolled tar).
- [ ] Compute + persist save-hash in the shelf.
- [ ] `--dry-run` prints planned paths and exits 0.
- [ ] r/o pantry → clear error + suggestion to use `--pantry`.
- [ ] `--force` to overwrite an existing can (optional but recommended).
- [ ] Tests: dry-run output, r/o refusal, can created, hash persisted (fakes for
      the actual pack).

## Testing / validation

```sh
make unit-test
make lint/flake8 && make lint/black && make lint/mypy
hubenv env save demo --dry-run
hubenv env save demo --pantry /tmp/ro-pantry   # r/o -> error
```

## Acceptance criteria

- `hubenv env save demo` creates a can under the primary pantry's
  `shelves/demo/archives/` and a save-hash.
- `--dry-run` writes nothing and prints the planned paths.
- Saving to an r/o pantry fails with an actionable message.
- `--force` overwrites an existing can instead of failing.