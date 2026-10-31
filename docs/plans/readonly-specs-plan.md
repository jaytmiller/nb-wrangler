# Plan: Keep reinstall workflows from modifying the wrangler spec

Status: **implemented and ratified** (2026-10-31). Q1 `--inject-spi` behavior change approved 2026-10-30; Q2 "explicit per-site refresh" concern resolved by decision 8 (single designated update path). Tests green (296 passed).

## Goal

`nbw --reinstall` and `nbw --data-reinstall` — and every step that does not
force or strongly imply a spec update — must leave the wrangler spec
unchanged **in any form**: no `date_updated` change, no `spec_sha256` change,
no other content change, whether in the in-memory `SpecManager` or in the
files written during the run.

Explicitly requested spec-updating steps keep their current behavior:
`--spec-update-hash`, `--spec-reset` (curation/data resets),
`--spec-disable-dev-overrides`, curation `_save_final_spec`, and
`--data-collect` / `--data-update`.

## Non-goal

No change to the spec file format, no change to workflow step ordering, no
new CLI flags.

## Findings (verified against the code)

### `--reinstall`  (`wrangler.py:387-407`)

Steps: `_validate_spec` → `_spec_add` → `_initialize_environment` →
`_install_packages`.

| Step | Spec effect |
|---|---|
| `_validate_spec` (`wrangler.py:981-984`) | `validate_sha256()` calls `add_sha256()` (`spec_manager.py:698-712`, `693-696`) which **writes** `system["spec_sha256"]` in memory. Value-identical when the hash is valid, but the mutation happens regardless; value changes when the stored hash was bad. |
| `_spec_add` (`wrangler.py:685-688` → `pantry.py:174-179`) | **Byte-identical copy** of the original file into the pantry shelf. ✅ No modification. |
| `_initialize_environment` (`wrangler.py:890-917`, fresh envs only) and `_install_packages` (`wrangler.py:919-935`, **always**) → `_copy_spec_to_env` (`wrangler.py:945-952`) → `save_spec_as` (`spec_manager.py:591-620`) | `refresh_date_updated()` (`spec_manager.py:676-681`) **unconditionally** rewrites in-memory `date_updated` to now. Without `--spec-ignore-hash`: a **new `spec_sha256`** computed over the date-changed content. With `--spec-ignore-hash`: `spec_sha256` is **popped** from the in-memory spec. Result: the copy written to `NBW_MM/envs/<env>/<spec-name>` differs from the source in `date_updated` and/or hash. |
| Source file | **Not rewritten** by this workflow in the normal case (all destinations differ). **But** the poisoned in-memory state means any later save to the source in a combined invocation (e.g. `--reinstall --data-update`) would persist the mutated date/hash. |

**Conclusion: `--reinstall` DOES modify the spec in form** (in-memory
`date_updated` + `spec_sha256` on every run; date/hash in the env-dir copy).

### `--data-reinstall`  (`wrangler.py:409-420`)

Steps: `_validate_spec` → `_spec_add` → `data_wrangler.download` →
`validate` → `unpack`.

- `download` / `validate` / `unpack` (`data_wrangler.py:136-236`) perform
  **zero spec writes/mutations**; exports go to pantry shelf files
  (`nbw-spec-exports.sh`, `nbw-pantry-exports.sh`), not the spec.
- `_spec_add` → pane shelf copy is byte-identical.
- `_register_environment` (`wrangler_mixin.py:116-133`) only registers the
  Jupyter kernel.
- Only latent mutation: the same `validate_sha256` → `add_sha256` in-memory
  re-assignment (a no-op in value when the hash is valid/absent).

**Conclusion: `--data-reinstall` is already spec-safe on disk**; only the
latent in-memory mutation remains.

### `--inject-spi` (tail of `inject`, `injector.py:112-177`)

- `SpiInjector.inject()` ends by archiving the spec as
  `environments/nbw-wrangler-spec.yaml`. At HEAD that went through the old
  conflated `save_spec_as`, which refreshed `date_updated` and recomputed
  `spec_sha256` internally — so the archived spec was re-stamped at inject
  time: its `date_updated` meant "when injected" and its `spec_sha256` was a
  fresh hash that matches no user-curated spec file. The tail's
  `add_sha256=True` dates to commit `2e15cf6`, when the internal refresh was
  baked into saving itself — an artifact of the old conflated save, not an
  intentional "lock at inject time" decision.
