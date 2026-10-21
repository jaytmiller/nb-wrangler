# `hubenv` — Top-Level Behavior Specification

> Reverse-engineered, *top-level* spec. Derived from the current implementation
> in `nb_wrangler/hubenv/` (25 modules, ~3.6 kloc), grounded in
> `nb_wrangler/pantry.py`, `nb_wrangler/environment.py`,
> `nb_wrangler/data_manager.py`, and `nb_wrangler/constants.py`.
>
> **This document is an inventory and contract seed, not a per-command spec.**
> Its purpose is to define stable feature boundaries, shared cross-cutting
> invariants, and a decomposition contract so that each feature can be
> expanded into a detailed spec of the form of
> [`hubenv-env-create.md`](hubenv-env-create.md) (already written).
>
> Verified against `tests/hubenv/` (`test_create.py`, `test_save.py`,
> `test_restore.py`, `test_ls_info.py`, `test_rm.py`,
> `test_ensure_register.py`, `test_install_relock.py`, `test_var.py`,
> `test_data.py`, `test_export_status_doctor.py`, `test_dry_run.py`,
> `test_e2e.py`, `test_config.py`).

---

## 1. Purpose

`hubenv` is the Persistent Platform Environments (PPE) CLI for nb-wrangler.
It lets a user install Python environments and register them as Jupyter
kernels **independently of notebook repositories and wrangler specs**, and
keep those environments portable across machines by packing them into
pantry archives ("cans") that can later be restored.

Design intent (verified in `cli.py` / `parser.py`):

- `hubenv` is a **subcommand-based** CLI, deliberately distinct from the
  flag-based `nbw` CLI (same engine underneath: `NbwPantrySet`,
  `EnvironmentManager`, `data_manager`, the shared logger).
- Environments are the primary resource, so the env verbs are **flattened to
  the top level** (`hubenv create`, not `hubenv env create`).
- `var` and `data` remain subcommand groups; `export`, `status`, `doctor`,
  `completions` are top-level utilities.
- `hubenv` never performs notebook curation, Docker builds, or git cloning —
  that is `nbw`'s territory. `hubenv` operates on the *environment* and
  its *state on disk*.

The public command surface (23 commands), confirmed against `parser.py`:

| Area | Commands |
|---|---|
| Env lifecycle | `create`, `save`, `restore`, `ensure` |
| Env mutation | `install`, `uninstall`, `relock`, `rm` |
| Kernel & shell | `register`, `unregister`, `activate`, `deactivate` |
| Inspection | `ls`, `info`, `status`, `doctor` |
| Spec & vars | `export`, `var ls`, `var add`, `var rm` |
| Data | `data ls`, `data download`, `data unpack`, `data pack`, `data clean` |
| Tooling | `completions <shell>`, `--version`, (no command) → help |

---

## 2. Core Concepts

Five objects form the domain model. Every command's behavior can be
described in terms of which of these it reads or writes.

| Object | Definition | On disk |
|---|---|---|
| **Live env** | A real mamba environment under the nb-wrangler envs root, the thing you `activate` and run notebooks in. | `$NBW_MM/envs/<name>` (default `~/.nbw-live/mm/envs/<name>`) |
| **Shelf** | The pantry-side record of an environment: a directory holding the spec, archive, and hashes. | `<pantry>/shelves/<name>/` |
| **Spec (implicit)** | The shelf's `nbw-wrangler-spec.yaml` — a *full valid wrangler spec* on disk, interacted with by hubenv as a *mamba-spec view* (`name`/`channels`/`dependencies`/`environment_vars`). | `<shelf>/nbw-wrangler-spec.yaml` |
| **Can** | A packed archive of a live env, the unit of restore-ability. A shelf is **restorable only once a can exists** (i.e. after `hubenv save`). | `<shelf>/archives/<name>.tar` |
| **Kernel** | A Jupyter kernelspec making the env visible to JupyterLab. | `~/.local/share/jupyter/kernels/<name>/` |

### 2.1 Environment state matrix

`status` (`status.py:_state_for`) defines the canonical self-describing
states; every listing command must be consistent with these:

| live? | shelf? | can? | State string |
|---|---|---|---|
| ✅ | ✅ | ✅ | `live+archived` |
| ✅ | ✅ | ❌ | `live+spec-only` |
| ✅ | ❌ | ❌ | `live` |
| ❌ | ✅ | ✅ | `archived` |
| ❌ | ✅ | ❌ | `spec-only` |

Key invariant: **a shelf directory alone is not "archived"**.
`PantryStore.has_can(name)` is the single source of truth for
"restorable" (see `status.py:build_status_envs`).

### 2.2 Pantries & shadowing

A *pantry* is a directory containing `shelves/`. Multiple pantries form a
search chain (`NBW_PANTRY` is colon-separated, like `PATH`; see §4.4). When
the same name exists in several pantries the later ones **shadow** the
earlier; `ls`/`info` emit a shadowing warning
(`_common.py:print_shadowing_warnings`), and `restore`/`ensure` refuse to
guess — the user must pass `--pantry`.

---

## 3. Runtime configuration & storage layout

### 3.1 Environment variables (from `constants.py`)

