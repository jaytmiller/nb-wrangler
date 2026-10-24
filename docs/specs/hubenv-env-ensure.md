# `hubenv ensure` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/env_ensure.py` (which also owns `register`/`unregister`
> — those are specced in [`hubenv-kernel-and-shell.md`](hubenv-kernel-and-shell.md))
> and `nb_wrangler/hubenv/env_restore.py` (`find_restore_shelf`, which
> `ensure` delegates to), `nb_wrangler/environment.py`, and
> `nb_wrangler/hubenv/_common.py` (`print_exports`).
>
> Verified against `tests/hubenv/test_e2e.py` and `test_ensure.py`.

---

## 1. Purpose

`hubenv ensure NAME` is the **canonical "make this env available" entry
point**. It is deliberately idempotent and is the function that at-boot
snippets (from `restore --at-boot`) call at shell startup:

1. **Live env exists** → no-op skip (print exports).
2. **Shelf + can exists** → delegate to `hubenv restore` (unpack + kernel
   register).
3. **Neither** → clean error with a `hubenv create … --name NAME`
   suggestion (exit 1).

`ensure` is the only command that *chooses* between a no-op and a restore
based on live state; `restore` always tries to unpack.

---

## 2. Command synopsis

```
hubenv ensure NAME [--pantry PATH] [--display-name NAME] [--dry-run]
```

---

## 3. Arguments

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name to ensure. |
| `--pantry PATH` | optional, `None` | Source pantry: exact shelf lookup in that pantry (no chain fallback). |
| `--display-name NAME` | optional, `None` | Jupyter kernel display name for the delegated restore; threads through
  to `cmd_env_restore` via an internal `EnsureArgs` namespace. (RE-07
  resolved — previously accepted but ignored.) |
| `--dry-run` | optional, `False` | Print one "would restore" line; nothing executed. |
| global flags | — | `-q/--quiet`, `--verbose`, `--debug`, `--color`, `--log-times`,
  `--reset-log` (see [`hubenv-common.md`](hubenv-common.md) §3). |

---

## 4. Execution paths

### 4.1 Step 1 — Live check

`EnvironmentManager.environment_exists(NAME)`:

- **True** → print
  `Environment '<name>' is already live (idempotent skip).`
  then two `print_exports` lines (stdout):
  ```
  export NBW_ACTIVE_ENV=<name>
  export NBW_ENV_ROOT=<live envs root>/<name>
  ```
  → exit **0**. (This is the entire "live" path — no restore, no kernel
  re-registration.)

### 4.2 Step 2 — Shelf lookup (`find_restore_shelf`)

`EnsureArgs(NAME, pantry, display_name)` is built (with `force=False`,
`at_boot=False`) and `find_restore_shelf` returns:

- **`--pantry` given**:
  - shelf dir `<pantry>/shelves/<name>` exists → `[(pantry, shelf)]`;
  - otherwise → logger error
    `No shelf '<name>' found in pantry <pantry>.` and `None` → exit **1**.
- **No `--pantry`** (chain):
  - **0 matches** → `[]` →
    `No live environment and no archive shelf for '<name>'. Run \`hubenv
    create ... --name <name>\` first.` → exit **1**.
  - **≥ 1 match** → `[(pantry1, shelf1), …]`.
    - **> 1 match** → multi-match refusal (stderr):
      ```
      ERROR: 'demo' found in multiple pantries:
      INFO:   <shelf path 1>
      INFO:   <shelf path 2>
      INFO: Use --pantry to select a specific one.
      ```
      → exit **1**.
    - **exactly 1 match** → proceed.

### 4.3 Step 3 — Dry-run

If `--dry-run` (and a shelf was found) → print
`Dry-run: would restore '<name>' from <shelf path>` → exit **0**.
No restore is performed, no exports are printed.

### 4.4 Step 4 — Delegate to restore

`cmd_env_restore(EnsureArgs(NAME, pantry, display_name))` is called — the
full restore pipeline (see [`hubenv-env-restore.md`](hubenv-env-restore.md)
§4):

- can missing → clear "spec-only" error
  (`Environment '<name>' has a shelf spec at … but no archive (can) at ….
   Run: hubenv save <name>`), exit 1;
- idempotency: matching save/restore hashes →
  `Environment '<name>' already restored (idempotent skip). Use --force to
  re-unpack.` + exports, exit 0;
- unpack → record restore hash →
  `register_environment(name, display_name, {})` where `display_name =
  args.display_name or spec_display_name(shelf.spec) or name` → exports
  → exit 0.

`ensure` returns whatever `cmd_env_restore` returned.

---

## 5. Exit codes

| Condition | Code |
|---|---|
| Live env present (no-op skip) | 0 |
| Shelf found, `--dry-run` | 0 |
| Delegated restore succeeds (fresh unpack / idempotent skip / kernel register) | 0 |
| `--pantry` given, shelf not there | 1 |
| No shelf anywhere (no live env) | 1 |
| Multi-match (chain, >1 pantry) | 1 |
| Delegated restore fails (can missing / unpack error / register error) | 1 |

---

## 6. Side-effect summary by flag combination

| Combination | Live env | Shelves / can | Kernel | At-boot snippet |
|---|---|---|---|---|
| `ensure NAME` (live) | nothing | nothing | nothing | nothing |
| `ensure NAME` (archived, fresh) | unpacked (restore) | nothing (read) | registered | nothing (`at_boot` fixed to False) |
| `ensure NAME` (archived, idempotent) | nothing | nothing | nothing | nothing |
| `ensure NAME --dry-run` (archived) | nothing | nothing | nothing | nothing |
| `ensure NAME` (neither) | nothing | nothing | nothing | nothing |
| `ensure NAME --pantry` (missing) | nothing | nothing | nothing | nothing |

