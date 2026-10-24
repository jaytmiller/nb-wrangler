# `hubenv data` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/data.py`, `nb_wrangler/data_manager.py`,
> `nb_wrangler/pantry.py`, and `nb_wrangler/cli.py` (dispatch).
>
> Verified against `tests/hubenv/test_data.py`.

---

## 1. Purpose

The `data` group manages **data archives** for an environment — the
`refdata` / supporting-data files (e.g. reference atlases, data tarballs)
that are *distinct from* the environment can. Five verbs:

- **`data ls NAME`** — list data archives (scans the shelf's `archives/`
  dir for `data-*` files).
- **`data download NAME`** — download data archives declared by the env's
  wrangler spec into the shelf.
- **`data unpack NAME`** — unpack downloaded archives into the env's install
  locations (with symlinks by default).
- **`data pack NAME`** — pack the live data dirs back into archive files in
  the shelf.
- **`data clean NAME [archived|unpacked|both]`** — delete data archives and/or
  unpacked files.

**Key architectural distinction**: `data ls` reads the pantry *directly*;
all other verbs **delegate** to `data_manager.py`, which in turn runs the
**nb-wrangler** machinery (`NotebookWrangler.main()`) with data flags. The
`data` group is the hubenv front door to wrangler's `--data-*` path without
reimplementing it.

---

## 2. Command synopsis

```
hubenv data ls       NAME [--format table|json]
hubenv data download NAME [--select REGEX] [--no-validate]
hubenv data unpack   NAME [--no-unpack-existing] [--symlinks|--no-symlinks]
hubenv data pack     NAME
hubenv data clean    NAME [archived|unpacked|both]
```

---

## 3. Arguments

### 3.1 `data ls`

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name. |
| `--format` | optional, `table` | `table` (default) or `json`. |

### 3.2 `data download`

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name. |
| `--select REGEX` | optional, `.*` | Python regex selecting archives by repo name / section name / URL (passed to `--data-select`). |
| `--no-validate` | optional, `False` | Skip post-download checksum/manifest validation. |

### 3.3 `data unpack`

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name. |
| `--no-unpack-existing` | optional, `False` | Skip archives already unpacked. |
| `--symlinks` (default) | optional | Create symlinks at install_data locations. |
| `--no-symlinks` | optional, `False` | Do **not** create symlinks. |

### 3.4 `data pack`

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name. |

### 3.5 `data clean`

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name. |
| `mode` | optional, `both` | `archived` (delete archive files only), `unpacked` (delete unpacked files
  only), or `both` (default). |

### 3.6 Dispatch guard (RE-09 resolved)

Bare `hubenv data` (no sub-command) →
`hubenv data: sub-command required. Use one of: ls, download, unpack, pack,
clean` (stderr) → exit **1**. (Same pattern as `hubenv var`.)

---

## 4. Execution paths

### 4.1 `data ls NAME`

1. `config = PantryStore()` (default chain).
2. For each shelf matching `NAME` (`config.find_shelves(NAME)`), scan
   `<shelf>/archives/` for regular files matching `data-*` (excludes
   `last-save.sha256`, `env-*.tar` can files, and any non-`data-*` file).
3. Collect `(filename, size)` tuples, **sorted by filename**.
4. Emit:
   - **table** (default):
     ```
     ARCHIVE                      SIZE
     ----------------------------------------------------------------------
     data-roman.tar.gz            2048
     data-stips.tar.gz            512
     ```
     empty → `(no data archives defined for '<name>')`.
   - **json**:
     ```json
     {
       "name": "<name>",
       "archives": ["data-alpha.tar.gz"]
     }
     ```
5. → exit **0** (never exits 1; no-shelf = empty list).

### 4.2 `data download NAME [--select REGEX] [--no-validate]`

1. `data_manager.download_data(NAME, select=args.select, validate=not
   args.no_validate)`:
   - Resolve the shelf spec via `NbwPantrySet.from_env().get_shelf(NAME).spec_path`.
   - **No spec** →
     `No wrangler spec found for env '<name>'.` (stderr) → return False
     → `data download` exits **1**.
   - Build a `WranglerConfig` with `spec_file=<spec>`, `repos_dir=<spec dir>/notebook-repos`, `output_dir=$NBW_ROOT/temps`, and the flags
     `data_download=True`, `data_select=select`,
     `data_no_validation=not validate`.
   - `NotebookWrangler().main()` runs the **wrangler data-download step**;
     any exception → logged as a failure → return False.
2. Return False → exit **1**; True →
   `Downloaded data archives for '<name>'.` → exit **0**.

### 4.3 `data unpack NAME [--no-unpack-existing] [--symlinks|--no-symlinks]`

1. `data_manager.unpack_data(NAME, symlinks=args.symlinks,
   no_unpack_existing=args.no_unpack_existing)`:
   - Same spec resolution as download (no spec → exit 1).
   - Config with `data_unpack=True`, `data_no_symlinks=not symlinks`,
     `data_no_unpack_existing=no_unpack_existing`.
   - Runs the wrangler **data-unpack step**.
2. Success →
   `Unpacked data archives for '<name>'.` → exit **0**; failure → exit **1**.

### 4.4 `data pack NAME`

1. `data_manager.pack_data(NAME)`:
   - Spec resolution; no spec → exit 1.
   - Config with `data_pack=True`; runs the wrangler **data-pack step**.
2. Success →
   `Packed data archives for '<name>'.` → exit **0**; failure → exit **1**.

### 4.5 `data clean NAME [archived|unpacked|both]`