| Variable | Default | Meaning |
|---|---|---|
| `NBW_ROOT` | `~/.nbw-live` | Live-state root; must not inherit `MAMBA_ROOT_PREFIX`/`CONDA_ROOT_PREFIX` |
| `NBW_MM` | `$NBW_ROOT/mm` | Mamba root under `NBW_ROOT` |
| — | `$NBW_MM/envs` | **Live envs root** (live envs live here) |
| `NBW_PANTRY` | `~/.nbw-pantry` | Pantry search chain; **colon-separated**, like `PATH` |
| `NBW_CACHE` | `$NBW_ROOT/cache` | Cache dir |
| `NBW_MAMBA_CMD` | `$NBW_MM/bin/micromamba` (or `$MAMBA_EXE`) | Mamba executable used for env ops |
| `NBW_PIP_CMD` | (built-in default) | Pip executable used for `--using` default installs |
| `NBW_ACTIVE_ENV` | *(unset)* | Convention var naming the active PPE; `activate`/`doctor`/`status` consume it |
| `NBW_ENV_ROOT` | *(unset)* | Printed by `print_exports` as `<live_envs_root>/<name>`; the counterpart convention var |

### 3.2 Directory layout (defaults)

```
~/.nbw-live/                          # NBW_ROOT
├── mm/envs/<name>/                   # LIVE ENVS (created by mamba)
└── cache/
~/.nbw-pantry/                        # NBW_PANTRY (chain element)
├── shelves/
│   └── <name>/                       # SHELF
│       ├── nbw-wrangler-spec.yaml    # SHELF SPEC (full wrangler spec on disk)
│       └── archives/
│           ├── <name>.tar            # CAN
│           ├── data-*                # DATA ARCHIVES (hubenv data *)
│           └── last-save.sha256      # SAVE HASH
# restore hash (per env, under the live store — see env_restore.py)
~/.hubenv/env-<name>.sh               # at-boot snippet (only on restore --at-boot)
~/.local/share/jupyter/kernels/<name>/# KERNELSPEC
```

### 3.3 The store: `PantryStore`

`hubenv/config.py` defines `PantryStore`, a **thin subclass of
`NbwPantrySet`** (shared with `nbw`) that anchors `NBW_PANTRY_DIRS` /
`NBW_ROOT` to the `hubenv.config` namespace (so test patches keep working).
All pantry logic — search, writability, shelf lookups, pack/unpack,
`has_can`, restore hashes, shelf-spec paths — is inherited; zero logic is
duplicated in hubenv. `HubenvConfig` is a back-compat alias.

---

## 4. Global conventions (cross-cutting invariants)

These invariants apply to **every** command and are binding constraints on
any future implementation or refactor. A detailed spec may *refine* them for
one command but never contradict them.

### 4.1 Entry point & dispatch (`cli.py`)

- `hubenv` console script → `nb_wrangler.hubenv.cli:main(argv)`.
- `main` wraps dispatch in `try/except`:
  - `HubenvError` → log `exc.message` to stderr, return `exc.exit_code`.
  - `KeyboardInterrupt` → log "Interrupted." (INFO), return **130**.
  - **Any other exception propagates** (traceback + exit 1).
- Parsing uses strict `argparse` (`parse_args`) — unknown flags and
  positionals are rejected as argparse usage errors (exit **2**).
- `--version` prints `nb_wrangler.constants.__version__` and exits **0**.
- No command → `parser.print_help()`, exit **0**.
- Dispatch is dict-based: env verbs in `_ENV_DISPATCH`, `var.*` in
  `_dispatch_var`, `data.*` in `_dispatch_data`, utilities in `_main`.
  A non-empty sub-parser that receives no sub-command logs an error and
  returns **1**.
- The legacy `"not yet implemented"` path (`_cmd_not_implemented`, exit
  **2**) is reachable only for names that are not in any dispatch table;
  with the current parser it is not reachable for user input.
- `_setup_config` builds a `WranglerConfig` (logging + `hubenv_command`
  path such as `var.ls`) and installs it as the singleton; **no command
  consumes `hubenv_command` today** — it is reserved for logging/telemetry.

### 4.2 Global flags (registered on top level *and* each command)

| Flag | Effect |
|---|---|
| `-q`, `--quiet` | Suppress all log output to stderr; only stdout visible |
| `--verbose` | Verbose log output |
| `--debug` | Drop into pdb on exceptions |
| `--color` | Colorize log output (`auto`/`always`/`never` per `VALID_COLOR_MODES`) |
| `--log-times` | Timestamps in log messages |
| `--reset-log` | Delete the nb-wrangler log file |

Registered on both sides of the command boundary
(`hubenv --quiet create` and `hubenv create --quiet` both parse); on the
sub-command side the defaults are `argparse.SUPPRESS` so they do not clobber
a top-level value.

### 4.3 Output discipline (stdout vs stderr)

**stdout is reserved for machine-readable / eval-able output** —
`export …` lines, tables, JSON, YAML specs, shell snippets. **Diagnostics
go to the logger on stderr.** A command's stdout must be safely consumable
via `$(…)` or `eval "$(…)"`.

Known stdout contents per command (what a script may parse):

| Command | stdout contract |
|---|---|
| `create` | eval-able `export NBW_ACTIVE_ENV=…` + `export NBW_ENV_ROOT=…`; or the seeded YAML under `--dry-run`; or the "Not archived yet…" hint |
| `save` | one `Saved environment '<name>' to <path>` line |
| `restore` | eval-able exports; one "already restored (idempotent skip)" line when skipped; at-boot lines |
| `ensure` | "already live (idempotent skip)" + exports, or restore's output |
| `register` | one line + exports |
| `activate` / `deactivate` | **only** the shell snippet (pure stdout) |
| `ls` / `info` | table or JSON (`--format`) |
| `status` / `doctor` | table or JSON (`--format`) |
| `export` | spec YAML / requirements text, or one "Exported spec …" line |
| `var ls` | table, `export …` lines (`--export`), or JSON |
| `var add` / `var rm` | one `Set …`/`Removed …` line per var + "Kernel refreshed…" |
| `data ls` | table or JSON |
| `data download/unpack/pack/clean` | one status line |
| `completions <shell>` | **only** the completion script |
| `install` / `uninstall` | installer output path + "Spec updated. Run `hubenv relock …`" suggestion (unless `--no-relock`) |

