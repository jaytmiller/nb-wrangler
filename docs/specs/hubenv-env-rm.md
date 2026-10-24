# `hubenv rm` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/env_rm.py`, `nb_wrangler/environment.py`, and
> `nb_wrangler/hubenv/env_restore.py` (at-boot snippet removal).
>
> Verified against `tests/hubenv/test_rm.py`.

---

## 1. Purpose

`hubenv rm` deletes environments from the **live** environment root
(`$NBW_MM/envs/`), the **archive** shelves (`<pantry>/shelves/`), or both.
It is the only hubenv command that is **interactive** (a `Proceed? (y/N)`
prompt), and the only one that deletes the at-boot snippet written by
`restore --at-boot`.

The command is a **5-step pipeline**: resolve → dry-run → validate →
confirm → execute. Each stage is independent and the failure at any stage is
a clean exit-1 error (no partial deletion past the confirm step).

---

## 2. Command synopsis

```
hubenv rm NAME… [--live | --archived | --both] [--pantry PATH] [-y/--yes] [--dry-run]
```

---

## 3. Arguments

| Argument | Required / Default | Description |
|---|---|---|
| `NAME…` | required, positional, one or more | Exact names or **glob patterns** (e.g. `team-*`); matched with
  `fnmatch` against live env names and shelf names. |
| `--live` | optional, part of a mutually-exclusive group | Delete only live environments. |
| `--archived` | optional, part of the group | Delete only archive shelves. |
| `--both` | optional, **default** | Delete from both live and archive. |
| `--pantry PATH` | optional, `None` | Restrict shelf search to a single pantry directory. |
| `-y`, `--yes` | optional, `False` | Skip the `Proceed? (y/N)` confirmation prompt (for scripts). |
| `--dry-run` | optional, `False` | Print the deletion plan only; nothing is executed. |
| global flags | — | `-q/--quiet`, `--verbose`, `--debug`, `--color`, `--log-times`,
  `--reset-log` (see [`hubenv-common.md`](hubenv-common.md) §3). |

---

## 4. Execution paths

### 4.1 Step 1 — Resolve

`target = args.target or "both"`; targets are collected per target type:

- **live** (if `target` ∈ `live`/`both`): every live env whose name
  `fnmatch(name, pattern)` for some pattern; each target is
  `{"type": "live", "name", "path", "writable": True}`.
- **archived** (if `target` ∈ `archived`/`both`): every shelf in the pantry
  chain (or the single `--pantry` pantry) whose name matches; each target is
  `{"type": "shelf", "name", "path", "pantry", "writable"}`.

If the resolved target list is empty → `No matching environments found.`
(stderr) → exit **1**.

### 4.2 Step 2 — Dry-run (if `--dry-run`)

Print the plan (stdout, see §9) → exit **0**. No further steps.

### 4.3 Step 3 — Validate

Two independent guards (both are exit-1, nothing is deleted):

1. **Read-only guard** — any shelf target whose pantry is not writable:
   `cannot delete '<name>' from read-only pantry: <pantry>` plus
   `Set NBW_PANTRY to a writable path or use --pantry <writable-path>.`
   → exit **1**.
2. **Path-escape guard** (`is_safe_rm_path`) — every target's resolved path
   must lie under a safe root:
   - live → `$NBW_MM/envs` (resolved);
   - shelf → some `<pantry>/shelves` (resolved, over the chain).
   A target outside all safe roots →
   `Refusing to delete path outside safe roots: <path>` → exit **1**.

### 4.4 Step 4 — Confirm

Print the plan (stdout). If not `-y`:

- Prompt `Proceed? (y/N): ` — written to **stderr** (RE-13 resolved —
  stdout stays machine-readable);
- read stdin: `y` / `yes` (case-insensitive, stripped) → proceed;
  anything else, including **EOF** (piped input / closed stdin) →
  `Aborted.` (stderr) → exit **1**.

### 4.5 Step 5 — Execute

Per target, in order:

- **Already gone** (`path.exists()` false) → print `Already gone: <type>
  '<name>'` (stdout) and **continue** (not an error; RE-14 / §4.7 idempotency).
- **live** → `EnvironmentManager.unregister_environment(name)` (kernel) then
  `delete_environment(name)`. Success → `Removed live '<name>' at <path>`.
  Failure → warning `Could not remove '<name>'` and the failure counter
  increments.
- **shelf** → `shutil.rmtree(path)`. Success →
  `Removed shelf '<name>' at <path>` + **remove the at-boot snippet**
  (`~/.hubenv/env-<name>.sh`, via `remove_at_boot_snippet`, logs
  `Removed at-boot snippet <path> (if present).` to stderr/info).
- Any `OSError` → warning `Could not remove '<name>': <e>` and the failure
  counter increments.

**Cleanup**: after all targets, for each pantry whose `shelves/` dir is now
empty, best-effort `shutil.rmtree` (silently ignored on failure).

Return value: 0 if the failure counter is 0, else 1 (partial failure).

---

## 5. Exit codes

| Condition | Code |
|---|---|
| `--dry-run` | 0 |
| No matching targets | 1 |
| Read-only pantry / unsafe path (validation) | 1 |
| Confirmation aborted (prompt or EOF) | 1 |
| All targets removed (or already gone) | 0 |
| One or more targets failed to remove | 1 (partial) |

---

## 6. Side-effect summary by flag combination

