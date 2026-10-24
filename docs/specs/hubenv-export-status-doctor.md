# `hubenv export` / `status` / `doctor` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/export.py`, `nb_wrangler/hubenv/status.py`,
> `nb_wrangler/hubenv/doctor.py`, `nb_wrangler/hubenv/env_spec.py`, and
> `nb_wrangler/pantry.py`.
>
> Verified against `tests/hubenv/test_export_status_doctor.py`.

---

## 1. Purpose

The utility trio is the "what do I have, and is it healthy?" surface:

- **`hubenv export NAME`** — export the env's implicit spec in one of three
  formats (mamba spec YAML, pip requirements list, or full wrangler spec
  YAML).
- **`hubenv status`** — a whole-system state summary: one row per distinct
  env, with live/archived/kernel/active state.
- **`hubenv doctor`** — a self-test suite of four checks (mamba availability,
  pantry writability, kernel-JSON sanity, spec-only shelves) with pass/fail
  reporting.

`status` and `doctor` are **always exit 0** (except `doctor`, which exits 1
on any failing check — see §5).

---

## 2. Command synopsis

```
hubenv export NAME [--to-mamba-spec | --to-requirements | --to-wrangler-spec]
                  [-o FILE | -] [--pantry PATH]
hubenv status [--format table|json]
hubenv doctor [--format table|json]
```

---

## 3. Arguments

### 3.1 `export`

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name. |
| `--to-mamba-spec` | optional, part of a mutually-exclusive group | Export as mamba spec YAML. |
| `--to-requirements` | optional, part of the group | Export as a pip requirements list. |
| `--to-wrangler-spec` | optional, part of the group | Export as a full wrangler spec YAML. |
| `-o FILE`, `--output FILE` | optional, `-` | Output file; `-` (default) = stdout. |
| `--pantry PATH` | optional, `None` | Restrict shelf search to a single pantry directory. |

**No flag** → default is `--to-mamba-spec` (the mamba-view YAML). The three
`--to-*` flags are mutually exclusive; none are required.

### 3.2 `status` / `doctor`

| Argument | Required / Default | Description |
|---|---|---|
| `--format` | optional, `table` | `table` (default) or `json`. |

No positional arguments.

---

## 4. Execution paths

### 4.1 `export NAME`

1. `store = store_for(args)` (single `--pantry` pantry or the default chain).
2. `spec_path = store.shelf_spec_path(NAME)`. **No spec** →
   `No spec found for env '<name>'.` (stderr) → exit **1**.
3. `spec = load_hubenv_spec(store, NAME)`.
4. Format:
   - **`--to-requirements`** → `spec_to_requirements(spec)`:
     extract the `{"pip": […]}` sub-list from `dependencies` into lines
     (`numpy`, `numpy==1.26.4`, …), joined by `\n` + trailing newline.
     - **Empty** →
       `spec for '<name>' has no pip packages; empty requirements output`
       (stderr, RE-10 resolved) and stdout is **empty**.
   - **`--to-wrangler-spec`** → `to_wrangler_yaml(NAME, spec)`:
     a full wrangler spec YAML (with `image_spec_header`,
     `extra_mamba_packages`, `extra_pip_packages`, `spec_sha256`, etc.).
   - **default / `--to-mamba-spec`** → `yaml_dumps(spec)`: the mamba-view
     YAML.
5. Write:
   - **`-o -`** (default) → `print(output, end="")` to stdout.
   - **`-o FILE`** → `Path(FILE).write_text(output)`; then print
     `Exported spec for '<name>' to <FILE>` to stdout.
6. → exit **0**.

### 4.2 `status`

1. `config = PantryStore()` (chain).
2. **Aggregate**:
   - `active_env = os.environ.get("NBW_ACTIVE_ENV")`.
   - `active_pantry = os.environ.get("NBW_PANTRY")` or
     `config.first_writable_pantry()`.
   - `live_envs = config.list_live_envs()`.
   - `shelves = config.list_shelves()`.
   - `kernelspecs = list_kernelspecs()` — runs `jupyter kernelspec list
     --json` (via `EnvironmentManager`); parses the `kernelspecs` dict;
     lowercases keys; returns `{}` on any parse/execution failure.