### 4.4 Exit code contract

| Code | Meaning |
|---|---|
| `0` | Success (including documented idempotent skips) |
| `1` | Any handled failure (not found, no writable pantry, refused delete, subprocess failure, validation failure) |
| `2` | argparse usage errors (unknown flag/sub-command — parsing is strict, §4.1); the "Not implemented" dispatch path (unreachable via the current parser) |
| `130` | Interrupted (Ctrl-C / `KeyboardInterrupt`) |

Handlers signal results by **returning int** and logging errors to stderr.
`cmd_env_create` is the one handler that *raises* `HubenvError`; `main()` catches it,
logs its message to stderr, and returns its `exit_code`.

### 4.5 Pantry resolution rules

- `--pantry PATH` (where offered) restricts to a single pantry; if the
  shelf is not there, the command fails with a clear message (it does not
  fall back to the chain).
- Offered by: `create`, `save`, `restore`, `ls`, `info`, `rm`, `ensure`,
  `export`, `var ls`, `var add`, `var rm` — the
  spec consumers resolve the store via `_common.store_for(args)`.
  `status`, `doctor`, `data *`, `register`, `unregister`, `activate`, and
  `deactivate` intentionally do **not** accept `--pantry` (they are
  kernel- or `data_manager`-bound, which take no pantry parameter).
- Otherwise the `NBW_PANTRY` chain is searched; for **writes** the first
  *writable* pantry wins; if none is writable the command fails (exit 1)
  with `print_no_writable_pantry` guidance.
- For multi-match reads, behavior is command-specific: `ls`/`info` collapse
  to the first and warn (or `--all` to expand); `restore`/`ensure` refuse
  and demand `--pantry`.

### 4.6 Kernel conventions

- Kernel name = env name; display name = `--display-name` or env name.
- Registered via `EnvironmentManager.register_environment`
  (`mamba run -n <name> python -m ipykernel install --user …`).
- `var add`/`var rm` **re-register** the kernel so its env vars refresh; a
  failed re-registration is a warning, never a rollback (the spec is the
  source of truth).

### 4.7 Idempotency conventions

- **Save hash**: `hubenv save` writes `<shelf>/archives/last-save.sha256`
  (sha256 of the can).
- **Restore hash**: `hubenv restore` records the save hash it unpacked
  (under the live store, `PantryStore.restore_hash_path(name)`); a later
  `restore` with matching hashes is an **idempotent skip** (exit 0) unless
  `--force`.
- **Ensure**: live env present → no-op skip; else restore; else error +
  `hubenv create` suggestion.
- **rm**: already-gone targets are reported "Already gone", not errors.

### 4.8 Spec model (mamba view ↔ wrangler spec)

Interactions with the shelf spec go through `env_spec.py`:

- **On disk** the shard spec is *always* a full valid wrangler spec
  (`mamba_to_wrangler` scaffolds `image_spec_header`, `repositories`,
  `system`, `extra_mamba_packages`/`extra_pip_packages`).
- **In memory / CLI** hubenv speaks the *mamba view*
  (`name`/`channels`/`dependencies`/`environment_vars`);
  `wrangler_to_mamba` converts on load.
- Load when the shelf spec is missing falls back to `seed_from_empty(name, None)`
  (deps `["pip"]`) so first-mutation commands have a well-typed seed.
- `save_hubenv_spec` coerces via `_coerce_to_wrangler` and writes with
  `mkdir(parents=True, exist_ok=True)` — **overwrites unconditionally**
  (no confirmation, no backup).

---

## 5. Feature areas

Each area below is the decomposition unit for detailed specs. Per-command
stubs give the one-line purpose, argument surface, behavior summary, and
known rough edges. Every stub names its detailed-spec target
(`docs/specs/hubenv-<feature>.md`).

> **Ground truth per command:** argument surface = `parser.py`;
> dispatch = `cli.py`; behavior = the named module; storage = `pantry.py` /
> `constants.py`; acceptance = `tests/hubenv/`.

### 5.1 Environment lifecycle

#### `hubenv create` — *already specced*

> **Detailed spec: [`hubenv-env-create.md`](hubenv-env-create.md).**

Purpose: seed a mamba-spec dict from one of five sources and bring the env
into the PPE lifecycle (build live env, persist shelf spec, register
kernel); `--save` additionally packs the can.

Key arguments: one of `--from-empty | --from-requirements FILE… |
--from-mamba-spec FILE | --from-wrangler-spec FILE |
--from-existing-env ENV_NAME` (mutually exclusive, exactly one),
`--name` (required only for `--from-empty` / `--from-requirements`; derived
otherwise: mamba spec `name` or file stem, wrangler spec `kernel_name` or
`image_name` or file stem, imported env name for `--from-existing-env`),
`--display-name`, `--python`, `--pantry`,
`--ephemeral`, `--save`, `--dry-run`.

#### `hubenv save NAME`

Purpose: pack a live env into a pantry can and record the save hash.

Synopsis: `hubenv save NAME [--pantry PATH] [--dry-run] [--force]`

Behavior (`env_save.py`):
1. Resolve a writable target pantry (`--pantry` first writable default) —
   none → exit 1 (`print_no_writable_pantry`).
2. Verify live env exists at `$NBW_MM/envs/<name>` — missing → exit 1.
3. `--dry-run` → print `shelf:` / `can:` / `live env:` lines, exit 0.
4. Existing can without `--force` → exit 1.
5. `NbwShelf.pack_environment(name, name, ".tar")`; failure → exit 1.
6. Persist `last-save.sha256`; print `Saved environment '<name>' to <path>`.

Shared by `create --save` (`_save_after_create` wraps the same `_do_save`).