1. `data_manager.delete_data(NAME, mode=args.mode)`:
   - Spec resolution; no spec → exit 1.
   - Config with `data_delete=mode` (verbatim: `archived` / `unpacked` /
     `both`); runs the wrangler **data-delete step**.
2. Success →
   `Cleaned data for '<name>' (mode: <mode>).` → exit **0**; failure →
   exit **1**.

---

## 5. Exit codes

| Command | Condition | Code |
|---|---|---|
| `data ls` | always (empty or populated) | 0 |
| `data download/unpack/pack/clean` | spec found + wrangler step succeeds | 0 |
| `data download/unpack/pack/clean` | no wrangler spec for the env | 1 |
| `data download/unpack/pack/clean` | wrangler step fails (exception / error) | 1 |
| bare `data` (no sub-command) | RE-09 resolved | 1 |

---

## 6. Side-effect summary by flag combination

| Verb | Archives in shelf | Live data dirs | Symlinks |
|---|---|---|---|
| `data ls` | read-only | read-only | read-only |
| `data download` | archives written to `<shelf>/archives/data-*` | untouched | untouched |
| `data unpack` | read-only | unpacked into install locations | created by default |
| `data pack` | archive files written (from live dirs) | read-only | untouched |
| `data clean both` | archive files deleted | unpacked files deleted | deleted |
| `data clean archived` | archive files deleted | untouched | untouched |
| `data clean unpacked` | untouched | unpacked files deleted | deleted |

---

## 7. Edge cases

- **`data ls` has no `--pantry`** — it reads the full `NBW_PANTRY` chain
  (no `--pantry` offered). RE-12 partial: `data *` is deliberately out of
  scope (it is bound to the wrangler spec, which has its own pantry).
- **`data ls` excludes internal files** — only `data-*` files are listed;
  `last-save.sha256` and the `env-*.tar` can are not data archives.
- **Bare `data`** → RE-09 resolved: clean usage error, exit 1 (not 0).
- **No shelf spec** → all four action verbs exit 1 with
  `No wrangler spec found for env '<name>'.` — *before* any wrangler step
  runs.
- **`--select` is a regex, not a glob** — matched against repo name,
  section name, or URL (via `RefdataValidator.filter_data_url`).
- **`--no-symlinks`** is a mutually-exclusive group with `--symlinks` (default
  `--symlinks` true); `--no-symlinks` unsets symlink creation.
- **`data clean` mode is optional** — `nargs="?"` with default `both`; a
  bare `data clean NAME` cleans both.
- **Wrangler step failures** are reported as a single `False`; the specific
  wrangler error is logged by `NotebookWrangler.main()` (not re-printed by
  the hubenv command).

---

## 8. Pantry interaction

- **Read** — `data ls` scans the full `NBW_PANTRY` chain (no `--pantry`).
  The four action verbs resolve the shelf spec via
  `NbwPantrySet.from_env().get_shelf(NAME)` (chain).
- **Write** — `data download`/`pack` write archives to
  `<shelf>/archives/data-*`; `data unpack`/`clean` write/delete live data
  dirs (outside the pantry).
- **No `--pantry`** on any `data` verb (RE-12 partial — deliberately out of
  scope).

---

## 9. Output (stdout) examples

### 9.1 `data ls` (table, populated)

```
$ hubenv data ls demo
ARCHIVE                      SIZE
----------------------------------------------------------------------
data-roman.tar.gz            2048
data-stips.tar.gz            512
```

### 9.2 `data ls` (table, empty)

```
$ hubenv data ls ghost
(no data archives defined for 'ghost')
```

### 9.3 `data ls --format json`

```json
{
  "name": "demo",
  "archives": [
    "data-roman.tar.gz",
    "data-stips.tar.gz"
  ]
}
```

### 9.4 `data download` (success)

```
$ hubenv data download demo --select roman_.* --no-validate
Downloaded data archives for 'demo'.
```

### 9.5 `data unpack` (success)

```
$ hubenv data unpack demo
Unpacked data archives for 'demo'.
```

### 9.6 `data pack` (success)

```
$ hubenv data pack demo
Packed data archives for 'demo'.
```

### 9.7 `data clean` (success)

```
$ hubenv data clean demo both
Cleaned data for 'demo' (mode: both).
```

### 9.8 No spec (any action verb)

(stderr; stdout empty:)

```
No wrangler spec found for env 'ghost'.
```

### 9.9 Bare `data` (RE-09)

(stderr; stdout empty:)

```
ERROR: hubenv data: sub-command required. Use one of: ls, download, unpack, pack, clean
```

---

## 10. What is NOT done (out of scope for the current implementation)

- No **`--pantry`** on any `data` verb (RE-12 partial — deliberately out of
  scope).
- No **`--select`** on `data ls` (it lists all `data-*`; selection is a
  download concern).
- No **glob** on `data ls` (regex is only for `--select`).
- No **partial clean** (only `archived` / `unpacked` / `both`).
- No **dry-run** on any `data` verb.
- No **validation toggle** on `data ls` / `unpack` / `pack` / `clean` (only
  `download` has `--no-validate`).

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§4.3 stdout contract, §4.4 exit
  codes, §4.5 pantry resolution, §5.6 Data stubs, §7 RE-09 / RE-12).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§3 global flags,
  §6–§7 store methods, §10 output discipline, §11 exit codes).
- [`hubenv-env-save.md`](hubenv-env-save.md) — the env can (distinct from
  data archives).
- [`hubenv-var.md`](hubenv-var.md) — the sibling group with the same dispatch
  pattern (`_dispatch_data` vs. `_dispatch_var`).