3. **Per-env rows** (`build_status_envs`) — one row per distinct env name
   (union of live envs and shelf names). State is computed by
   `_state_for(live, has_shelf, has_can)` where **`has_can` is the single
   source of truth** for "actually archived" (a shelf dir alone is *not*
   archived — [`hubenv-common.md`](hubenv-common.md) §12):

   | live? | shelf? | can? | State |
   |---|---|---|---|
   | ✅ | ✅ | ✅ | `live+archived` |
   | ✅ | ✅ | ❌ | `live+spec-only` |
   | ✅ | ❌ | ❌ | `live` |
   | ❌ | ✅ | ✅ | `archived` |
   | ❌ | ✅ | ❌ | `spec-only` |

4. **Emit**:
   - **table** (default):
     ```
     Active env:     <name or (none)>
     Active pantry:  <path>

     +------------+----------------+... (grid table)
     | ENV        | STATE          | LIVE            | PANTRY   | KERNEL     | ARCHIVED      |
     |------------+----------------+-----------------|----------|------------|---------------|
     | demo       | live+archived  | /path/mm/demo   | /pantry  | registered | yes           |
     +------------+----------------+-----------------+----------+------------+---------------|
     | prod       | spec-only      | -               | /pantry  | absent     | no (spec-only)|
     +------------+----------------+-----------------+----------+------------+---------------|

     Pantries:
     +----------------------+---------+
     | PATH                 | Writable |
     |----------------------+----------|
     | /pantry1             | r/w      |
     | /pantry2             | r/o      |
     +----------------------+----------|
     ```
   - **json**:
     ```json
     {
       "active_env": "<name or null>",
       "active_pantry": "<path>",
       "pantries": [
         {"path": "/pantry1", "writable": true},
         {"path": "/pantry2", "writable": false}
       ],
       "environments": [
         {
           "name": "demo",
           "state": "live+archived",
           "live": true,
           "can": true,
           "live_path": "/path/mm/demo",
           "pantry": "/pantry1",
           "kernel_registered": true
         }
       ]
     }
     ```
5. → exit **0** (always).

### 4.3 `doctor`