`ensure` never writes an at-boot snippet (the internal `EnsureArgs` always
sets `at_boot=False`, even though the flag exists on the parser for
`restore` only).

---

## 7. Edge cases

- **`--display-name` threads through** (RE-07 resolved) — it is honored by
  the delegated restore; the internal `EnsureArgs` namespace is the only
  carrier (restore's own `--display-name` is not a separate flag path).
- **Live env + shelf both present** → live wins; no restore, no kernel
  re-registration (the env is already available).
- **Shelf present, no can** → the *delegate's* spec-only error is the
  user-visible one (not a custom `ensure` message):
  `Environment '<name>' has a shelf spec at <path> but no archive (can) at
  <can path>.` + `Run: hubenv save <name>`.
- **`--dry-run` with no shelf** → the "no shelf" error fires *before*
  the dry-run check (lookup is step 2, dry-run is step 3); a `--dry-run`
  against a nonexistent env is exit 1 with the create suggestion.
- **`--dry-run` with live env** → the live no-op path (step 1) fires
  before the dry-run check; exports are printed.
- **Multi-match** is only possible without `--pantry` (with `--pantry` the
  lookup is exact, single or none).
- **Idempotency** — repeated `ensure` after a fresh restore hits the
  idempotent-skip branch (matching hashes) and exits 0 without re-unpacking.
- **At-boot use** — the snippet written by `restore --at-boot` calls
  `hubenv ensure <name> 2>/dev/null || true` — so ensure's exit code is
  *not* what the shell sees; the snippet swallows it.

---

## 8. Pantry interaction

- **Source scope** — `--pantry PATH` restricts the shelf lookup to that
  pantry (exact, no chain fallback).
- **Default** — the full `NBW_PANTRY` chain; multi-match → refuse
  (RE-12 resolved: `ensure` is on the `--pantry` offering list).
- **Read-only** — no pantry writes (restore does not write to the pantry;
  the can is read, the live env is written under `NBW_MM`).

---

## 9. Output (stdout) examples

### 9.1 Live no-op

```
$ hubenv ensure demo
Environment 'demo' is already live (idempotent skip).
export NBW_ACTIVE_ENV=demo
export NBW_ENV_ROOT=/home/u/.nbw-live/mm/envs/demo
```

### 9.2 Archival restore (fresh unpack)

```
$ hubenv ensure demo
export NBW_ACTIVE_ENV=demo
export NBW_ENV_ROOT=/home/u/.nbw-live/mm/envs/demo
```

(stderr: restore's unpack/register logs; stdout is only the exports.)

### 9.3 Archival restore (idempotent skip)

```
$ hubenv ensure demo
Environment 'demo' already restored (idempotent skip). Use --force to re-unpack.
export NBW_ACTIVE_ENV=demo
export NBW_ENV_ROOT=/home/u/.nbw-live/mm/envs/demo
```

### 9.4 `--dry-run` (archived)

```
$ hubenv ensure ghost --dry-run
Dry-run: would restore 'ghost' from /home/u/pantry/shelves/ghost
```

### 9.5 No shelf, no live env

(stderr; stdout empty:)

```
ERROR: No live environment and no archive shelf for 'ghost'. Run `hubenv create ... --name ghost` first.
```

### 9.6 Multi-match (stderr; stdout empty)

```
ERROR: 'demo' found in multiple pantries:
INFO:   /home/u/pantry1/shelves/demo
INFO:   /home/u/pantry2/shelves/demo
INFO: Use --pantry to select a specific one.
```

### 9.7 Spec-only (can missing — via delegate)

(stderr; stdout empty:)

```
ERROR: Environment 'demo' has a shelf spec at /home/u/pantry/shelves/demo but no archive (can) at /home/u/pantry/shelves/demo/archives/env-demo.tar.
INFO: Run: hubenv save demo   to create the restoreable can.
```

---

## 10. What is NOT done (out of scope for the current implementation)

- No **`--at-boot`** flag — `ensure` is the *consumer* of at-boot snippets,
  not a producer; the internal `EnsureArgs` fixes `at_boot=False`.
- No **fresh creation** — if nothing is live or archived, `ensure` errors
  with a `create` suggestion; it does not itself seed/build.
- No **`--force`** flag — re-unpack forcing is `restore`'s domain (and
  `EnsureArgs.force` is always `False`).
- No **kernel re-registration on the live path** — step 1 is a pure no-op
  (the live env's kernel is assumed already registered).
- No **`--pantry` on the live path** — `--pantry` only affects the shelf
  lookup; a live env is always found regardless of pantry.

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§4.3 stdout contract, §4.5 pantry
  resolution, §4.7 idempotency, §5.1 `ensure` stub, §7 RE-07 / RE-12).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§3 global flags,
  §6–§7 store methods, §9 idempotency contract (ensure is the canonical
  "available or restore" entry point), §10 output discipline, §11 exit codes).
- [`hubenv-env-restore.md`](hubenv-env-restore.md) — the pipeline
  `ensure` delegates to (unpack, idempotency hashes, kernel register, at-boot
  snippet).
- [`hubenv-kernel-and-shell.md`](hubenv-kernel-and-shell.md) — `register`/
  `unregister` (the kernel side of the same `env_ensure.py` module).