- `SpiInjector.set_wrangler_spec()` (`injector.py:106-110`) is **dead and
  broken**: zero callers, and it passes a **file** path to
  `save_spec(dir)` — directory semantics (would write
  `nbw-wrangler-spec.yaml/<source name>`). A pre-split-era leftover that
  duplicates the tail's intent.
- `core_name` (`injector.py:70-80`) embeds `spec_id` = stored
  `spec_sha256[:6]`, and `spi_injection_branch_name` is computed **after**
  `inject()` (`wrangler.py:356`, `_spi_cm_and_optional_build`) — so auto
  branch/tag names embed whatever hash `inject()` leaves behind; today that
  is the re-stamped one.
- The generic-name spec is purely a traceability artifact:
  `docs/inject-spi.md:12` (baked into the image at
  `/opt/environments/nbw-wrangler-spec.yaml`), `registry.py` `cat_spec`
  (display-only), and no consumer verifies the archived hash.
- `ingest_dir`/`archive_dir`/`ingest_name` (`injector.py:49-50, 88-92`) are
  defined but unused — no code writes into `nbw-spec-archive` — so the
  `environments/` spec is the **only** second spec file the tail affects.
- Sample-spec note: `sample-specs/tike-wrangler-k1.yaml`'s stored hash
  predates the current hash computation (invalid under the old *and* new
  algorithm — not a regression); tests needing a validating hash must
  re-hash a tmp copy first.

### Verified clean

- `data_manager.py` / `RefdataValidator`: no `sha256`, `date_updated`, or
  `save_spec` references.
- `utils.uri_to_local_path` (`utils.py:169+`): plain downloader; no spec logic.
- Existing test `test_save_spec_creates_output`
  (`tests/test_spec_manager_extended.py:94-111`) asserts file existence only
  → safe to change save semantics.

## Conflicts identified

1. **Copy vs. update conflated in one code path** — `save_spec_as`
   (`spec_manager.py:591-620`) serves both "copy elsewhere" (env dir, SPI
   generic spec write) and "update source" (resets), with one always-mutating
   path: `refresh_date_updated()` always, then recompute *or strip* the hash.
2. **Inconsistent copy semantics within a single `--reinstall` run** — the
   pantry shelf copy is byte-identical, the env-dir copy has refreshed
   `date_updated` and a different (or missing) hash.
3. **`--spec-ignore-hash` semantics incomplete** — help says hashes are "not
   added or verified upon re-installation" (`cli.py:599-604`), but the save
   path actively *removes* `spec_sha256` (`spec_manager.py:602-606`).
4. **Intent documented but unenforced** — `_initial_spec_sha256` is stashed
   in `load_and_validate` "to ensure readonly workflows do not change it"
   (`spec_manager.py:541-545`), yet nothing reads it.
5. **`validate_sha256` is nominally a read but writes in-memory state** via
   `add_sha256()` (`spec_manager.py:698-712`).
6. **`set_wrangler_spec` is dead and broken** — zero callers, and it passes
   a file path to directory-semantics `save_spec`; meanwhile `inject`'s tail
   inlines the same intent with the old refresh+rehash semantics.

## Decisions (approved)

