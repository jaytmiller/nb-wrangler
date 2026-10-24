# `hubenv var` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/var.py`, `nb_wrangler/hubenv/env_spec.py`,
> `nb_wrangler/hubenv/_common.py`, `nb_wrangler/pantry.py`, and
> `nb_wrangler/environment.py`.
>
> Verified against `tests/hubenv/test_var.py`.

---

## 1. Purpose

The `var` group manages the **`environment_vars`** section of an env's shelf
spec — the set of `export KEY=VALUE` lines that get emitted when the env is
activated. It has three verbs:

- **`var ls NAME [GLOB…]`** — read the variables (table, `export …` lines, or
  JSON).
- **`var add NAME VAR=VALUE…`** — add/update variables and **re-register the
  kernel** so the Jupyter kernel picks them up.
- **`var rm NAME GLOB…`** — remove variables by glob and **re-register the
  kernel**.

The spec is the **source of truth**; the kernel is a *cache* of the spec's
`environment_vars`. Every mutation (`add`, `rm`) re-registers the kernel, and
a failed re-registration is a **warning, never a rollback** (the spec stays
updated).

---

## 2. Command synopsis

```
hubenv var ls   NAME [GLOB…] [--export] [--format table|json] [--pantry PATH]
hubenv var add  NAME VAR=VALUE… [--pantry PATH]
hubenv var rm   NAME GLOB… [--pantry PATH]
```

---

## 3. Arguments

### 3.1 `var ls`

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name. |
| `GLOB…` | optional, zero or more | `fnmatch` patterns filtering variable *names*; empty → all vars. |
| `--export` | optional, `False` | Print `export VAR=VALUE` lines (suitable for `eval`). |
| `--format` | optional, `table` | `table` (default) or `json`. |
| `--pantry PATH` | optional, `None` | Restrict shelf search to a single pantry directory. |

**Mutual exclusion (RE-08 resolved):** `--export` and `--format json` are
incompatible. Passing both is a **usage error**:
`--export and --format json are mutually exclusive; choose one.` (stderr,
exit 1).

### 3.2 `var add`

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name. |
| `VAR=VALUE…` | required, one or more | Assignments, split on the **first** `=`. |
| `--pantry PATH` | optional, `None` | Restrict shelf search to a single pantry directory. |

### 3.3 `var rm`

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name. |
| `GLOB…` | required, one or more | `fnmatch` patterns of variable names to remove. |
| `--pantry PATH` | optional, `None` | Restrict shelf search to a single pantry directory. |

---

## 4. Execution paths

### 4.1 `var ls NAME [GLOB…]`

1. **Mutual-exclusion guard** — if `--export` and `--format json` both
   set →
   `--export and --format json are mutually exclusive; choose one.` (stderr)
   → exit **1**.
2. `store = store_for(args)` — single `--pantry` pantry or the default chain
   ([`hubenv-common.md`](hubenv-common.md) §6).
3. `spec = load_hubenv_spec(store, NAME)` — **no shelf spec → fallback seed**
   (`seed_from_empty`, no `environment_vars`) so an env with no spec is an
   *empty view*, not an error.
4. `env_vars = spec.get("environment_vars") or {}`.
5. Filter by glob (empty list → all; `fnmatch` per name).
6. Emit:
   - **`--format json`** →
     `{"name": "<name>", "environment_vars": {…sorted…}}` (JSON, stdout);
   - **`--export`** → one `export KEY=VALUE` line per variable, **sorted by
     key** (stdout);
   - **table** (default) → two-column table, **sorted by key**:
     ```
     VAR                  VALUE
     ------------------------------------------------------------
     DEBUG                1
     API_KEY              secret
     ```
     empty → `(no environment variables defined for '<name>')`.
7. → exit **0**. (`var ls` never exits 1.)

### 4.2 `var add NAME VAR=VALUE…`

