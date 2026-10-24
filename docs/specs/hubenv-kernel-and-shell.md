# `hubenv register` / `unregister` / `activate` / `deactivate` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/env_ensure.py` (`cmd_env_register`,
> `cmd_env_unregister`), `nb_wrangler/hubenv/env_activate.py`
> (`cmd_env_activate`, `cmd_env_deactivate`), `nb_wrangler/activation.py`,
> `nb_wrangler/hubenv/_common.py` (`var_export_lines`, `print_exports`), and
> `nb_wrangler/environment.py`.
>
> Verified against `tests/hubenv/test_e2e.py`.

---

## 1. Purpose

The kernel & shell group is the "make a live env usable from Jupyter and
from a shell" surface:

- **`register NAME`** / **`unregister NAME`** manage the **Jupyter kernel
  spec** for a live environment (kernel name = env name; display name
  resolves CLI > recorded shelf spec > env name).
- **`activate NAME`** / **`deactivate`** emit a **pure-stdout shell snippet**
  that the user `eval`s or sources. The snippet activates the env **by
  absolute path** (so it works even under a foreign mamba/micromamba whose
  `MAMBA_ROOT_PREFIX` cannot see the nb-wrangler env dir) and exports the
  env's recorded `environment_vars`.

All four commands are **kernel- or snippet-bound** — none accepts `--pantry`
(RE-12 partial resolution: they are deliberately out of scope).

---

## 2. Command synopsis

```
hubenv register    NAME [--display-name NAME] [--dry-run]
hubenv unregister  NAME [--dry-run]
hubenv activate    NAME
hubenv deactivate
```

---

## 3. Arguments

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Environment name (kernel name = env name). |
| `--display-name` (`register`) | optional, `None` | Jupyter kernel **display** name. Resolution order:
  CLI `--display-name` > `spec_display_name` (recorded in the shelf spec's
  `image_spec_header.display_name`) > env name. |
| `--dry-run` | optional, `False` | Print one "would …" line; nothing executed (all four verbs). |
| global flags | — | `-q/--quiet`, `--verbose`, `--debug`, `--color`, `--log-times`,
  `--reset-log` (see [`hubenv-common.md`](hubenv-common.md) §3). |

`activate` and `deactivate` take **no command flags** other than globals
(`activate` requires exactly the name positional; `deactivate` takes none).

---

## 4. Execution paths

### 4.1 `register NAME`

1. **Display-name resolution** —
   ```
   display_name = args.display_name
   if display_name is None:
       matches = PantryStore().find_shelves(NAME)   # chain, no --pantry
       if matches:
           display_name = spec_display_name(NbwShelf(matches[0][1]).spec_path)
   display_name = display_name or NAME
   ```
   So a registered kernel *always* uses the same display name that
   `create` / `restore` recorded (the recorded `display_name` wins over the
   bare env name).
2. **`--dry-run`** →
   `Dry-run: would register kernel '<name>' as '<display_name>'` → exit **0**.
3. Else → `EnvironmentManager.register_environment(NAME, display_name, {})`:
   - success →
     ```
     Registered environment '<name>' as kernel '<display_name>'.
     export NBW_ACTIVE_ENV=<name>
     export NBW_ENV_ROOT=<live envs root>/<name>
     ```
     (the two `export` lines are `print_exports`) → exit **0**.
   - failure → exit **1** (the manager logs the underlying mamba/ipykernel
     failure).
4. Requires a live env + mamba/ipykernel in it; a missing env → `register_environment`
   fails → exit 1.

### 4.2 `unregister NAME`

1. **`--dry-run`** →
   `Dry-run: would unregister kernel '<name>'` → exit **0**.
2. Else → `EnvironmentManager.unregister_environment(NAME)` (best effort —
   no error if the kernelspec is absent).
   Always print
   `Unregistered Jupyter kernel '<name>' (if it existed).` → exit **0**
   (there is **no** failure signal when the kernel is absent).

### 4.3 `activate NAME`

1. **Live-env check** — `EnvironmentManager.environment_exists(NAME)`:
   missing →
   ```
   Environment '<name>' does not exist locally (looked under <NBW_MM>/envs).
   Restore it first with `hubenv ensure <name>`.
   ```
   (stderr) → exit **1**.
2. `env_path = em.env_live_path(NAME)` (absolute).
3. `extra_exports = var_export_lines(NAME, PantryStore())` — reads the shelf
   spec's `environment_vars` (via `load_hubenv_spec`, so the no-shelf spec
   falls back to an empty seed → `extra_exports == []`) and returns
   `export KEY=VALUE` lines **sorted by KEY**; returns `[]` on any spec
   load error.