| # | Question | Decision |
|---|---|---|
| 1 | Env-dir copy content | **Faithful copy** — written env copy preserves the source's `date_updated` and `spec_sha256` exactly, consistent with the byte-identical pantry shelf copy. |
| 2 | Fix structure | **Split save semantics** — `save_spec`/`save_spec_as` become non-mutating writes of the current state. Originally scoped so `revise_and_save` would be the designated update path with **no new public API**; decision 8 supersedes the scope (new `update_and_save` method approved 2026-10-31) while keeping the split semantics. |
| 3 | `--spec-ignore-hash` + save | **Preserve** the existing `spec_sha256` in the written file (no longer stripped). |
| 4 | `validate_sha256` | **Non-mutating** — compare against a computed hash without writing `spec_sha256` into in-memory state. |
| 5 | Content-changing updates | Keep today's visible behavior: `date_updated` refresh + hash handling on `--spec-update-hash`, resets, `--spec-disable-dev-overrides`, curation `_save_final_spec`, `--data-collect`/`--data-update`. |
| 6 | `inject` tail / `set_wrangler_spec` | **Consolidate into one faithful copy**: fix `set_wrangler_spec()` to write the current spec as `nbw-wrangler-spec.yaml` (name **unchanged**); a stored `spec_sha256` is preserved, a missing one is set (identity backfill so `core_name`/auto branch names keep resolving for hash-less specs). `inject()` ends by calling it and now **fails** if the archive save fails. `--inject-spi` is no longer an "exception" step — saves are copies everywhere. |
| 7 | `refresh_date_updated` placement | ~~Explicit at the designated update call sites~~ — **superseded by decision 8** after user review flagged per-site explicit refresh as a maintenance liability: the whole update protocol (refresh + hash policy) ended up conventioned across 5 sites, upheld only by workflow-ordering luck (e.g. `_save_final_spec` relied on a preceding `revise_and_save` having popped/recomputed the hash; nothing would stop a future step from saving a stale hash). |
| 8 | Single update protocol entry point | **`update_and_save(output, add_sha256=False)`** — one new public method (approved 2026-10-31; option 1: a named method beats reusing `revise_and_save`). Owns the entire protocol: `refresh_date_updated()`, then save via `save_spec_as` with a **fresh** `spec_sha256` if `add_sha256`, or the hash **popped** otherwise (an updated spec never keeps the old hash; same visible outcome as the old pop-on-save). All five update sites — `revise_and_save`, `_reset_and_save`, `spec_disable_dev_overrides`, `_save_final_spec`, `_update_spec_sha256` — delegate to it. A stale hash in a saved update becomes unrepresentable by construction; visible outcomes on all reachable flows are unchanged. |

## Design

Split "write" from "update" inside `SpecManager`:

| API | New meaning | `date_updated` | `spec_sha256` |
|---|---|---|---|
| `save_spec_as(path, add_sha256=False)` / `save_spec(dir, ...)` | Write out the **current** spec state; pure copy semantics | untouched | untouched; if `add_sha256=True`, compute and set (explicit hash-update opt-in) |
| `update_and_save(output, add_sha256=False)` | **The** designated update path — owns the whole update protocol (decision 8) | refreshed | popped when `add_sha256=False` (never stale); recomputed when `add_sha256=True` |
| `revise_and_save(dir, ...)` | Thin wrapper: adds `out` data, then delegates to `update_and_save` | refreshed (inherited) | as `update_and_save` (prior update-path behavior retained) |
| `validate_sha256()` | Validate integrity | untouched | untouched (computed hash used for comparison only) |
| `refresh_date_updated()`, `add_sha256()` | Unchanged; now called only from within the update protocol | — | — |

Workflow results after the change:

| Workflow | Source spec file | In-memory state | Env-dir copy | Pantry shelf copy | SPI archived spec |
|---|---|---|---|---|---|
| `--reinstall` | **unchanged** (no write; state clean) | unchanged | faithful (`date_updated` + `spec_sha256` match source) | byte-identical (no change) | not written |
| `--data-reinstall` | unchanged (no write) | unchanged | not written | byte-identical (no change) | not written |
| `--inject-spi` | unchanged (no source write) | unchanged; a **missing** `spec_sha256` is set at archive time (net outcome same as today) | not written | not written | **faithful** copy of the curated spec (stored date + hash) |
| curation / data curation | written by designated update steps (refresh + hash) as today | n/a | faithful to in-memory state (unchanged) | written by designated update steps as today | n/a |

## Change list (per file)

All edits are 1–2 lines each; every affected method stays within the 5–20 SLOC
target.

### `nb_wrangler/spec_manager.py`

