# `hubenv install` / `hubenv uninstall` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/env_pkg.py`, `nb_wrangler/hubenv/env_spec.py`,
> `nb_wrangler/environment.py`, and `nb_wrangler/constants.py`.
>
> Verified against `tests/hubenv/test_install_relock.py`.

---

## 1. Purpose

`hubenv install NAME PACKAGE…` and `hubenv uninstall NAME PACKAGE…`
install / remove packages **inside a live mamba environment** and keep the
shelf's **implicit wrangler spec** in sync (the `dependencies` list), so a
later `export`/`relock` reflects the current package set.

They are the only hubenv commands that **write into a live environment**
(mutating its site-packages / conda env) *and* a shelf spec. The command
order is deliberately one-directional: the installer runs **first**, the spec
write happens **only if the install/uninstall succeeded**, and a kernel
re-registration is *not* part of this command (kernel var changes belong to
`var add`/`var rm`; lock re-curation is the user's next step via `hubenv
relock`).

---

## 2. Command synopsis

```
hubenv install   NAME PACKAGE… [--using mamba|pip|uv] [--no-relock] [--dry-run]
hubenv uninstall NAME PACKAGE… [--using mamba|pip|uv] [--no-relock] [--dry-run]
```

---

## 3. Arguments

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Name of the **live** mamba environment (must already exist — no auto-create). |
| `PACKAGE…` | required, positional, one or more | Package names / pin strings for the installer. |
| `--using` | optional, `None` | Installer: `mamba` (conda-level, `NBW_MAMBA_CMD`), `pip`, or `uv`
  (`uv pip`). Omitted → **pip via `$NBW_PIP_CMD`** (the parser help:
  "default: pip via NBW_PIP_CMD"). |
| `--no-relock` | optional, `False` | Suppress the post-action relock suggestion line. |
| `--dry-run` | optional, `False` | Print the planned command + spec delta; execute nothing. |
| global flags | — | `-q/--quiet`, `--verbose`, `--debug`, `--color`, `--log-times`,
  `--reset-log` (see [`hubenv-common.md`](hubenv-common.md) §3). |

---

## 4. Execution paths

Shared pipeline for both verbs (`cmd_env_pkg_action`, action = `install` or
`uninstall`):

1. **Live-env precheck** — `EnvironmentManager.environment_exists(NAME)`.
   Missing → logger error
   `Live environment '<name>' not found.` → exit **1**. This check also runs
   under `--dry-run`.
2. **`--dry-run`** →
   - build the planned command string (`build_pkg_cmd`);
   - print
     `Dry-run: would run: <command>`
     then
     `Spec delta: + pkg1 + pkg2 …` (install) / `Spec delta: - pkg1 …`
     (uninstall);
   → exit **0**. Nothing is written.
3. **Run the installer** (action succeeds → continue):
   - `--using mamba`: `$NBW_MAMBA_CMD install|remove -n NAME -y PKG…`
     via `wrangler_run`;
   - `--using pip` / `uv` / omitted:
     `<pip|uv pip|NBW_PIP_CMD> install|uninstall PKG…`
     inside the env (`em.env_run(name, cmd)`).
   - Any installer failure (`em.handle_result` non-zero) → logger error
     `Failed to <install|uninstall> packages in '<name>': <installer output>`
     → exit **1**, **spec untouched**.
4. **Spec sync** — `update_and_save_spec(store, NAME, PACKAGE…, action, using)`:
   - `--using pip|uv` (and the default) → mutates the `{"pip": […]}`
     sub-list of `dependencies`: add = de-duplicate and append; remove = drop
     entries whose base name (version/prefix stripped, lowercased —
     `pkg_base_name`) matches.
   - `--using mamba` → mutates the conda-string list: add = de-duplicate,
     inserted before the first pip sub-dict; remove = drop by base name.
   - Written via `save_hubenv_spec` — **unconditional overwrite** of the shelf
     spec (see [`hubenv-common.md`](hubenv-common.md) §8).
5. **Relock suggestion** — unless `--no-relock`, prints:
   `Spec updated. Run \`hubenv relock <name>\` to re-curate locks and validate.`
6. → exit **0**.

---

## 5. Exit codes

| Condition | Code |
|---|---|
| `--dry-run` (live env exists) | 0 |
| Live env not found (including under `--dry-run`) | 1 |
| Installer command failed | 1 (spec unmodified) |
| Action completed (packages + spec) | 0 |

---

## 6. Side-effect summary by flag combination

| Combination | Live env | Shelf spec | Kernel |
|---|---|---|---|
| `install` / `uninstall` (default) | packages added / removed | rewritten (pip or conda section) | untouched |
| `… --using mamba` | conda-level change | conda deps rewritten | untouched |
| `… --dry-run` | nothing | nothing | nothing |
| `… --no-relock` | as above | as above | (no suggestion line) |

Rough-edge note (from the top spec stub): the spec update is a *silent*
mutation — it is **unconditional** once the installer succeeds, and there is
no backup of the prior spec; a failed installer leaves the spec unmodified
(the ordering in §4 is load-bearing).

---

## 7. Edge cases

- **Install into a non-live env** — clean error, never an auto-create:
  `Live environment 'ghost' not found.` (exit 1). `install`/`uninstall` do
  **not** accept `--pantry` (they are kernel/live-env bound; RE-12 partial
  resolution — `status`, `doctor`, `data *`, `register`, `unregister`,
  `activate`, `deactivate` are deliberately out of scope, as are `install`/
  `uninstall`).
- **`--dry-run` still validates the live env** — it is not a pure string
  formatter; a missing env under `--dry-run` is exit 1.
- **Deduplication on add** — installing an already-present package rewrites the
  spec list without changing its content.
- **Uninstall by base name** — removing a package matches its base name
  (stripping `==`, `>=`, etc., lowercasing), so `pip uninstall "numpy"` and
  a spec entry `numpy==1.26.4` match.
- **No relock side effect** — this command never re-cures pins; `--no-relock`
  only suppresses the *suggestion*, not behavior.
- **Spec write uses the implicit two-form model** — `save_hubenv_spec`
  round-trips through the full wrangler spec (simple 1-doc or inline 2-doc)
  with a valid `spec_sha256` (RE-14; see
  [`hubenv-common.md`](hubenv-common.md) §8).

---

## 8. Pantry interaction

- **No `--pantry`** on this command. The `PantryStore()` default chain is used
  purely to *locate the shelf spec* for the sync step (step 4); there is no
  pantry-scoped `--pantry` filter because the command is bound to a live
  environment, and RE-12 resolves it to "deliberately out of scope".
- Read: `NBW_PANTRY` chain for shelf-spec lookup.
- Write: shelf spec only (the live env itself is mutated directly by
  mamba/pip/uv, outside the pantry).

---

## 9. Output (stdout) examples

### 9.1 `install --dry-run`

```
$ hubenv install demo numpy pandas --using pip --dry-run
Dry-run: would run: pip install numpy pandas
Spec delta: + numpy + pandas
```

### 9.2 `install` (success)

```
$ hubenv install demo numpy pandas
Spec updated. Run `hubenv relock demo` to re-curate locks and validate.
```

(installer subprocess output goes to stderr/log; only the suggestion line is
the parseable stdout.)

### 9.3 `uninstall --dry-run`

```
$ hubenv uninstall demo numpy --using mamba --dry-run
Dry-run: would run: mamba uninstall -n demo -y numpy
Spec delta: - numpy
```

### 9.4 `--no-relock`

```
$ hubenv install demo numpy --no-relock
```
(stderr: mamba/pip activity only; stdout empty.)

### 9.5 Live env missing

(stderr; stdout empty:)

```
ERROR: Live environment 'ghost' not found.
```

---

## 10. What is NOT done (out of scope for the current implementation)

- No **relock** by default — pins are only *suggested*; run `hubenv relock`
  separately.
- No **kernel re-registration** — env-var changes are `var add`/`var rm`;
  plain install/uninstall leaves the kernel spec alone.
- No **spec backup / diff** — `save_hubenv_spec` overwrites unconditionally.
- No `--pantry` scoping (RE-12 partial; live-env bound).
- No rollback on installer failure (spec simply left untouched).

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§4.3 stdout contract, §4.4 exit
  codes, §4.6 kernel conventions, §5.2 stubs).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§3 global flags,
  §4 runtime config for `NBW_PIP_CMD`/`NBW_MAMBA_CMD`, §8 implicit spec model
  — `update_and_save_spec` add/remove semantics, §10 output discipline,
  §11 exit codes).
- [`hubenv-env-relock.md`](hubenv-env-relock.md) — the command the suggestion
  line points at.
- [`hubenv-env-save.md`](hubenv-env-save.md) — the can this command keeps in
  sync with (package list lives in the same implicit spec).