4. Build the snippet
   ```python
   activation.emit_activation(str(em.nbw_mm_dir), em.mamba_cmd,
                              activation.detect_shell(), str(env_path),
                              name=NAME, extra_exports=extra_exports)
   ```
   and **write it to stdout** via `sys.stdout.write(snippet)` — the snippet
   is the *only* stdout. Exit **0**.

### 4.4 `deactivate`

1. `snippet = activation.emit_deactivate(em.mamba_cmd,
   activation.detect_shell())`.
2. `sys.stdout.write(snippet)` → exit **0**. No live-env check, no args.

---

## 5. The snippet format (`activation.py`)

`activation.emit_activation` / `emit_deactivate` are **pure** functions —
paths and commands are passed in explicitly, no logging, no import-time env
reads. The output is deterministic per (nbw_mm, mamba_cmd, shell, env_path,
name, extra_exports).

### 5.1 Shell detection (`activation.detect_shell`)

Priority order (over `os.environ` unless an `env` mapping is passed):

1. `NBW_SHELL` env var (value must be `bash`/`zsh`/`fish`);
2. `ZSH_VERSION` → `zsh`;
3. `BASH_VERSION` → `bash`;
4. `FISH_VERSION` → `fish`;
5. `basename($SHELL)` or `basename($0)` ∈ {`bash`, `zsh`, `fish`};
6. default `bash`.

### 5.2 `activate` snippet — bash / zsh (common)

```bash
export NBW_ACTIVE_ENV=<name>;
export NBW_ENV_ROOT=<env_path>;
export MAMBA_ROOT_PREFIX=<nbw_mm>;
eval "$(mamba shell hook 2>/dev/null)";
mamba activate <env_path>;
export <KEY>=<VALUE>;            # one per environment_vars entry, sorted
export <KEY>=<VALUE>;
```

Key points:

- `NBW_ACTIVE_ENV` / `NBW_ENV_ROOT` are set **before** the mamba hook so
  they survive `activate`.
- `MAMBA_ROOT_PREFIX` is pinned to the nb-wrangler root — this is what makes
  the snippet work under a **foreign** mamba/micromamba.
- The activation is **by absolute path** (`mamba activate <env_path>`), not
  by env name.
- Each `export` line ends with `; ` (bash/zsh); fish uses `set -gx`.
- `environment_vars` exports are appended **after** the activate line and
  are **byte-equivalent** to `hubenv var ls NAME --export`
  ([`hubenv-var.md`](hubenv-var.md) §9).

### 5.3 `activate` snippet — fish

```fish
set -gx NBW_ACTIVE_ENV <name>;
set -gx NBW_ENV_ROOT <env_path>;
set -gx MAMBA_ROOT_PREFIX <nbw_mm>;
eval "$(mamba shell hook)";
mamba activate <env_path>;
set -gx <KEY> <VALUE>;           # one per environment_vars entry, sorted
```

### 5.4 `deactivate` snippet — bash / zsh

```bash
eval "$(mamba shell hook 2>/dev/null);
mamba deactivate
```

### 5.5 `deactivate` snippet — fish

```fish
eval "$(mamba shell hook)";
mamba deactivate
```

---

## 6. Side-effect summary by flag combination

| Verb / combination | Jupyter kernel | Filesystem | stdout |
|---|---|---|---|
| `register NAME` | kernelspec written (user-level Jupyter dir) | kernelspec dir + files | one summary line + 2 exports |
| `register NAME --dry-run` | nothing | nothing | one "would register" line |
| `unregister NAME` | kernelspec removed (best effort) | kernelspec dir (if present) | one "Unregistered … (if it existed)." line |
| `unregister NAME --dry-run` | nothing | nothing | one "would unregister" line |
| `activate NAME` | nothing | nothing | **only** the shell snippet |
| `activate NAME` (live env missing) | nothing | nothing | (stdout empty) error on stderr |
| `deactivate` | nothing | nothing | **only** the shell snippet |

---

## 7. Edge cases

- **`register` on a missing env** → exit 1 (the manager's failure; no
  clean message beyond the manager log).
- **`register` display-name fallback** — without `--display-name`, a kernel
  registered by `register` uses the *recorded* display name from the shelf
  spec (not necessarily the env name). If the shelf spec has no `display_name`
  header, it falls back to the env name.
- **`unregister` is best effort** — no exit-1 path; the "(if it existed)"
  suffix is literal and always printed.
