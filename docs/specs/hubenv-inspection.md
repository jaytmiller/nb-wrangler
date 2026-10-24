# `hubenv ls` / `hubenv info` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/env_ls.py`, `nb_wrangler/hubenv/env_info.py`,
> `nb_wrangler/pantry.py` store methods, and
> `nb_wrangler/environment.py`.
>
> Verified against `tests/hubenv/test_ls_info.py`.

---

## 1. Purpose

The inspection pair is the read-only lens on hubenv state:

- **`hubenv ls`** lists live mamba environments and pantry shelves in one
  table (or JSON), marking which are live and which are restorable — i.e.
  which have a packed can.
- **`hubenv info`** shows detailed metadata for a single environment: live
  path, plus every shelf that matches the name (pantry, path, writability,
  save hash, can presence and size).

Both commands are pure readers: nothing on disk is created or modified.
Their job is to be consistent with the canonical **environment state model**
([`hubenv-common.md`](hubenv-common.md) §12 / [`hubenv.md`](hubenv.md) §4.8
area): `has_can()` is the single source of truth for "restorable", and a
shelf directory alone is **not** "archived" (`spec-only`).

---

## 2. Command synopsis

```
hubenv ls [NAME-or-glob…] [--all] [--pantry PATH] [--format table|json]

hubenv info NAME [--pantry PATH] [--format table|json]
```

---

## 3. Arguments

| Argument | Required / Default | Description |
|---|---|---|
| `NAME-or-glob…` (`ls`) | optional, positional (zero or more) | Filter shelves by exact name or glob pattern. Zero patterns → all shelves. |
| `--all` (`ls`) | optional, `False` | Expand duplicate names across pantries; without it the **first** match per name wins (later duplicates are collapsed). |
| `--pantry PATH` (`ls`/`info`) | optional, `None` | Restrict the shelf search to a single pantry directory. Shelf *reads only*; live envs are always shown. |
| `NAME` (`info`) | required, positional | Exact environment name to inspect. |
| `--format` | optional, `table` | `table` or `json` (json emits a single parseable object to stdout). |
| global flags | — | `-q/--quiet`, `--verbose`, `--debug`, `--color`, `--log-times`, `--reset-log` (see [`hubenv-common.md`](hubenv-common.md) §3). |

---

## 4. Execution paths

### 4.1 `hubenv ls`

1. `PantryStore()` — the default `NBW_PANTRY` chain (see §8: `--pantry` is
   applied as a filter to `list_shelves`, not as store scoping).
2. If no positional patterns were given, the search pattern set is `[None]`
   (all shelves); otherwise each pattern is searched independently and results
   extended in argument order.
3. `list_live_envs()` from the live env root (`$NBW_MM/envs/`).
4. `--format json` → one JSON object (see §9.2) → exit 0.
5. Otherwise print the table (see §9.1):
   - shelves in result order; each row: `NAME`, `PANTRY` (absolute pantry
     path), `STATUS` (`r/o` if the pantry is not writable, blank if writable),
     `ARCHIVE` (see 4.2), `LIVE` (`*` if the name also has a live env).
   - Without `--all`, names already printed are skipped (first match wins);
     with `--all`, every matching shelf row is printed.
   - Live envs that appeared on no shelf row get a final row: `PANTRY=<live>`,
     `ARCHIVE=not a shelf`, `LIVE=*`.
6. Always finish with **shadowing warnings** (stderr) when any name has
   shelves in more than one pantry: `'{name}' shadowed across pantries: <p1>, <p2>, …`.
7. Exit **0**. `ls` never errors on an empty result set.

### 4.2 The `ARCHIVE` cell

Per row, `PantryStore.has_can(name)` is consulted (the can, i.e.
`<shelf>/archives/env-<name>.tar`, under the highest-priority matching
shelf):

- can present → the **12-character truncation** of the shelf's save hash
  (the `last-save.sha256` value); if the hash file is missing but a can exists,
  the cell shows the literal `ok`.