1. **Spec-exists guard** (before any mutation) —
   `store.shelf_spec_path(NAME).exists()` is False →
   ```
   No spec found for env '<name>'.
   Create it first: hubenv create <name> --from-empty
   ```
   (stderr) → exit **1**. (RE-11 resolved: **no auto-creation**; the shelf
   must already exist.)
2. **Parse** assignments — each `item` split on the **first** `=`:
   - no `=` in `item` →
     `'<item>' is not a VAR=VALUE assignment` (stderr) → exit **1**
     (parse runs before the spec load; a malformed assignment aborts even
     if the spec exists).
3. Load the spec; `env_vars = spec.get("environment_vars") or {}`;
   `spec["environment_vars"] = env_vars`; `env_vars.update(updates)`.
4. `save_hubenv_spec(store, NAME, spec)` — unconditional overwrite.
5. **Kernel refresh** — `EnvironmentManager.register_environment(NAME, NAME,
   env_vars)` (re-registers the kernel with the env name as display name and
   the new var map). On failure → warning
   `Kernel refresh for '<name>' failed (spec still updated).` (stderr);
   the spec is **not** rolled back.
6. Print (stdout), one line per variable **sorted**:
   ```
   Set <key>=<value> for env '<name>'
   ```
   then
   ```
   Kernel refreshed for '<name>'.
   ```
   → exit **0**.

### 4.3 `var rm NAME GLOB…`

1. Load the spec (fallback seed if no shelf — **no spec-exists guard**).
2. `env_vars = spec.get("environment_vars") or {}`;
   `removed = remove_vars_by_glob(env_vars, GLOB…)`:
   - `fnmatch` each name; delete matches in-place.
3. **No matches** →
   `No matching variables for <GLOB list> in env '<name>'.` (stdout)
   → exit **0**; spec **untouched**, kernel **not refreshed**.
4. **Matches** →
   `save_hubenv_spec`; kernel refresh (same as `var add`; warning on
   failure); print (stdout), one line per removed variable **sorted**:
   ```
   Removed <key> from env '<name>'
   ```
   then
   ```
   Kernel refreshed for '<name>'.
   ```
   → exit **0**.

---

## 5. Exit codes

| Command | Condition | Code |
|---|---|---|
| `var ls` | always (table / export / json, any or no vars) | 0 |
| `var ls` | `--export` + `--format json` both set | 1 |
| `var add` | shelf spec missing (RE-11) | 1 |
| `var add` | malformed assignment (no `=`) | 1 |
| `var add` | success | 0 |
| `var rm` | no matches | 0 |
| `var rm` | success (matches) | 0 |

---

## 6. Side-effect summary by flag combination

| Verb / combination | Shelf spec | Kernel |
|---|---|---|
| `var ls` (any format) | nothing | nothing |
| `var add NAME VAR=VALUE…` | rewritten (`environment_vars` updated, form-preserved, fresh `spec_sha256`) | **re-registered** with the new var map |
| `var rm NAME GLOB…` (matches) | rewritten (matching vars deleted) | **re-registered** |
| `var rm NAME GLOB…` (no match) | untouched | not refreshed |

Kernel re-registration is best effort: a failure warns but **never rolls back**
the spec (the spec is the source of truth, §4.6).

---

## 7. Edge cases

- **`var ls` on a spec-less env** → empty view, not an error:
  `(no environment variables defined for '<name>')` (table), empty
  JSON object, empty export. (The fallback seed is `["pip"]` with no
  `environment_vars`.)
- **`--export` and `--format json`** — RE-08 resolved to a clean usage error
  (stderr, exit 1), not "JSON wins".
- **`var add` on a spec-less env** — RE-11 resolved: **exit 1 with a
  create-suggestion**, no auto-creation. (`var rm` on a spec-less env is a
  no-op with the "No matching variables" message — it was never erroring.)
- **First-`=` split** — `URL=http://x?a=1&b=2` sets `URL` to the full value
  (split on the first `=` only).
- **`var add` is idempotent** — re-adding the same `VAR=VALUE` rewrites the
  same value; the kernel is re-registered each time.