Detailed spec target: `docs/specs/hubenv-env-save.md`.

#### `hubenv restore NAME`

Purpose: unpack a saved can into a live env and (re)register the kernel.

Synopsis: `hubenv restore NAME [--pantry PATH] [--force] [--at-boot]`

Behavior (`env_restore.py`):
1. Find the shelf (`--pantry` exact, or chain search; multi-match → refuse,
   hint `--pantry`).
2. Can missing → **clear "spec-only" error**: "Run `hubenv save NAME`"
   (exit 1). This is the canonical message for the spec-only state.
3. Idempotency: `--force` skips the check; matching save/hash →
   "already restored (idempotent skip)" + exports, exit 0.
4. `NbwShelf.unpack_environment(...)`; success → record restore hash.
5. `register_environment(name, display_name, {})` — `display_name` is
   `--display-name` or falls back to `NAME`.
6. Print exports; `--at-boot` → see below.

`--at-boot` (`write_at_boot_snippet`): writes a guarded snippet to
`~/.hubenv/env-<name>.sh` (setting `NBW_ACTIVE_ENV` and running
`hubenv ensure <name> 2>/dev/null || true`) and prints the `source`
instruction for the user to add to their shell startup (no automatic 
`~/.bashrc` edit; `hubenv rm` removes the snippet via `remove_at_boot_snippet`).

Detailed spec target: `docs/specs/hubenv-env-restore.md`.

#### `hubenv ensure NAME`

Purpose: idempotently ensure an env is available — live → no-op; archived
→ restore (delegates to `cmd_env_restore`); else error with a
`hubenv create` suggestion (exit 1).

Synopsis: `hubenv ensure NAME [--pantry PATH] [--display-name NAME] [--dry-run]`

Behavior (`env_ensure.py`):
1. `EnvironmentManager.environment_exists` → "already live (idempotent
   skip)" + exports, exit 0.
2. Shelf found → `--dry-run` prints one "would restore" line; else
   `cmd_env_restore` (which does unpacking + kernel registration).
3. No shelf → exit 1 with `hubenv create ... --name NAME` suggestion.

Detailed spec target: `docs/specs/hubenv-env-ensure.md`.

### 5.2 Environment mutation

#### `hubenv install NAME PACKAGE…` / `hubenv uninstall NAME PACKAGE…`

Purpose: install/remove packages into/from a live env and keep the implicit
spec in sync.

Synopsis: `hubenv install|uninstall NAME PACKAGE… [--using mamba|pip|uv]
[--no-relock] [--dry-run]`

Behavior (`env_pkg.py`):
1. Live env missing → exit 1 ("Live environment '…' not found.").
2. `--dry-run` → print planned command + spec delta, exit 0.
3. Run installer in the env: `--using mamba` → `$NBW_MAMBA_CMD
   install|remove -n NAME -y …`; `--using pip|uv` → `pip|uv pip
   install|uninstall …`; **default (`--using` omitted) → `$NBW_PIP_CMD`**
   via `env_run` (per parser help: "default: pip via NBW_PIP_CMD").
   Failure → exit 1.
4. `update_and_save_spec` rewrites the shelf spec's package list
   (pip section for pip/uv; conda deps for mamba; dedupe on add, base-name
   removal on uninstall via `pkg_base_name`).
5. Print relock suggestion unless `--no-relock`.

Rough edges: the spec update is a *silent* mutation — a failed installer
leaves the spec unmodified (that ordering holds); the spec write is
unconditional (`save_hubenv_spec` overwrite).

Detailed spec target: `docs/specs/hubenv-env-install-uninstall.md`.

#### `hubenv relock NAME`

Purpose: re-curate (version-pin) the pip section of the implicit spec and
persist it.

Synopsis: `hubenv relock NAME [--dry-run]`

Behavior (`env_relock.py`):
1. Live env missing → exit 1.
2. No pip section → "No pip packages to relock" (exit 0, no-op).
3. `RequirementsCompiler.compile_packages_for_env` resolves pins;
   failure → exit 1.
4. `--dry-run` → print resolved list, exit 0.
5. Replace the pip section in the spec and `save_hubenv_spec`.

Rough edges: only pip packages are relocked (conda deps are touched by
install/uninstall but not re-pinned here); compiler failure surfaces as an
exit 1 without always naming the offending package.

Detailed spec target: `docs/specs/hubenv-env-relock.md`.

#### `hubenv rm NAME…`

Purpose: delete environments from live and/or archive.

Synopsis: `hubenv rm NAME… [--live | --archived | --both] [--pantry PATH]
[-y/--yes] [--dry-run]`

Behavior (`env_rm.py`) — a 5-step pipeline:
1. **Resolve** glob patterns against live envs and/or shelves per target
   (`both` is default).
2. `--dry-run` → print plan, exit 0.
3. **Validate**: read-only shelf pantries are refused (exit 1, with guidance
   to set `NBW_PANTRY` / `--pantry`); paths outside the safe roots
   (`$NBW_MM/envs` or `<pantry>/shelves`) are **refused** (exit 1) —
   `is_safe_rm_path` is the path-escape guard.
4. **Print plan**; **prompt** "Proceed? (y/N)" (written to **stderr**) 
   unless `-y` (EOF → abort, exit 1). The `rm` prompt is the only interactive
   one in the CLI.
5. **Execute**: live → `unregister_environment` + `delete_environment`;
   shelf → `shutil.rmtree`; already-gone → reported, not an error;
   best-effort removal of now-empty `shelves/` dirs.

Detailed spec target: `docs/specs/hubenv-env-rm.md`.

### 5.3 Kernel & shell

#### `hubenv register NAME`

Purpose: (re)register the Jupyter kernel for a live env.

