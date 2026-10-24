# `hubenv save` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/env_save.py`, `nb_wrangler/hubenv/_common.py`,
> `nb_wrangler/pantry.py`, and `nb_wrangler/environment.py`.
>
> The `--save` path of `hubenv create` (Phase 1) delegates to the same
> `_do_save` helper, so it is covered here.
>
> Verified against `tests/hubenv/test_save.py` and `test_e2e.py` (Phase 2).

---

## 1. Purpose

`hubenv save` packs a **live** environment into a pantry *can* (a tarball) and
records a save hash so that a later `restore` can be idempotent. It is the
single code path that makes an environment *restorable*: until a can exists,
`restore`/`ensure` refuse and `status`/`ls` show the env as `spec-only`.

The can is `<target pantry>/shelves/<name>/archives/env-<name>.tar`
(`NbwShelf.env_archive_path`), built with `tar -amcf` from the live env dir
`$NBW_MM/envs/<name>`. The command is *not* itself idempotent-skip: re-saving
over an existing can requires `--force`.

---

## 2. Command synopsis

```
hubenv save NAME [--pantry PATH] [--dry-run] [--force]
```

---

## 3. Arguments

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Name of the live environment to archive (mamba env name = shelf name = kernel name). |
| `--pantry` | optional, `None` | Target pantry directory. When set, `PantryStore(paths=[Path(value)])` is used and the forced pantry must itself be writable (no fallback). When omitted, the first writable pantry in the `NBW_PANTRY` chain is used. |
| `--dry-run` | optional, `False` | Print the planned `shelf:` / `can:` / `live env:` paths; return 0 without writing. |
| `--force` | optional, `False` | Overwrite an existing can. |
| global flags | — | `-q/--quiet`, `--verbose`, `--debug`, `--color`, `--log-times`, `--reset-log` (see [`hubenv-common.md`](hubenv-common.md) §3). |

---

## 4. Execution paths

### 4.1 Default (write) path

1. `target = PantryStore().target_pantry(pantry)`:
   - `--pantry` set → path must be writable (`p.exists() and os.access(p, W_OK)`),
     else `None`;
   - otherwise → first writable pantry, or `None`.
   - `None` → `print_no_writable_pantry(pantry)`:
     - forced → stderr `"Pantry '…' is read-only or does not exist."`;
     - chain → stderr `"No writable pantry found. Set NBW_PANTRY to a writable path."`
     → **return 1**.
2. `em = EnvironmentManager()`; `env_path = em.env_live_path(name)`.
   Missing → stderr `"Live environment 'NAME' not found at <env_path>"` → **return 1**.
3. `shelf = NbwShelf(target/"shelves"/name, pantry_path=target)`;
   `can_path = shelf.env_archive_path(name, ".tar")`.
4. Existing can (`can_path.exists()`) without `--force` →
   stderr `"Archive already exists at <can_path>. Use --force to overwrite."`
   → **return 1**.
5. `shelf.pack_environment(name, name, ".tar")` →
   `tar -amcf <can> <live env dir>` (timeout `ARCHIVE_TIMEOUT`, `MAMBA_ROOT_PREFIX` pinned to `$NBW_MM`):
   - success → INFO log `"Packed <live env dir> into <can>"`;
   - failure → ERROR log `"Failed to pack <live env dir> into <can>:"` + subprocess output → **return 1** (no save hash written).
6. `persist_save_hash(shelf, can_path)`: sha256 of the can →
   `<shelf>/archives/last-save.sha256` (newline-terminated).
7. stdout `"Saved environment 'NAME' to <can_path>"` → **return 0**.

### 4.2 `--dry-run`

Steps 1–3 unchanged (writability and live-env checks still run). Then:

```
shelf: <target pantry>/shelves/<name>
can: <target pantry>/shelves/<name>/archives/env-<name>.tar
live env: <live env dir>
```

to stdout and **return 0**. No can, no save hash, no filesystem writes.

### 4.3 Shared use by `create --save`

`cmd_env_create` (with `--save`) calls `_do_save(PantryStore(), name, pantry,
force=False)` after a successful build and non-ephemeral persist. On success it
logs INFO `"Environment 'NAME' is archived and restorable."` and returns the
save's exit code. Note `force=False` is hard-coded: `create --save` will **not**
overwrite a pre-existing can (it exits 1 in that case, after the env was already
created).