1. **`save_spec_as` (591-620)** — core of the fix:
   - Remove the `self.refresh_date_updated()` line (598).
   - Remove the `else` branch (602-606) — i.e. with `add_sha256=False`, do
     **nothing** to `spec_sha256` (delete the `pop` + "Removing potentially
     outdated sum" log).
   - Update the docstring: "Save the current YAML spec to a file without
     modifying it. Optionally computes and sets `spec_sha256`."
2. **New `update_and_save(output, add_sha256=False)`** — the single
   designated update path (decision 8): `refresh_date_updated()`, then
   `self.system.pop("spec_sha256", None)` when `add_sha256=False` (an
   updated spec must never keep the old hash; same visible outcome as the
   old pop-on-save), then `save_spec_as(output, add_sha256=...)`. A stale
   hash in a saved update is now unrepresentable by construction.
3. **`revise_and_save` (622-643)** — becomes a thin wrapper over
   `update_and_save`: apply `**additional_outputs` via `set_output_data`,
   then `update_and_save(self.output_spec(output_dir), add_sha256)`. The
   explicit refresh + pop it previously inlined now live in
   `update_and_save`; the caller-facing signature (dir input, `add_sha256`,
   `**outputs`) is unchanged.
4. **`_reset_and_save` (645-664)** — tail becomes
   `return self.update_and_save(self._source_file)`: the inlined refresh
   and the `save_spec_as` save call are subsumed by the helper; the
   content-reset `pop("spec_sha256")` stays (the helper's pop is a no-op
   there).
5. **`spec_disable_dev_overrides` (674-682)** — tail becomes
   `return self.update_and_save(self._source_file, add_sha256=True)`
   (refresh + rehash now in the helper; visible outcome unchanged).
6. **`validate_sha256` (698-712)** — replace
   `actual_hash = self.add_sha256()` (704) with
   `actual_hash = self._compute_sha256()`. New helper **`_compute_sha256`** serializes a
   `to_dict()` deep copy with `spec_sha256` blanked (plus the inline mamba
   spec, mirroring `to_string()`) and hashes it: exactly the hash state
   `add_sha256` produces, without writing in-memory state. **`add_sha256`** now
   delegates to `_compute_sha256` (single source of the hashing algorithm,
   behavior-identical) so validation stays non-mutating.

`refresh_date_updated`, `save_spec`, `load_and_validate`,
`load_spec` — unchanged.

### `nb_wrangler/wrangler.py`

7. **`_update_spec_sha256` (968-972)** — the inlined refresh +
   `save_spec(..., add_sha256=True)` becomes one
   `spec_manager.update_and_save(spec_manager.output_spec(Path(
   config.spec_file).parent), add_sha256=True)`; visible outcome unchanged.
8. **``_save_final_spec` (953-966)** — source write becomes
   `update_and_save(output_spec(config.spec_file.parent),
   add_sha256=not spec_ignore_hash)` (refresh + hash policy now live in the
   helper); the pantry-shelf write becomes a plain `save_spec_as(shelf)` — a
   faithful snapshot of the same already-resolved state (at HEAD the shelf
   save internally refreshed the date and rehashed a second time, so shelf
   and source could differ by a timestamp; an artifact of the old conflated
   save — now shelf and source always agree). The shelf write also only runs
   if the source write succeeded.
9. **`_copy_spec_to_env` (945-951)** — simplify the tail save to plain
   `save_spec(env_live_path(...))`, dropping
   `add_sha256=not self.config.spec_ignore_hash`. Output is value-identical
   in every reachable state (on the validated-hash path the recompute equals
   the validated stored hash), but this removes the last mutating spec-API
   call (`add_sha256()` in-memory write) from the reinstall path —
   `--reinstall` now issues **zero** mutating spec calls.

No other `wrangler.py` change: `_spec_add` and the
reinstall/data-reinstall workflow lists stay as-is and automatically become
non-mutating by virtue of changes 1–5.

### `nb_wrangler/injector.py`

10. **`set_wrangler_spec` (106-110)** — fix the dead/broken method into the
   designated SPI archive step: `save_spec_as(self.environments_path /
   "nbw-wrangler-spec.yaml", add_sha256=self.spec_manager.sha256 is None)` —
   a faithful copy of the current spec (name **unchanged**); a stored
   `spec_sha256` is preserved, a missing one is set so the archived spec has
   an identity (keeps `core_name`/branch naming working for hash-less specs,
   matching today's net outcome).
11. **`inject` (170-177)** — replace the trailing
    `refresh_date_updated()` + `save_spec_as(..., add_sha256=True)` with
    `if not self.set_wrangler_spec(): return False` — the tail delegates to
    the fixed method, and `inject()` no longer reports success when the
    archive save fails (at HEAD the failure was swallowed).

### No changes needed

- `nb_wrangler/pantry.py` — `set_wrangler_spec` is already a byte-for-byte
  copy.
- `nb_wrangler/data_wrangler.py` — `download`/`validate`/`unpack` already
  spec-clean; `collect`/`update` flow through `revise_and_save` and keep
  today's update semantics.
- `nb_wrangler/config.py`, `cli.py`, `wrangler_mixin.py`, `environment.py` —
  no changes.

## Behavior-impact notes (to call out in the changelog)

- `save_spec_as(path)` / `save_spec(dir)` no longer refresh
  `date_updated` nor strip `spec_sha256` — this is the core of the requested
  behavior change and is a **public-API behavior change** (approved via the
  decision record above, per AGENTS.md "ask before changing public APIs").
- `--spec-ignore-hash` runs: env-dir and SPI generic spec copies now **retain**
  the original hash instead of stripping it (matches the CLI help: "not added
  or verified").
- `--spec-update-hash`, resets, `--spec-disable-dev-overrides`, curation and
  data-curation source writes: **unchanged visible outcome** (date refresh +
  hash handling as today) — now guaranteed by construction (decision 8):
  every update save routes through `update_and_save`, which either stamps a
  fresh hash or pops the stale one, so a saved update can no longer carry an
  outdated `spec_sha256`.
- Curation pantry-shelf write: now a **faithful snapshot of the same updated
  state** as the source file (at HEAD the shelf save internally refreshed the
  date and re-hashed a second time, so shelf and source could differ by a
  timestamp — an artifact of the old conflated save).
- Public API: **one new method**, `SpecManager.update_and_save(output,
  add_sha256=False)` (approved 2026-10-31, per AGENTS.md);
  `refresh_date_updated()` stays public and is now called only from
  `update_and_save`.
- `--reinstall` no longer leaves poisoned in-memory state, so combined
  invocations (e.g. `--reinstall --data-update`) no longer persist a mutated
  `date_updated`/`spec_sha256` to the source.
- `--reinstall` env-dir copy: becomes a **faithful copy** — preserves the
  source's `date_updated` and the validated `spec_sha256` (decision 1)
  instead of a refreshed date + fresh hash from the old save path.
- `--inject-spi`: the archived SPI spec `environments/nbw-wrangler-spec.yaml`
  (in the SPI repo and baked into the image at
  `/opt/environments/nbw-wrangler-spec.yaml`) now carries the **curated**
  `date_updated` and `spec_sha256` instead of an inject-time refresh +
  rehash. Auto branch/tag names (`nbw-<time>-<image>-<spec_id>`, `spi-...`)
  now embed the **curated** hash prefix — directly traceable to the spec
  file that was injected. **Corner case (flagged for vetoes)**: a spec with
  **no** stored hash is given one at archive time (net outcome same as
  today) — the backfill guard is what prevents `core_name`'s `"-".join([...
  , spec_id])` from hitting `None` on `--inject-spi` build steps without
  `--spi-branch`.
- `--inject-spi` now fails (returns `False`, stops the workflow) if the spec
  archive save fails; at HEAD the injection reported success.

## Tests (focused, per AGENTS.md) — implemented in `tests/test_readonly_specs.py`

New test file `tests/test_readonly_specs.py` (12 tests), with its own
`_make_valid_spec_dict()` helper and the setup pattern from
`tests/test_readonly_pantry.py`:

1. `test_save_spec_preserves_date_and_hash` — spec with a valid
   `spec_sha256` → `save_spec(out_dir)` → in-memory `date_updated` and
   `spec_sha256` unchanged; written file's `date_updated`/`spec_sha256` equal
   the source's.
2. `test_save_spec_ignore_hash_preserves_hash` — `save_spec(out_dir,
   add_sha256=False)` → written file retains the original hash (no longer
   stripped).
3. `test_revise_and_save_refreshes_date_and_hash` — `revise_and_save(out_dir,
   add_sha256=True, some_key=value)` → `date_updated` refreshed, stored hash
   recomputes to the stored value, `out` key present.
4. `test_validate_sha256_non_mutating` — valid hash → `validate_sha256()` is
   `True`, in-memory state byte-identical before/after (`to_dict()`
   equality); invalid hash → `False` with no new hash written.
5. `test_reset_spec_removes_hash_and_refreshes_date` — `reset_spec()` →
   written source has refreshed `date_updated` and **no** `spec_sha256`.
6. Wrangler-level: after simulating the `--reinstall` spec-touched path
   (`_validate_spec` + `_spec_add` + `_copy_spec_to_env` with a patched or
   real `env_manager`, following the setup pattern in
   `tests/test_readonly_pantry.py`), assert the env-dir spec copy is faithful
   to the source (`date_updated`, `spec_sha256`) and the source file bytes
   are unchanged.
7. Existing `test_save_spec_creates_output` and `tests/test_readonly_pantry.py`
   still pass unmodified.
8. `test_reinstall_validated_hash_keeps_spec_untouched` — `--reinstall`
   **without** `--spec-ignore-hash` on a spec whose stored hash validates:
   `_validate_spec` + `_spec_add` + `_copy_spec_to_env` leave the in-memory
   state and the source file byte-identical, and the env-dir `system`
   section equals the source's. The sample spec's stored hash predates the
   current hash computation, so the test re-hashes a tmp copy first
   (`add_sha256()` + `save_spec_as()`).
9. `TestSetWranglerSpecIsFaithfulCopy` — `SpiInjector.set_wrangler_spec`
   with a real `SpecManager` + a dummy repo manager (pattern from
   `tests/test_assets_injection.py`): (a) stored hash → archived
   `nbw-wrangler-spec.yaml` carries the stored hash + `date_updated` and the
   in-memory state is unchanged; (b) no stored hash → the archived spec is
   given a hash that validates against its own stored content.
10. `TestUpdateAndSaveProtocol::test_drops_stale_hash_when_not_rehashing`
    — a spec whose stored `spec_sha256` validates; content is then mutated
    (the stored hash is now stale); `update_and_save(out,
    add_sha256=False)` → written file has a refreshed `date_updated`, **no**
    `spec_sha256`, and the in-memory state also dropped the stale hash.
11. `TestUpdateAndSaveProtocol::test_stamps_fresh_valid_hash_when_rehashing`
    — content mutated, then `update_and_save(out, add_sha256=True)` →
    `validate_sha256()` is `True` and the written file's `spec_sha256`
    recomputes to its stored value (a fresh hash over the refreshed state).
12. Full suite: all pre-existing unit tests still pass unmodified
    (296 total).

## Verification (run 2026-10-30)

```bash
make unit-test     # 294 passed
make lint/black    # clean (67 files unchanged)
make lint/flake8   # 0 issues
make lint/radon    # clean (all A/B grades)
make lint/mypy     # no issues (23 source files)
```

`make test-functional` **not run**: no Docker/micromamba in this sandbox.

## Verification (re-run 2026-10-31, after decision 8)

```bash
make unit-test     # 296 passed
make lint/black    # clean
make lint/flake8   # 0 issues
make lint/radon    # clean (diagnostic; wrangler.py C=1.12 — already C=1.27 at HEAD)
make lint/mypy     # no issues (23 source files)
```

`make test-functional` **not run**: no Docker/micromamba in this sandbox.

Note: the 2026-10-30 "all A/B grades" line was inaccurate — `wrangler.py`
was already at C (1.27) at HEAD; the radon target is diagnostic and passes
either way.

## Optional follow-up (out of scope here)

- Wire `_initial_spec_sha256` (`spec_manager.py:541-545`) into a debug
  assertion / test helper ("readonly workflows did not change it") so the
  stored intent becomes enforceable instead of documented-only.