Synopsis: `hubenv register NAME [--display-name NAME] [--dry-run]`

Behavior (`env_ensure.py:cmd_env_register`): `--dry-run` → one line; else
`register_environment(name, display_name, {})`; success → one line +
`print_exports` + exit 0; failure → exit 1. Requires mamba + the live env.

#### `hubenv unregister NAME`

Purpose: remove the kernelspec (best effort; "if it existed").

Synopsis: `hubenv unregister NAME [--dry-run]`

Behavior: `--dry-run` → one line; else `unregister_environment(name)`,
"Unregistered Jupyter kernel '…' (if it existed).", exit 0 (no failure
signal when the kernel is absent).

#### `hubenv activate NAME` / `hubenv deactivate`

Purpose: emit a **pure stdout shell snippet** (for `eval`/source) that
activates `NAME` by absolute path, or deactivates the current mamba env.
No side effects beyond printing.

Synopsis: `hubenv activate NAME`; `hubenv deactivate` (no arguments)

Behavior (`env_activate.py`):
- `activate`: live env missing → exit 1 with
  "Restore it first with `hubenv ensure NAME`."
  Else `activation.emit_activation(...)` including the env's
  `environment_vars` exports (`var_export_lines`, byte-equivalent to
  `var ls NAME --export`); shell auto-detected (`activation.detect_shell`).
- `deactivate`: `activation.emit_deactivate(...)`; always exit 0.

Detailed spec target (shared): `docs/specs/hubenv-kernel-and-shell.md`.

### 5.4 Inspection

#### `hubenv ls [NAME-or-glob…]`

Purpose: list live envs and pantry shelves in one table.

Synopsis: `hubenv ls [PATTERN…] [--all] [--pantry PATH]
[--format table|json]`

Behavior (`env_ls.py`):
- Lists shelves per pattern (default: all) + live envs.
- Table: `NAME  PANTRY  STATUS  ARCHIVE  LIVE`; ARCHIVE is a 12-char
  truncated save hash, the marker `spec-only` when no can, or `not a shelf`
  for a live-only env (marked `*`); `--all` expands duplicate names,
  otherwise the first win.
- JSON: `{ shelves: [...can...], live_envs: [...] }`.
- Always ends with shadowing warnings (stderr) when a name spans pantries.

#### `hubenv info NAME`

Purpose: detailed metadata for one env (live path + per-shelf: pantry,
path, writability, save hash, can/archive presence & size).

Synopsis: `hubenv info NAME [--pantry PATH] [--format table|json]`

Behavior (`env_info.py`): no shelf *and* no live env → warning + exit 1;
otherwise print the block; "NOT ARCHIVED — run: hubenv save NAME" when the
can is absent; shadowing warnings on multiple shelves.

#### `hubenv status`

Purpose: whole-system state summary (one row per distinct env).

Synopsis: `hubenv status [--format table|json]`

Behavior (`status.py`): always exit 0. Rows combine `live_envs`,
`shelves`, `has_can` (the "actually archived" truth), and kernel
registered (via `jupyter kernelspec list --json`). Header line shows
`active_env` (`NBW_ACTIVE_ENV`) and active pantry (`NBW_PANTRY` or first
writable). Pantries listed with `r/w`/`r/o`. JSON is the full dict.
Rough edges: the JSON `pantries` field omits `writable` in some builds
(re-verify when speccing; the current `aggregate_status` includes it).

#### `hubenv doctor`

Purpose: run self-test checks and report pass/fail.

Synopsis: `hubenv doctor [--format table|json]`

Checks (`doctor.py`), in order:
1. **mamba/micromamba** on PATH.
2. **pantry writability** (≥1 writable in the chain).
3. **kernel-JSON sanity** — for `NBW_ACTIVE_ENV` only: kernel dir under
   `~/.local/share/jupyter/kernels`, `kernel.json` present, valid, `argv`
   non-empty; when no active env → "skipped" (pass).
4. **spec-only shelves** — any shelf without a can → FAIL with hint
   "Run `hubenv save <name>`…".

Exit: 0 if all pass, else 1. Table or JSON (`{checks:[…], all_pass}`) —
JSON has two parallel shapes (`checks`/`all_pass` vs. per-check
`pass`/`detail`/`hint`).

Detailed spec target (shared): `docs/specs/hubenv-inspection.md`
(loudly cover `ls`, `info`, `status`, `doctor`).

### 5.5 Spec & vars

#### `hubenv export NAME`

Purpose: export the implicit spec in one of three formats.

Synopsis: `hubenv export NAME [--to-mamba-spec | --to-requirements |
--to-wrangler-spec] [-o FILE|-] [--pantry PATH]`

Behavior (`export.py`):
- No shelf spec → "No spec found for env 'NAME'." + exit 1. Pantry lookup
  honors `--pantry` (RE-12 resolved in v0.10.0, via `store_for`).
- `--to-mamba-spec` (default) → mamba-view YAML; `--to-requirements` → pip
  lines; `--to-wrangler-spec` → full wrangler-spec YAML
  (`mamba_to_wrangler`).
- `--output "-"` → stdout (default); else write file + one "Exported spec …"
  line.

`--to-requirements` on a spec without pip packages still exits 0, but now 
prints a **stderr warning** ("spec for 'NAME' has no pip packages; empty 
requirements output") instead of silently emitting an empty string; 
`--to-mamba-spec` is the no-flag default, matching the help text.

#### `hubenv var ls NAME [GLOB…]`

Purpose: list `environment_vars` for an env.

Synopsis: `hubenv var ls NAME [GLOB…] [--export] [--format table|json]
[--pantry PATH]`

Behavior (`var.py`): filters by glob (empty → all); prints table
(default), `export VAR=VALUE` lines (`--export`), or JSON
(`--format json`). **`--export` and `--format json` are mutually
exclusive** — passing both is a usage error (stderr
"--export and --format json are mutually exclusive; choose one.", exit 1)
— Pantry lookup honors `--pantry`.  No spec → empty view (no error); "(no environment variables
defined for '<name>')" marker.