| Combination | Live envs | Shelves | Kernel | At-boot snippet |
|---|---|---|---|---|
| `rm NAME --both -y` (default) | `unregister_environment` + `delete_environment` per match | `shutil.rmtree` per match | unregistered (via `delete`) | removed if present |
| `rm NAME --live` | as above | nothing | unregistered | nothing (snippet not removed) |
| `rm NAME --archived` | nothing | `shutil.rmtree` per match | nothing | removed if present |
| `… --dry-run` | nothing | nothing | nothing | nothing |
| `…` (no `-y`, prompt) | as above (after `y`) | as above | as above | as above |
| `…` (prompt, anything else / EOF) | nothing | nothing | nothing | nothing |

---

## 7. Edge cases

- **Glob matching** is `fnmatch` semantics (`*`, `?`, `[seq]`), not shell
  glob — patterns are per-name, not path wildcards. `team-*` matches `team-a`,
  `team-b`, etc.
- **Read-only pantries** are refused even with `-y` (validation is
  independent of the prompt).
- **Path-escape guard** is a hard refusal — a shelf "path" that somehow
  resolves outside any `<pantry>/shelves` or `$NBW_MM/envs` is never deleted.
- **Already-gone targets** are reported on stdout and do **not** count as
  failures; `rm` is thus safe to re-run (idempotent at the result level).
- **Partial failure** (e.g. one live env is locked, another is gone) → exit
  1, but the successfully-removed targets are reported and the empty-shelf
  cleanup still runs.
- **Confirmation prompt on stderr** (RE-13 resolved) — stdout after a
  successful run is *only* the plan + `Removed …` / `Already gone:` lines,
  so `hubenv rm … -y | cat` is a clean pipeline.
- **Kernel unregistration** for live targets is best-effort: `unregister_environment`
  logs its own result; even if it fails, the env dir is still deleted.
- **`--pantry` scoping** (RE-12 resolved) — with `--pantry PATH`, only that
  pantry's shelves are considered as targets; live targets are unaffected.

---

## 8. Pantry interaction

- **Read** — default chain for shelf resolution; `--pantry PATH` restricts to
  one pantry (source scope for the archive targets).
- **Write** — the command *writes* only in the sense of deleting: shelf dirs
  and their contents are removed from the (potentially single) pantry.
- **No `--pantry` fallback** — if a target shelf is not in the given pantry,
  it is not found (and if nothing matches, exit 1 with the no-match message).

---

## 9. Output (stdout) examples

### 9.1 Plan + success (`rm demo1 demo2 -y`)

```
The following will be removed:
  [live]   demo1            -> /home/u/.nbw-live/mm/envs/demo1
  [live]   demo2            -> /home/u/.nbw-live/mm/envs/demo2
Removed live 'demo1' at /home/u/.nbw-live/mm/envs/demo1
Removed live 'demo2' at /home/u/.nbw-live/mm/envs/demo2
```

(stderr for the at-boot snippet, if any was present:)

```
INFO: Removed at-boot snippet /home/u/.hubenv/env-demo1.sh (if present).
```

### 9.2 Already-gone (stdout; no error)

```
The following will be removed:
  [live]   ghost            -> /home/u/.nbw-live/mm/envs/ghost
Already gone: live 'ghost'
```
(exit 0.)

### 9.3 Interactive prompt (stdout = plan; **stderr** = prompt)

```
The following will be removed:
  [shelf]  demo1            -> /home/u/pantry/shelves/demo1  (/home/u/pantry)

stderr: Proceed? (y/N): 
```

### 9.4 No match

(stderr; stdout empty:)

```
ERROR: No matching environments found.
```

### 9.5 Read-only refusal

(stderr; stdout empty:)

```
ERROR: cannot delete 'prod' from read-only pantry: /home/u/pantries/remote
ERROR: Set NBW_PANTRY to a writable path or use --pantry <writable-path>.
```

### 9.6 Dry-run

```
The following will be removed:
  [live]   demo             -> /home/u/.nbw-live/mm/envs/demo
  [shelf]  demo             -> /home/u/pantry/shelves/demo  (/home/u/pantry)
```
(exit 0; nothing deleted.)

---

## 10. What is NOT done (out of scope for the current implementation)

- No **backup** of deleted envs / shelves — deletion is permanent (no trash
  dir, no archive of the deleted can).
- No **recursive sub-shell** confirmation — the prompt is a single `y`/`yes`
  for the whole plan; there is no per-item confirmation.
- No **`--dry-run` confirmation** — `--dry-run` short-circuits before
  validation and confirm (the plan is printed for whatever would match).
- No **partial-mode flag** for "only delete live if no archived" — the
  `--live`/`--archived`/`--both` choice is per-invocation, not per-target.
- No **`--pantry` on live targets** (live targets ignore pantry; `--pantry`
  only scopes archive targets).

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§4.3 stdout contract, §4.4 exit
  codes, §4.5 pantry resolution, §4.7 idempotency, §5.2 `rm` stub,
  §7 RE-13 / RE-12).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§3 global flags,
  §6–§7 store methods, §9 idempotency (already-gone), §10 output discipline
  (prompt on stderr, RE-13), §11 exit codes).
- [`hubenv-env-restore.md`](hubenv-env-restore.md) — the command whose at-boot
  snippet `rm` removes.
- [`hubenv-env-ensure.md`](hubenv-env-ensure.md) — the command that can
  recreate what `rm` deletes.