- **`activate` is pure** — it never mutates the shell or the filesystem;
  the caller must `eval`/source. If the live env is missing, it points at
  `hubenv ensure` (the canonical restore path).
- **`activate` with no shelf spec** — `var_export_lines` returns `[]`
  (the spec fallback seed has no `environment_vars`), so the snippet is
  still emitted (just without `environment_vars` exports).
- **`deactivate` never fails** — no live-env check, no kernel check; always
  exit 0.
- **`--pantry` is not offered** on any of the four (RE-12 partial:
  `register`, `unregister`, `activate`, `deactivate` are deliberately out of
  scope — they are kernel- or `data_manager`-bound).
- **`activate`'s env-var exports are sorted** and use the exact `export
  KEY=VALUE` format that `var ls --export` produces — the two are
  byte-equivalent for the same env.

---

## 8. Pantry interaction

- **No `--pantry`** on any of the four commands (RE-12 partial — deliberately
  out of scope; they are kernel- or snippet-bound).
- **Read-only** — `register` reads the shelf spec's `display_name` via the
  default `NBW_PANTRY` chain (`find_shelves`). No writes to the pantry.
- **Write** (only `register`) — the Jupyter user-level kernel dir
  (`~/.local/share/jupyter/kernels/`), which is outside the pantry tree.

---

## 9. Output (stdout) examples

### 9.1 `register` (success)

```
$ hubenv register demo
Registered environment 'demo' as kernel 'My Demo'.
export NBW_ACTIVE_ENV=demo
export NBW_ENV_ROOT=/home/u/.nbw-live/mm/envs/demo
```

### 9.2 `register --dry-run`

```
$ hubenv register demo --dry-run
Dry-run: would register kernel 'demo' as 'demo'
```

### 9.3 `unregister` (kernel absent or present)

```
$ hubenv unregister demo
Unregistered Jupyter kernel 'demo' (if it existed).
```

### 9.4 `unregister --dry-run`

```
$ hubenv unregister demo --dry-run
Dry-run: would unregister kernel 'demo'
```

### 9.5 `activate` (bash, with two environment_vars)

```
$ hubenv activate demo
export NBW_ACTIVE_ENV=demo;
export NBW_ENV_ROOT=/home/u/.nbw-live/mm/envs/demo;
export MAMBA_ROOT_PREFIX=/home/u/.nbw-live/mm;
eval "$(mamba shell hook 2>/dev/null)";
mamba activate /home/u/.nbw-live/mm/envs/demo;
export DEBUG=1;
export PATH=/opt/demo/bin;
```

(used as `eval "$(hubenv activate demo)"`.)

### 9.6 `deactivate` (bash)

```
$ hubenv deactivate
eval "$(mamba shell hook 2>/dev/null);
mamba deactivate
```

### 9.7 `activate` (live env missing — stderr; stdout empty)

```
ERROR: Environment 'ghost' does not exist locally (looked under /home/u/.nbw-live/mm/envs). Restore it first with `hubenv ensure ghost`.
```

---

## 10. What is NOT done (out of scope for the current implementation)

- No **`--pantry`** on any of the four (RE-12 partial — deliberately out of
  scope).
- No **kernel re-registration on `unregister`** (obviously).
- No **`activate` dry-run** (no `--dry-run` on `activate`/`deactivate`;
  they are pure emitters).
- No **`activate` with a different mamba** — the snippet uses the *current*
  `NBW_MAMBA_CMD` (the one that built the env); there is no `--mamba`
  override.
- No **fish `deactivate`** difference from bash/zsh beyond the syntax (the
  hook line omits the `2>/dev/null` guard in fish).
- No **`register` on a non-live env** — `register_environment` fails when the
  env dir is missing (no clean message).

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§4.3 stdout contract, §4.4 exit
  codes, §4.5 pantry resolution, §4.6 kernel conventions, §4.7 idempotency,
  §5.3 Kernel & shell stubs, §7 RE-12 / RE-07).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§3 global flags,
  §6–§7 store methods, §8 implicit spec model (`spec_display_name`), §10
  output discipline, §11 exit codes).
- [`hubenv-env-ensure.md`](hubenv-env-ensure.md) — the command that calls
  `register` transitively (via `restore`) and is the canonical "available"
  entry point that `activate` points at.
- [`hubenv-var.md`](hubenv-var.md) — the `environment_vars` that `activate`
  exports (byte-equivalent `export` lines).
- [`hubenv-env-restore.md`](hubenv-env-restore.md) — the command that writes
  the at-boot snippet that `ensure` consumes.