#### `hubenv var add NAME VAR=VALUE…`

Purpose: add/update `environment_vars` in the shelf spec and refresh the
kernel.

Synopsis: `hubenv var add NAME VAR=VALUE… [--pantry PATH]`

Behavior: **spec-exists guard first** (before any mutation): no shelf
spec → stderr "No spec found for env 'NAME'. Create it first:
hubenv create NAME --from-empty" + exit 1 — 
Pantry lookup honors `--pantry`. Then: parse assignments (first `=` only; 
malformed → "not a VAR=VALUE assignment" + exit 1); load spec; update dict;
`save_hubenv_spec`; `refresh_kernel_vars` (re-register with the new vars;
failure → warning, spec kept). Prints one `Set …` line per var +
"Kernel refreshed for '<name>'."

#### `hubenv var rm NAME GLOB…`

Purpose: remove `environment_vars` by glob and refresh the kernel.

Synopsis: `hubenv var rm NAME GLOB… [--pantry PATH]`

Behavior: remove matches (no match → "No matching variables …" + exit 0,
spec untouched); otherwise save + kernel refresh; one `Removed …` line per
var. No dry-run (the spec write is unconditional).

Detailed spec target (shared): `docs/specs/hubenv-var.md`; `hubenv export`
→ `docs/specs/hubenv-export.md`.

### 5.6 Data

#### `hubenv data ls NAME` / `download` / `unpack` / `pack` / `clean`

Purpose: manage *data* archives (distinct from the env can) for an env —
list, download from the platform, unpack into install locations, pack live
data dirs, clean.

| Command | Synopsis | Behavior |
|---|---|---|
| `data ls` | `data ls NAME [--format table|json]` | Scans `<shelf>/archives/data-*` files (excluding internal files) → `ARCHIVE  SIZE` table or JSON (name + archive list). No shelf → "(no data archives …)" marker. |
| `data download` | `data download NAME [--select REGEX] [--no-validate]` | Delegates to `data_manager.download_data(name, select, validate)`; success → one line; failure → exit 1. Default `select=".*"`. |
| `data unpack` | `data unpack NAME [--no-unpack-existing] [--symlinks\|--no-symlinks]` | `data_manager.unpack_data(...)`; symlinks at install locations by default; success → one line; failure → exit 1. |
| `data pack` | `data pack NAME` | `data_manager.pack_data(name)`; success → one line; failure → exit 1. |
| `data clean` | `data clean NAME [archived\|unpacked\|both]` | `data_manager.delete_data(name, mode)` (`both` default); success → one line; failure → exit 1. |

Rough edges: `data ls` is the only `data` command that reads the pantry
directly (all others delegate to `data_manager`); `data ls` has no
`--select` and no glob (it lists all `data-*`); the `data` sub-parser
shares the `_dispatch_data` style of `var` (bare `data` → exit 1, RE-09
resolved).

Detailed spec target: `docs/specs/hubenv-data.md`.

### 5.7 Tooling

#### `hubenv completions <shell>`

Purpose: print a static (no-runtime-dependency) completion script for
`bash` | `zsh` | `fish`.

Synopsis: `hubenv completions bash|zsh|fish`