- **No `--dry-run`** on `var add`/`var rm` — the spec write is unconditional
  (no confirm, no backup).
- **Glob semantics** — `fnmatch` (name-level, not path-level); `var rm`
  with a glob matching nothing is exit 0 (not an error).
- **Sorted output** — table rows, `export` lines, and JSON keys are all
  **sorted by variable name**; the per-var `Set …` / `Removed …` lines are
  also sorted.

---

## 8. Pantry interaction

- **Read** — default `NBW_PANTRY` chain, or the single `--pantry` pantry via
  `store_for(args)` (RE-12 resolved: `var ls/add/rm` accept `--pantry`).
- **Write** — the shelf spec (unconditional overwrite, source form preserved,
  fresh `spec_sha256`).
- No live-env check — `var` commands operate on the **spec only**; they do
  not require a live env (the kernel refresh re-registers via mamba, which
  is a best-effort side effect).

---

## 9. Output (stdout) examples

### 9.1 `var ls NAME` (table, default)

```
$ hubenv var ls demo
VAR                  VALUE
------------------------------------------------------------
DEBUG                1
API_KEY              secret
```

### 9.2 `var ls NAME` (empty)

```
$ hubenv var ls ghost
(no environment variables defined for 'ghost')
```

### 9.3 `var ls NAME --export`

```
$ hubenv var ls demo --export
export API_KEY=secret
export DEBUG=1
```

### 9.4 `var ls NAME --format json`

```json
{
  "name": "demo",
  "environment_vars": {
    "API_KEY": "secret",
    "DEBUG": "1"
  }
}
```

### 9.5 `var add NAME VAR=VALUE…`

```
$ hubenv var add demo DEBUG=1
Set DEBUG=1 for env 'demo'
Kernel refreshed for 'demo'.
```

### 9.6 `var rm NAME GLOB…` (matches)

```
$ hubenv var rm demo API_
Removed API_KEY from env 'demo'
Kernel refreshed for 'demo'.
```

### 9.7 `var rm NAME GLOB…` (no match)

```
$ hubenv var rm demo NOPE
No matching variables for ['NOPE'] in env 'demo'.
```
(exit 0; spec untouched, kernel not refreshed.)

### 9.8 `var ls` mutual-exclusion error

(stderr; stdout empty:)

```
ERROR: --export and --format json are mutually exclusive; choose one.
```

### 9.9 `var add` on a spec-less env

(stderr; stdout empty:)

```
ERROR: No spec found for env 'ghost'. Create it first: hubenv create ghost --from-empty
```

---

## 10. What is NOT done (out of scope for the current implementation)

- No **`--dry-run`** on `var add`/`var rm` (the spec write is unconditional).
- No **rollback on kernel-refresh failure** — the spec is the source of
  truth; a failed re-registration is a warning only.
- No **live-env requirement** — `var` commands operate on the spec; they do
  not verify the live env exists.
- No **`--format`** on `var add`/`var rm` (only `var ls`).
- No **batch multi-env** target (one `NAME` per invocation).

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§4.3 stdout contract, §4.4 exit
  codes, §4.6 kernel conventions (re-register on var change), §4.5 pantry
  resolution, §5.5 Spec & vars stubs, §7 RE-08 / RE-11 / RE-12).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§3 global flags,
  §6–§7 store methods, §8 implicit spec model (`load_hubenv_spec` /
  `save_hubenv_spec` and the fallback seed), §10 output discipline, §11 exit
  codes).
- [`hubenv-kernel-and-shell.md`](hubenv-kernel-and-shell.md) — the kernel
  that `var add`/`var rm` re-register, and the `activate` snippet that
  emits the `environment_vars` `var ls --export` produces.
- [`hubenv-env-restore.md`](hubenv-env-restore.md) / [`hubenv-env-create.md`](hubenv-env-create.md) — the commands that create the shelf spec
  `var add` requires.