- no can → the marker `spec-only`.
- live-only row (not a shelf) → `not a shelf`.

This is exactly the `status` command's `archived` column and the
`live+archived` / `spec-only` state strings — `ls` and `status` must never
disagree.

### 4.3 `hubenv info NAME`

1. `PantryStore()`; `list_shelves(glob_expr=NAME, pantry=<filter>)`;
   `list_live_envs()`.
2. **No shelf AND no live env** named `NAME` → logger warning
   `No shelf or live env named '<name>' found.` → exit **1**. (A shelf *or*
   a live env is enough to proceed.)
3. `--format json` → one JSON object (see §9.3) → exit 0.
4. Otherwise print the block (see §9.1) → exit 0.
5. Shadowing warnings (stderr) if the name matches shelves in multiple pantries.

### 4.4 The per-shelf block

For each matching shelf, in search order:

```
Shelf N:
    Field             Value
```

The fields (a `tabulate(..., tablefmt="plain")` table indented 4 spaces):

| Field | Value |
|---|---|
| `Pantry` | absolute pantry path |
| `Path` | absolute shelf dir `<pantry>/shelves/<name>` |
| `Writable` | `r/w` or `r/o` |
| `Save hash` | truncated hash or `none` |
| `Archive` | `<can path>  (<bytes> bytes)` if a can exists, otherwise `NOT ARCHIVED — run: hubenv save <name>` |

The can lookup is explicit: `NbwShelf(env_archive_path(NAME, DEFAULT_ARCHIVE_FORMAT)).exists()` — the file must physically exist to count as archived (same invariant as `has_can`).

Preceding lines:

```
Environment: <name>

  Live env:    <abs path> *        (live match found)
  Live env:    (not installed)     (no live match)

  Shelf 1: …
  Shelf 2: …
```

If **no** shelves match (but a live env exists), the block ends with
`  No shelves found.` — a `live` (no shelf at all) environment.

---

## 5. Exit codes

| Condition | Code |
|---|---|
| `ls`, any result set (including empty) | 0 |
| `info`, any match (shelf, live env, or both) | 0 |
| `info`, name found as neither shelf nor live env | 1 |

(`--format json` does not change exit codes.)

---

## 6. Side-effect summary

| Flag combination | Filesystem | Pantry | Live env |
|---|---|---|---|
| `ls` (all combos) | none | read-only | read-only |
| `info` (all combos) | none | read-only | read-only |

No writes, no kernel touches, no subprocesses (other than mamba's list of
live envs, which is filesystem scanning).

---

## 7. Edge cases

- **`ls` with no patterns**: the pattern list is normalized to `[None]`, so a
  bare `hubenv ls` always lists everything (shelves across all pantries + all
  live envs).
- **First-match collapse**: `ls demo` with shelves in two pantries prints one
  row (the first found) — unless `--all`, in which case both rows appear.
  The same name can appear once as a shelf row and never twice for the live
  marker.
- **Live-only environments** (mamba env with no shelf) appear as the
  `not a shelf` row, and `info` reports `No shelves found.` — the env is
  state `live` per the state model, not an error.
- **Spec-only shelves** are distinguishable in both commands: `ARCHIVE` cell
  `spec-only` / `info` `Archive: NOT ARCHIVED — run: hubenv save <name>`.
- **Read-only pantries** are displayed (`r/o`) but never refused — reading a
  read-only pantry is fine.
- **Shadowing** (same name in multiple pantries) is always reported as a
  warning on **stderr** after the table, so stdout stays parseable.

---

## 8. Pantry interaction

- **Read-only commands** — no pantry is written.
- **`--pantry` semantics: source / search scope.** It filters the shelf
  search to one pantry and does **not** fall back to the chain if the shelf
  is not there (consistent with [`hubenv.md`](hubenv.md) §4.5): `ls`/`info`
  with `--pantry PATH` where the shelf is absent report no shelves for it
  (live envs still listed in `ls`; `info` falls through to the live-env
  case or the not-found error).