Behavior (`completions_cmd.py`, `completions.py`): generates from a
hard-coded command tree; unknown shell → stderr message + exit 1; supported
→ the script on stdout (no trailing newline beyond the generator's own),
exit 0. Doc-usage: `eval "$(hubenv completions bash)"`, write to
`$fpath[1]/_hubenv`, or `~/.config/fish/completions/hubenv.fish`.

#### `hubenv --version` / (no command)

Purpose: print `nb_wrangler.constants.__version__`; with no command, print
the top-level help. Both exit 0. No detailed spec required (covered by
this document's §4.1).

---

## 6. Cross-cutting contracts (decomposition invariants)

These are the *shared* behaviors that every command relies on. They are
specified here once so that detailed specs can reference — not re-derive —
them.

### 6.1 The "implicit spec" contract

- The shelf spec is the **source of truth** for the environment's pinned
  package list and `environment_vars`.
- `env_spec.py` is the only read/write path (load/save/update). Commands
  must not hand-edit the YAML.
- On-disk = full wrangler spec (valid under `SpecManager`); in-memory =
  mamba view. Conversion is transparent.
- `save_hubenv_spec` overwrites unconditionally; `update_and_save_spec`
  is the canonical add/remove path (dedup on add, base-name removal on
  remove, pip/conda routing by `--using`).

### 6.2 Kernel-registration contract

- Register: `register_environment(name, display_name, env_vars)` (a
  `mamba run -n name python -m ipykernel install …` step).
- Unregister: `unregister_environment(name)` (best effort).
- `var` mutations must trigger a re-register; `create`/`restore`
  register-on-first-use; `rm --live` unregisters before deleting.

### 6.3 Pantry & shadowing contract

- Writability is per-pantry; the chain is searched in order; first
  writable wins for writes; reads are first-wins *or* explicit
  `--pantry` *or* refused (command-specific, documented per command).
- Shadowing is surfaced as a warning, never an error.
- Safe-path guard (`is_safe_rm_path`) applies to `rm` only.

### 6.4 Idempotency contract

- Save hash (`last-save.sha256`) and restore hash are the *only*
  idempotency tokens; `restore --force` is the sole bypass.
- `ensure` is the canonical "available or restore" entry point; it must
  be a no-op when live and must never re-run a full restore when the
  restore hash already matches the save hash.
- `rm` reports already-gone targets; it does not error on them.

### 6.5 Output & exit-code contract

- stdout = machine-readable / eval-able; stderr = diagnostics (§4.3).
- Exit codes per §4.4. Handlers return int; do not rely on exceptions.
- `--quiet` suppresses stderr; stdout is never suppressed by `--quiet`.

---

## 7. Known rough edges & open questions

The thirteen rough edges identified during decomposition are **all resolved
in v0.10.0** (per `docs/plans/hubenv-rough-edges-plan.md`). The table
below keeps the original pre-fix descriptions as design context; the
Status column records the resolution. New behavioral observations should
be appended here with a fresh ID.

| ID | Location | Description (pre-fix observation) | Status (v0.10.0) |
|---|---|---|---|
| RE-01 | `cli.py:_main` | `parse_known_args` silently ignores unknown flags. Typos in flags (e.g. `--nam`) are dropped rather than rejected by argparse. A script that mistypes a flag gets a silent different behavior. | **Resolved** — strict `parse_args`; unknown flags → argparse error, exit 2 (§4.1). |
| RE-02 | `cli.py:main` | `HubenvError` is defined and caught, but **no handler raises it** today. The "clean error message" path is a forward-looking mechanism; all current errors are handler-side `get_logger().error` + return 1. | **Resolved** — `HubenvError` lives in `_common.py` (re-exported by `cli.py`); `cmd_env_create` raises it on seed failures. |
| RE-03 | `env_create.py` / `seeds.py` | `--from-existing-env` runs `mamba env export` + `pip freeze` **before** the existence check, and even under `--dry-run`. A failed probe raises `ValueError`, which `main` does not catch → traceback + exit 1 (no clean message). See `hubenv-env-create.md` §6/§8. | **Resolved** — `_probe_target` runs first, then `_seed` wraps `build_seed_dict` in `except (ValueError, OSError)` → `HubenvError("Failed to seed spec for 'NAME': …", exit_code=1)` — clean message, no traceback (§5.1, `hubenv-env-create.md` §6/§8). |
| RE-04 | `env_restore.py:write_at_boot_snippet` | `--at-boot` appends a `source` line to `~/.bashrc` (marker-gated). It is **bash-only** (zsh/fish users are not handled), uses `2>/dev/null \|\| true` (silent failures), and the snippet directory `~/.hubenv/` is not cleaned up on `rm`/`unregister`. | **Resolved** — snippet only: `~/.hubenv/env-<name>.sh` + a printed `source` instruction; **no `~/.bashrc` edit**; `hubenv rm` removes the snippet via `remove_at_boot_snippet` (§5.1). |
| RE-05 | `doctor.py` | `doctor` **fails** when no EFS mount is detected under a pantry path, and `read_proc_mounts` only works on Linux (parses `/proc/mounts`). Non-EFS and non-Linux installs will see a red EFS row even though the rest of the system is healthy. | **Resolved** — the EFS check was removed entirely; doctor now runs 4 checks (§5.4). |
| RE-06 | `completions.py` | `_HUBENV_COMMAND_TREE` is stale (pre-flattening): it still models env verbs under an `env` group and omits `activate`/`deactivate` (it does include `register`/`unregister`). Generated completion suggests `hubenv env <verb>`, which does not parse. | **Resolved** — tree flattened to all 20 top-level verbs (incl. `activate`/`deactivate`); no `env <verb>` suggestions (§5.7). |
| RE-07 | `env_ensure.py` | `ensure --display-name` is accepted but **ignored**: the delegated `cmd_env_restore` registers the kernel with display name = env name (see `env_restore.py:47`). | **Resolved** — `--display-name` threads through `EnsureArgs`; `env_restore.py` registers with `display_name or NAME` (§5.1 restore/ensure). |
| RE-08 | `var.py:cmd_var_ls` | `--export` and `--format json` are both flags but mutually exclusive in output; when both are passed, **JSON wins** (unresolvable via argparse; `--format table --export` silently drops the table). | **Resolved** — passing both is now a usage error (stderr + exit 1) (§5.5 `var ls`). |
| RE-09 | `cli.py:_dispatch_var` / `_dispatch_data` | Missing sub-command in `var`/`data` logs an error and returns **0** (not 1) — a script treating exit 0 as success would not notice. | **Resolved** — bare `var`/`data` → stderr usage message, exit 1 (§4.1). |
| RE-10 | `export.py` | `--to-requirements` on a spec with no pip packages writes/prints an empty string (no error, no warning) — a "successful" 0-exit command that produced nothing. | **Resolved** — stderr warning "spec for 'NAME' has no pip packages; empty requirements output"; still exit 0 (§5.5 `export`). |
| RE-11 | `var.py` / `env_spec.py` | `var add`/`var rm` on an env with no shelf spec **creates** the shelf (via the `seed_from_empty` fallback) and writes a spec containing only the `environment_vars` — a side-effect not advertised by the help text. | **Resolved** — `var add` requires an existing shelf spec (exit 1 + "Create it first: hubenv create NAME --from-empty"); no auto-creation; `var rm` was already a no-op on a missing shelf (§5.5 `var add`). |
| RE-12 | `cli.py` / `parser.py` | `status`, `doctor`, `var`, `data`, `export`, `register`, `unregister`, `activate`, `deactivate` do **not** accept `--pantry`; they use the default `NBW_PANTRY` chain only. Only `create/save/restore/ls/info/rm/ensure` offer `--pantry`. | **Resolved (partial)** — `export`, `var ls`, `var add`, `var rm` now accept `--pantry` via `_common.store_for` (11 verbs total); `data*`, `status`, `doctor`, `register`/`unregister`, `activate`/`deactivate` remain deliberately out of scope (§4.5, §5.5). |
| RE-13 | `env_rm.py:prompt_rm_confirmation` | The interactive `Proceed? (y/N)` prompt reads from stdin and writes to **stdout** (mixed with the plan print), so the "stdout is machine-readable" discipline is bent by the only interactive command. | **Resolved** — the prompt goes to **stderr** (stdout stays machine-readable) (§5.2 `rm`). |

---

## 8. Decomposition contract

Rule: **expand this document into one detailed spec per `docs/specs/` file,
using the proven template in `hubenv-env-create.md`.**

### 8.1 Naming & mapping

| Detailed spec | Covers | Source module(s) | Plan-b phase |
|---|---|---|---|
| `hubenv-env-create.md` *(exists)* | `create` | `env_create.py`, `seeds.py`, `env_spec.py` | 1 |
| `hubenv-env-save.md` | `save` (+ `create --save` path) | `env_save.py` | 2 |
| `hubenv-env-restore.md` | `restore` (incl. `--at-boot`) | `env_restore.py` | 3 |
| `hubenv-inspection.md` | `ls`, `info` (or split) | `env_ls.py`, `env_info.py` | 4 |
| `hubenv-env-install-uninstall.md` | `install`, `uninstall` | `env_pkg.py` | 5 |
| `hubenv-env-relock.md` | `relock` | `env_relock.py` | 5 |
| `hubenv-env-rm.md` | `rm` | `env_rm.py` | 6 |
| `hubenv-env-ensure.md` | `ensure` (delegates to restore) | `env_ensure.py` | 7 |
| `hubenv-kernel-and-shell.md` | `register`, `unregister`, `activate`, `deactivate` | `env_ensure.py`, `env_activate.py` | 7 |
| `hubenv-var.md` | `var ls/add/rm` | `var.py` | 8 |
| `hubenv-data.md` | `data ls/download/unpack/pack/clean` | `data.py` (+ `data_manager.py`) | 9 |
| `hubenv-export-status-doctor.md` | `export`, `status`, `doctor` | `export.py`, `status.py`, `doctor.py` | 10 |
| `hubenv-completions.md` | `completions <shell>` | `completions.py`, `completions_cmd.py` | 11 |
| `hubenv-common.md` | Cross-cutting: config, global flags, output discipline, exit codes, pantry/shadowing, idempotency, spec model, shared contracts | `cli.py`, `parser.py`, `_common.py`, `config.py`, `env_spec.py`, `pantry.py` | (foundation) |

Each detailed spec's **"See also"** section must back-link to this document
and to the relevant cross-cutting contract (§6.x). No detailed spec may
re-define a contract that this document already fixes.

### 8.2 Detailed-spec template (mirrors `hubenv-env-create.md`)

1. **Purpose** — one paragraph.
2. **Command synopsis** — single line, all positional + flags inline.
3. **Arguments** — table(s): name, value, default, required, meaning.
4. **Execution paths** — numbered step-by-step per branch (default,
   `--dry-run`, `--force`, error branches).
5. **Exit codes** — table of condition → code.
6. **Side-effect summary** — matrix or bullets; what is written/changed
   per flag combination.
7. **Edge cases** — observed behaviors, including failures, empty inputs,
   idempotency, missing objects.
8. **Pantry interaction** — which pantries are searched/written;
   `--pantry` semantics; writability.
9. **Output examples** — real stdout/stderr samples per mode.
10. **What is NOT done (out of scope)** — explicit negative list.

### 8.3 Ground-truth rule for each detailed spec

- Argument surface from `parser.py` (authoritative).
- Dispatch from `cli.py`.
- Behavior from the named module (authoritative).
- Storage / env var / archive-format facts from `pantry.py`,
  `constants.py`, `env_spec.py`.
- Acceptance / observed behavior from `tests/hubenv/*`.
- Any `RE-##` item that touches the command is annotated in the relevant
  section (edge cases / out-of-scope) of that command's detailed spec.

### 8.4 Decomposition order (suggested)

1. **`hubenv-common.md`** first — it owns the cross-cutting contracts that
   every other spec references.
2. **MVP trio**: `hubenv-env-save.md` → `hubenv-env-restore.md` →
   `hubenv-inspection.md` (create is already written).
3. **Mutation & lifecycle**: install/uninstall + relock, rm, ensure,
   kernel-and-shell (register/unregister/activate/deactivate).
4. **Var & data**: `hubenv-var.md`, `hubenv-data.md`.
5. **Utilities**: export/status/doctor, completions.
6. **Back-fill**: update this top-level spec as features evolve; keep the
   RE-## table current.

---

## 9. What is NOT in scope (top-level)

- **No curation, no notebook discovery, no Docker build** — that is `nbw`.
- **No remote/network pantries** (pantries are local dirs; EFS is a
  deployment detail, not a `hubenv` feature).
- **No package indexing** beyond mamba/pip/uv in-environment.
- **No GPU / CUDA selection** (CPU-only per AGENTS.md).
- **No telemetry** (`hubenv_command` is reserved, not consumed).
- **No auth / multi-user policy** (writability is file-system perms).

---

## 10. References

- `hubenv-env-create.md` — the proven detailed-spec format (template) and
  the first decomposed feature.
- `docs/hubenv-howto.md` — user-facing concepts and quick recipes.
- `docs/plan-b/phases/00-index.md` — phase/plan index for the feature set.
- Source: `nb_wrangler/hubenv/` (all 25 modules), `nb_wrangler/pantry.py`,
  `nb_wrangler/environment.py`, `nb_wrangler/data_manager.py`,
  `nb_wrangler/constants.py`.
- Tests: `tests/hubenv/` (13 files).