---

## 5. Exit codes

| Condition | Exit code |
|---|---|
| `--dry-run` success | `0` |
| Pack success + save hash written | `0` |
| No writable pantry (chain or forced `--pantry`) | `1` |
| Live environment not found | `1` |
| Can already exists, `--force` not passed | `1` |
| Pack (tar) failure | `1` |
| Argparse usage error / interrupt | `2` / `130` |

---

## 6. Side-effect summary by flag combination

| | `--dry-run` | default | `--force` |
|---|---|---|---|
| `env-<name>.tar` can | ❌ | written (refused if present) | written (always overwritten) |
| `archives/last-save.sha256` | ❌ | written/rewritten | rewritten |
| live env | untouched | untouched | untouched |
| shelf spec / kernel | untouched | untouched | untouched |

---

## 7. Edge cases

- **Existing can, no `--force`** → exit 1; the can is *not* overwritten and
  the save hash is *not* rewritten.
- **No writable pantry** → exit 1; the message names the forced path when
  `--pantry` was given.
- **Live env missing** → exit 1 (checked *before* the can-existence check).
- **Pack failure** → exit 1; `last-save.sha256` is not updated (the command
  returns before `persist_save_hash`), so the env is still in its previous
  state (archived at the old can, or not archived at all).
- **Shadowed names**: `save` writes to a single target pantry only; it does
  not enumerate shadowing and does not touch other pantries.
- **No hash-based skip**: unlike `restore`, `save` never compares hashes —
  it only refuses without `--force`.
- `--dry-run` still runs the live-env existence check, so it exits 1 for a
  missing env.

---

## 8. Pantry interaction

- **Write**: exactly one target pantry — the forced `--pantry` (validated) or
  the first writable in the chain. Never writes to multiple pantries, never
  falls back from a failed forced path.
- **Read**: live env path only (`NBW_MM/envs/<name>`); the shelf dir is created
  implicitly by `pack_environment` (archive root mkdir) — a fresh `save` on a
  writable pantry therefore *creates* the shelf directory if absent (spec file
  is not created by save).
- **Writability**: per-pantry `os.access(W_OK)`; a forced read-only/non-existent
  path fails immediately (no fallback).
- `--pantry` here is *write-target* semantics (distinct from `restore`'s
  *source* semantics, which refuses multi-match).

---

## 9. Output (stdout) examples

### 9.1 `hubenv save demo --dry-run`

```
shelf: /home/u/.nbw-pantry/shelves/demo
can: /home/u/.nbw-pantry/shelves/demo/archives/env-demo.tar
live env: /home/u/.nbw-live/mm/envs/demo
```

### 9.2 `hubenv save demo` (success)

```
Saved environment 'demo' to /home/u/.nbw-pantry/shelves/demo/archives/env-demo.tar
```
(stderr: INFO `"Packed /home/u/.nbw-live/mm/envs/demo into .../env-demo.tar"`
on pack success.)

### 9.3 Failures (stderr)

```
Pantry '/opt/ro/pantry' is read-only or does not exist.
No writable pantry found. Set NBW_PANTRY to a writable path.
Live environment 'demo' not found at /home/u/.nbw-live/mm/envs/demo
Archive already exists at /home/u/.nbw-pantry/shelves/demo/archives/env-demo.tar. Use --force to overwrite.
```

---

## 10. What is NOT done (out of scope for the current implementation)

- No kernel registration, no restore, no data-archive management
  (those are `register`, `restore`, `hubenv data *`).
- No hash-based idempotent skip (that is `restore`'s job, §9 of
  [`hubenv-common.md`](hubenv-common.md)).
- No curation / spec re-lock — a fresh save of an *unchanged* env is cheap;
  keeping the *spec* current is `relock`'s job.
- No nbw spec curation, notebook discovery, or image build (that is `nbw`).

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§4.7 idempotency, §4.3 output
  discipline, §4.4 exit codes, §5.2 save stub).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§5 layout, §6
  store methods, §7 pantry rules, §9 idempotency).
- [`hubenv-env-restore.md`](hubenv-env-restore.md) — consumer of the save hash;
  [`hubenv-env-create.md`](hubenv-env-create.md) (the `--save` path);
  [`hubenv-env-rm.md`](hubenv-env-rm.md) (deletes the can with the shelf).