- **Default (no `--pantry`)**: the full `NBW_PANTRY` chain is searched in
  priority order; the first match wins per name unless `--all`.
- `ls`/`info` **are** on the `--pantry` offering list ([`hubenv.md`](hubenv.md)
  §4.5; RE-12 resolved): `create`, `save`, `restore`, `ls`, `info`, `rm`,
  `ensure`, `export`, `var ls/add/rm`.

---

## 9. Output (stdout) examples

### 9.1 `ls --format table` (default)

```
$ hubenv ls demo
NAME                 PANTRY                           STATUS     ARCHIVE          LIVE
----------------------------------------------------------------------------------------
demo                 /home/u/pantries/local           r/w        abc123def456     *
prod                 /home/u/pantries/remote          r/o        spec-only
scratch              <live>                           not a shelf
```

(stderr, if `demo` also has a shelf in a second pantry:)

```
WARNING: 'demo' shadowed across pantries: /home/u/pantries/local, /home/u/pantries/remote
```

### 9.2 `ls --format json`

```json
{
  "shelves": [
    {
      "name": "demo",
      "pantry": "/home/u/pantries/local",
      "writable": true,
      "save_hash": "abc123def456...",
      "can": true
    },
    {
      "name": "prod",
      "pantry": "/home/u/pantries/remote",
      "writable": false,
      "save_hash": null,
      "can": false
    }
  ],
  "live_envs": [
    {
      "name": "demo",
      "path": "/home/u/.nbw-live/mm/envs/demo"
    }
  ]
}
```

### 9.3 `info NAME --format table`

```
$ hubenv info demo
Environment: demo

  Live env:    /home/u/.nbw-live/mm/envs/demo *

  Shelf 1:
      Pantry      /home/u/pantries/local
      Path        /home/u/pantries/local/shelves/demo
      Writable    r/w
      Save hash   abc123def456...
      Archive     /home/u/pantries/local/shelves/demo/archives/env-demo.tar  (1843200 bytes)

$ hubenv info prod
Environment: prod

  Live env:    (not installed)

  Shelf 1:
      Pantry      /home/u/pantries/remote
      Path        /home/u/pantries/remote/shelves/prod
      Writable    r/o
      Save hash   none
      Archive     NOT ARCHIVED — run: hubenv save prod
```

### 9.4 `info NAME --format json`

```json
{
  "name": "demo",
  "shelves": [
    {
      "name": "demo",
      "pantry": "/home/u/pantries/local",
      "writable": true,
      "save_hash": "abc123def456...",
      "can": true,
      "can_path": "/home/u/pantries/local/shelves/demo/archives/env-demo.tar"
    }
  ],
  "live_env": {
    "name": "demo",
    "path": "/home/u/.nbw-live/mm/envs/demo"
  }
}
```

### 9.5 Not-found

(stderr only — stdout empty:)

```
WARNING: No shelf or live env named 'ghost' found.
```

---

## 10. What is NOT done (out of scope for the current implementation)

- No `--all` in `info` (the single-name command always shows every shelf
  matching the name).
- No `--format` other than `table` / `json`.
- No live-environment package listing, kernel listing, or disk-usage stats —
  `hubenv ls`/`info` are shelf + live-path level only.
- No `--pantry` fallback: when `--pantry` is given and the shelf is absent,
  the chain is **not** searched.
- No modification of any state; a failed or partial read is still exit 0
  (inspection is "best effort display", never a mutating contract).

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§2 state concepts, §4.5 pantry
  resolution, §5.4 Inspection stubs, §7 rough edges).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§5 layout, §6–§7
  store methods, §10 output discipline, §11 exit codes, §12 environment state
  model; `has_can` is the single "archived" source of truth).
- [`hubenv-env-save.md`](hubenv-env-save.md) / [`hubenv-env-restore.md`](hubenv-env-restore.md) — the commands that create and consume the can this spec reports on.