1. `config = PantryStore()` (chain).
2. Run **four checks in order** (each returns a dict with
   `check` / `pass` / `detail` / `hint`):

   | # | Check | Pass condition | Fail detail | Fail hint |
   |---|---|---|---|---|
   | 1 | mamba/micromamba | `shutil.which("micromamba")` or `shutil.which("mamba")` is non-None | `neither micromamba nor mamba on PATH` | `Install micromamba or add mamba to PATH.` |
   | 2 | pantry writability | ≥ 1 writable pantry in the chain | `No writable pantries` | `Check permissions on: <paths>` |
   | 3 | kernel-JSON sanity | (see below) | (see below) | (see below) |
   | 4 | spec-only shelves | no shelf without a can | `spec-only (no can yet): <names>` | `Run \`hubenv save <name>\` for each to make it restorable.` |

   **Kernel-JSON sanity** (#3): only applies when `NBW_ACTIVE_ENV` is set:
   - No active env → **pass**, `detail = "no active env — skipped"`.
   - Active env → look for the kernel dir at
     `~/.local/share/jupyter/kernels/<name>` (or lowercased):
     - Dir missing → `kernel spec for '<name>' not found` /
       `Run \`hubenv register <name>\` to create it.`
     - `kernel.json` missing → `kernel.json missing in <dir>` /
       `Re-register: \`hubenv register <name>\``
     - `kernel.json` invalid JSON → `invalid kernel.json for '<name>'` /
       `Re-register: \`hubenv register <name>\``
     - `kernel.json` has no `argv` → `kernel.json for '<name>' has no argv`
       / `Re-register: \`hubenv register <name>\``
     - Otherwise → **pass**,
       `detail = "valid kernel.json for '<name>'"`.

3. **Emit**:
   - **table** (default):
     ```
     hubenv doctor — self-test results
     ================================================================================
     +-------------------------+--------+----------------------------------+------------------------+
     | CHECK                   | STATUS | DETAIL                             | HINT                   |
     +-------------------------+--------+----------------------------------+------------------------+
     | mamba/micromamba        | PASS   | micromamba = /path/micromamba      |                       |
     +-------------------------+--------+----------------------------------+------------------------+
     | pantry writability      | PASS   | /pantry1                           |                       |
     +-------------------------+--------+----------------------------------+------------------------+
     | kernel-JSON sanity      | PASS   | no active env — skipped            |                       |
     +-------------------------+--------+----------------------------------+------------------------+
     | spec-only shelves       | PASS   | all shelves have an archive can    |                       |
     +-------------------------+--------+----------------------------------+------------------------+
     ================================================================================
     4/4 checks passed
     ```
   - **json**:
     ```json
     {
       "checks": [
         {"check": "mamba/micromamba", "pass": true, "detail": "…", "hint": ""},
         …
       ],
       "all_pass": true
     }
     ```
4. Exit **0** if all checks pass, **1** otherwise.

---

## 5. Exit codes

| Command | Condition | Code |
|---|---|---|
| `export` | spec found + written | 0 |
| `export` | no shelf spec | 1 |
| `status` | always | 0 |
| `doctor` | all four checks pass | 0 |
| `doctor` | any check fails | 1 |

---

## 6. Side-effect summary by flag combination

| Command / combination | Filesystem |
|---|---|
| `export NAME -o FILE` | writes `<FILE>` (overwrites if present) |
| `export NAME -o -` (default) | nothing (stdout) |
| `status` (any format) | nothing (reads only) |
| `doctor` (any format) | nothing (reads only) |

---

## 7. Edge cases

- **`export` on a spec-less env** → clean error, exit 1 (no auto-create).
- **`export --to-requirements` on a spec with no pip packages** → RE-10
  resolved: stdout is empty, stderr carries the warning, exit **0** (not 1).
- **`status` kernel detection is best effort** — `jupyter kernelspec list
  --json` failure (jupyter not installed, parse error) returns `{}`, so no
  env is marked kernel-registered; the command still exits 0.
- **`status` active-env / active-pantry** come from env vars, not from
  the env list; `NBW_ACTIVE_ENV` unset → `(none)` (table) or `null`
  (JSON).
- **`doctor` kernel-JSON check** only inspects the *active* env
  (`NBW_ACTIVE_ENV`); when no env is active, the check is skipped and
  **passes**.
- **`doctor` spec-only check** lists all shelves without a can; the hint
  tells you to `hubenv save` each. A shelf with a can is never flagged.
- **`doctor` table footer** always shows `<n>/4 checks passed` (n = number
  of passing checks).

---

## 8. Pantry interaction

- **Read-only** on all three commands (no writes).
- **`export`** is the only one that accepts `--pantry` (RE-12 resolved —
  via `store_for`). `status` and `doctor` use the full `NBW_PANTRY` chain
  and do **not** accept `--pantry` (RE-12 partial: deliberately out of
  scope).

---

## 9. Output (stdout) examples

### 9.1 `export NAME` (mamba spec, default)

```
$ hubenv export demo
name: demo
channels:
- conda-forge
dependencies:
- python=3.11
- pip
- {pip: [numpy, pandas]}
environment_vars:
  DEBUG: "1"
```

### 9.2 `export NAME --to-requirements`

```
$ hubenv export demo --to-requirements
numpy
pandas
```

### 9.3 `export NAME --to-requirements` (no pip packages — RE-10)

(stderr only; stdout empty:)

```
WARNING: spec for 'demo' has no pip packages; empty requirements output
```

### 9.4 `export NAME --to-wrangler-spec -o out.yaml`

```
$ hubenv export demo --to-wrangler-spec -o out.yaml
Exported spec for 'demo' to out.yaml
```

(out.yaml contains the full wrangler spec YAML with `image_spec_header`,
`extra_mamba_packages`, `extra_pip_packages`, `deployment_name`,
`valid_on`, `expires_on`, `spi`, etc.)

### 9.5 `export NAME` (no spec — stderr; stdout empty)

```
ERROR: No spec found for env 'ghost'.
```

### 9.6 `status` (table)

```
$ hubenv status
Active env:     demo
Active pantry:  /pantry1

+-------+--------------+--------------------+---------+----------+---------------+
| ENV   | STATE        | LIVE               | PANTRY  | KERNEL   | ARCHIVED      |
+=======+==============+====================+=========+==========+===============+
| demo  | live+archived| /path/mm/demo      | /pantry1| registered | yes         |
+-------+--------------+--------------------+---------+----------+---------------+
| prod  | spec-only    | -                  | /pantry2| absent   | no (spec-only)|
+-------+--------------+--------------------+---------+----------+---------------+

Pantries:
+-----------+----------+
| PATH      | Writable |
+===========+==========|
| /pantry1  | r/w      |
+===========+==========|
| /pantry2  | r/o      |
+===========+==========|
```

### 9.7 `status --format json`

```json
{
  "active_env": "demo",
  "active_pantry": "/pantry1",
  "pantries": [
    {"path": "/pantry1", "writable": true},
    {"path": "/pantry2", "writable": false}
  ],
  "environments": [
    {"name": "demo", "state": "live+archived", "live": true, "can": true, "live_path": "/path/mm/demo", "pantry": "/pantry1", "kernel_registered": true},
    {"name": "prod", "state": "spec-only", "live": false, "can": false, "live_path": null, "pantry": "/pantry2", "kernel_registered": false}
  ]
}
```

### 9.8 `doctor` (all pass)

```
$ hubenv doctor
hubenv doctor — self-test results
================================================================================
+-------------------------+--------+----------------------------------+------------------------+
| CHECK                   | STATUS | DETAIL                             | HINT                   |
+=========================+========+==================================+========================+
| mamba/micromamba        | PASS   | micromamba = /path/micromamba      |                        |
+-------------------------+--------+----------------------------------+------------------------+
| pantry writability      | PASS   | /pantry1                           |                        |
+-------------------------+--------+----------------------------------+------------------------+
| kernel-JSON sanity      | PASS   | no active env — skipped            |                        |
+-------------------------+--------+----------------------------------+------------------------+
| spec-only shelves       | PASS   | all shelves have an archive can    |                        |
+-------------------------+--------+----------------------------------+------------------------+
================================================================================
4/4 checks passed
```

### 9.9 `doctor` (one failing — spec-only)

(stderr: none; stdout:)

```
hubenv doctor — self-test results
================================================================================
+-------------------------+--------+----------------------------------+-------------------------------------------+
| CHECK                   | STATUS | DETAIL                             | HINT                                        |
+=========================+========+==================================+=============================================+
| mamba/micromamba        | PASS   | micromamba = /path/micromamba      |                                             |
+-------------------------+--------+----------------------------------+---------------------------------------------|
| pantry writability      | PASS   | /pantry1                           |                                             |
+-------------------------+--------+----------------------------------+---------------------------------------------|
| kernel-JSON sanity      | PASS   | no active env — skipped            |                                             |
+-------------------------+--------+----------------------------------+---------------------------------------------|
| spec-only shelves       | FAIL   | spec-only (no can yet): unsaved    | Run `hubenv save <name>` for each to make it restorable. |
+-------------------------+--------+----------------------------------+---------------------------------------------|
================================================================================
3/4 checks passed
```
(exit **1**.)

---

## 10. What is NOT done (out of scope for the current implementation)

- No **`--pantry`** on `status` / `doctor` (RE-12 partial — deliberately
  out of scope).
- No **`--format`** other than `table` / `json`.
- No **`export` to a directory** (only a single file or stdout).
- No **`status` per-pantry** breakdown (status shows all pantries as a flat
  list; per-env rows carry a single `pantry` field).
- No **`doctor` `--verbose`** or `--fix` — it only reports, never repairs
  (the hints point at the fix commands).

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§4.3 stdout contract, §4.4 exit
  codes, §4.5 pantry resolution, §5.4 Inspection / §5.5 Spec & vars /
  §5.7 Tooling stubs, §7 RE-10 / RE-12 / RE-05).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§3 global flags,
  §6–§7 store methods, §8 implicit spec model (`to_wrangler_yaml`,
  `load_hubenv_spec`, `extract_pip_packages`), §10 output discipline, §11
  exit codes, §12 environment state model).
- [`hubenv-inspection.md`](hubenv-inspection.md) — `ls` / `info` (the
  per-env inspection surface; `status` is the whole-system view).
- [`hubenv-env-save.md`](hubenv-env-save.md) — the command `doctor`'s spec-only
  check points at.
- [`hubenv-kernel-and-shell.md`](hubenv-kernel-and-shell.md) — the kernel
  that `doctor`'s kernel-JSON check inspects.
