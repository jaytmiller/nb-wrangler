# `hubenv` — Cross-Cutting Contracts (Foundation Spec)

> Reverse-engineered, *foundation* spec. Derived from the implementation in
> `nb_wrangler/hubenv/cli.py`, `parser.py`, `_common.py`, `config.py`,
> `env_spec.py`; `nb_wrangler/pantry.py`, `environment.py`, `activation.py`,
> and `constants.py`.
>
> This is the "common" spec of the decomposition: it owns the cross-cutting
> contracts that every other `hubenv-*` spec references rather than
> re-derives. Per the decomposition contract (§8 of `hubenv.md`), it is the
> only detailed spec that does **not** cover a single command — it covers
> the CLI plumbing, configuration, storage, and shared invariants.
>
> Verified against `tests/hubenv/`.

---

## 1. Purpose

`hubenv` is the Persistent Platform Environments (PPE) CLI for nb-wrangler.
This spec fixes the *shared* behaviors that every command relies on:

- the entry point, dispatch, and error-handling model of the CLI;
- the global flags and runtime configuration (env vars, directory layout);
- the pantry store, pantry resolution, and shadowing rules;
- the implicit (mamba-view ↔ wrangler-spec) model and its on-disk form;
- the idempotency tokens;
- the stdout/stderr output discipline and the exit-code contract.

A command's detailed spec may *refine* these contracts for one command but
may never contradict them (see "See also").

---

## 2. Entry point & dispatch (`cli.py`)

- The `hubenv` console script runs `nb_wrangler.hubenv.cli:main(argv)`.
- `main()` wraps dispatch in `try/except`:
  - `HubenvError` → `logger.error(exc.message)` to stderr; return
    `exc.exit_code`.
  - `KeyboardInterrupt` → `logger.info("\nInterrupted.")`; return **130**.
  - **Any other exception propagates** (traceback + exit 1).
- `main()` calls `_main(argv)`, which:
  1. `parser = build_parser()`; `args = parser.parse_args(argv)` — parsing is
     **strict** (`parse_args`); unknown flags or positionals are argparse
     usage errors, exit **2**.
  2. `args.version` → print `nb_wrangler.constants.__version__`, return 0.
  3. no `args.command` → `parser.print_help()`, return 0.
  4. `_setup_config(args)` → builds a `WranglerConfig` (logging + `hubenv_command`
     path such as `var.ls` + `hubenv_args`) and installs it as the singleton;
     `WranglerLogger.from_config(config)` wires the logger. **No command
     consumes `hubenv_command` today** — it is reserved for logging/telemetry.
  5. Dispatch is dict-based:
     - env verbs in `_ENV_DISPATCH` (flattened top-level): `create`, `save`,
       `restore`, `ls`, `info`, `install`, `uninstall`, `relock`, `rm`,
       `ensure`, `register`, `unregister`, `activate`, `deactivate`;
     - `var` / `data` groups in `_dispatch_var` / `_dispatch_data`;
     - utilities in `_main` directly: `export`, `status`, `doctor`,
       `completions`.
     - A non-empty sub-parser that received no sub-command logs
       "…sub-command required. Use one of: …" and returns **1**
       (RE-09 resolved). An unknown sub-command logs the
       "not yet implemented" message and returns **2** (RE-02/RE-09).
- `HubenvError` is defined in `_common.py` (re-exported by `cli.py`) and carries
  a message + `exit_code`. Today only `cmd_env_create` raises it (seed
  failures); every other handler returns an int instead.

---

## 3. Global flags

Registered on the **top-level** parser and on **every** command parser
(`_add_global_flags(parser, subcommand=True)`), so a flag works on either side
of the command (`hubenv --quiet create` ≡ `hubenv create --quiet`). On the
sub-command side defaults are `argparse.SUPPRESS` so they never clobber a
top-level value.

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `-q`, `--quiet` | bool | `False` | Suppress all log output (stderr); only stdout visible |
| `--verbose` | bool | `False` | Verbose log output |
| `--debug` | bool | `False` | Drop into pdb on exceptions |
| `--color` | choice | `DEFAULT_COLOR_MODE` | Colorize log output (`auto`/`always`/`never` per `VALID_COLOR_MODES`) |
| `--log-times` | choice | `DEFAULT_LOG_TIMES_MODE` | Timestamps in log messages (`VALID_LOG_TIME_MODES`) |
| `--reset-log` | bool | `False` | Delete the nb-wrangler log file |

`--quiet` suppresses **stderr log lines only**; stdout is never suppressed.

---

## 4. Runtime configuration (environment variables, `constants.py`)

| Variable | Default | Meaning |
|---|---|---|
| `NBW_ROOT` | `~/.nbw-live` | Live-state root; must **not** inherit `MAMBA_ROOT_PREFIX`/`CONDA_ROOT_PREFIX` |
| `NBW_MM` | `$NBW_ROOT/mm` | Mamba root under `NBW_ROOT` |
| — (derived) | `$NBW_MM/envs/<name>` | **Live envs root** (where mamba actually installs) |
| `NBW_PANTRY` | `~/.nbw-pantry` | Pantry search chain; **colon-separated**, like `PATH` (`NBW_PANTRY_DIRS` holds the full list, `NBW_PANTRY` the first entry) |
| `NBW_CACHE` | `$NBW_ROOT/cache` | Cache dir (also seeds `UV_CACHE_DIR`, `PIP_CACHE_DIR`, …) |
| `NBW_MAMBA_CMD` | `$NBW_MM/bin/micromamba` (or `$MAMBA_EXE`) | Mamba executable used for all env ops |
| `NBW_PIP_CMD` | `uv pip` | Pip executable used for `--using` default installs |
| `NBW_ACTIVE_ENV` | *(unset)* | Convention var naming the active PPE; read by `status`/`doctor`/activation |
| `NBW_ENV_ROOT` | *(unset)* | Convention var `print_exports` prints as `<live_envs_root>/<name>` |
| `NBW_SHELL` | *(unset)* | Overrides shell detection in `activation.detect_shell` |

**Subprocess isolation:** every `EnvironmentManager.wrangler_run` call pins
`MAMBA_ROOT_PREFIX=$NBW_MM` in the subprocess environment (overriding any
inherited value), so mamba always resolves envs under the nb-wrangler root,
even when the user's shell runs a different mamba ("foreign" env).

---

## 5. Directory layout (defaults)

```
$NBW_MM/envs/<name>/                          # LIVE ENV (created by mamba)
$NBW_ROOT/.hubenv-restore/<name>.sha256       # RESTORE HASH (per env)
<pantry>/shelves/<name>/                     # SHELF (one per env per pantry)
  nbw-wrangler-spec.yaml                     # SHELF SPEC (full valid wrangler spec, §8)
  archives/
    env-<name>.tar                           # CAN (packed live env)
    data-*                                    # DATA ARCHIVES (hubenv data *)
    last-save.sha256                          # SAVE HASH
~/.hubenv/env-<name>.sh                      # at-boot snippet (restore --at-boot only)
~/.local/share/jupyter/kernels/<name>/       # KERNELSPEC
```

`<pantry>` is any element of the `NBW_PANTRY` chain (or a `--pantry` path).
The can filename is `env-<name>.tar` — `NbwShelf.env_archive_path(name,
DEFAULT_ARCHIVE_FORMAT)` emits `"env-" + name + archive_format`
(`DEFAULT_ARCHIVE_FORMAT == ".tar"`).

---

## 6. The store: `PantryStore` / `NbwPantrySet`

`hubenv.config.PantryStore` is a **thin subclass of
`nb_wrangler.pantry.NbwPantrySet`** — zero logic duplicated in hubenv. It
anchors `NBW_PANTRY_DIRS`/`NBW_ROOT` to the `hubenv.config` namespace so
test patches of `nb_wrangler.hubenv.config.*` keep working. `HubenvConfig` is
a back-compat alias.

Key methods (all inherited from `NbwPantrySet`):

| Method | Returns / behavior |
|---|---|
| `target_pantry(forced)` | Forced path → validated writable → returned; else `first_writable_pantry()`; `None` when no writable pantry (logs error for a forced non-writable path) |
| `first_writable_pantry()` | First writable pantry in priority order, or `None` |
| `is_writable(p)` | `p.exists() and os.access(p, os.W_OK)` |
| `writable_pantries()` | All writable pantries in priority order |
| `list_shelves(glob, pantry)` | `[{pantry, name, path, writable, save_hash}]`; `save_hash` read from `archives/last-save.sha256` (or `None`) |
| `list_live_envs()` | `[{name, path}]` for dirs under `live_envs_root` (`NBW_MM/envs`) |
| `find_shelves(name)` | **All** `(pantry_path, shelf_path)` pairs across pantries (used for shadowing detection; restore/ensure refuse on multi-match) |
| `get_shelf(name)` | First match in priority order; primary pantry if none (used to *create*) |
| `has_can(name)` | `True` iff `<first matching shelf>/archives/env-<name>.tar` exists. **The single source of truth for "actually archived".** A shelf directory alone is *not* archived. |
| `shelf_spec_path(name)` | `<first writable pantry>/shelves/<name>/nbw-wrangler-spec.yaml` (falls back to the first pantry dir when none is writable) |
| `restore_hash_path(name)` | `$NBW_ROOT/.hubenv-restore/<name>.sha256` |

`NbwShelf` (per shelf dir) provides: `spec_path` (`nbw-wrangler-spec.yaml`),
`archive_root` (`archives/`), `env_archive_path(name, fmt)`
(`archives/env-<name>.<fmt>`), `pack_environment`/`unpack_environment`
(`tar -amcf` / `tar -amxf`, `ARCHIVE_TIMEOUT`), and the save-hash file at
`archives/last-save.sha256`.

---

## 7. Pantry resolution & shadowing

- **`store_for(args)`** (`_common.py`): `--pantry PATH` → `PantryStore(paths=[Path(PATH)])`;
  else `PantryStore()` (default chain).
- **Writes**: first *writable* pantry wins (via `target_pantry`). A
  `--pantry` that is itself not writable fails with "Pantry '…' is read-only
  or does not exist. Use --pantry <writable-path>." — there is **no fallback**
  to the chain.
- **Reads** are command-specific:

  | Commands | `--pantry` | Multi-match read behavior |
  |---|---|---|
  | `create`, `save`, `restore`, `ensure`, `rm`, `ls`, `info`, `export`, `var ls`, `var add`, `var rm` | offered | `ls`/`info` collapse to first + warn (or `--all`); `restore`/`ensure` **refuse** and demand `--pantry` |
  | `status`, `doctor`, `data *`, `register`, `unregister`, `activate`, `deactivate` | **not offered** (deliberate; kernel/data-bound, or read-only ops) | chain used |

  (RE-12 resolved partial: `export`/`var *` gained `--pantry` via
  `_common.store_for`.)

- **Shadowing** (same name in several pantries): surfaced as a **warning** via
  `print_shadowing_warnings` (`_common.py`), never an error. Warning text:
  `"'{name}' shadowed across pantries: <p1>, <p2>"`.

---

## 8. Implicit spec model (`env_spec.py`)

Interactions with the shelf spec go only through `env_spec.py`; commands must
not hand-edit the YAML.

- **On disk**: always a **full valid wrangler spec** in exactly one of two
  mutually-exclusive forms (see `docs/spec-format.md`):
  - **Simple** — single YAML document; header requires `kernel_name` +
    `python_version`.
  - **Inline** — two YAML documents separated by `---`; doc 2 is a mamba-clean
    seed (`name`, `channels`, `dependencies`, no `environment_vars`).
  - Always with a valid `spec_sha256`; the file passes
    `SpecManager.load_and_validate` + `validate_sha256` and round-trips
    through save/relock (RE-14).
- **In memory**: a *mamba view* `{name, channels, dependencies,
  environment_vars?, DISPLAY_NAME_FLAG, INLINE_FLAG}`.
- **`load_hubenv_spec(store, name)`**:
  - no shelf spec → `seed_from_empty(name, None)` fallback (deps `["pip"]`);
  - two-doc → view built from doc 2 with doc-1 `environment_vars` merged in,
    flagged `INLINE_FLAG`;
  - single-doc → `wrangler_to_mamba`.
- **`save_hubenv_spec(store, name, spec)`**:
  - `to_wrangler_yaml` emits the form the source was created in (simple 1-doc,
    inline 2-doc), scaffolds `image_spec_header`/`repositories`/`system`,
    stamps a fresh `date_updated`, and computes a valid `spec_sha256`
    (shared `sha256_str`; `\n---\n` separator; no trailing newline — byte-exact
    vs `SpecManager.to_string` + `add_sha256`).
  - Creates parent dirs; **overwrites unconditionally** (no confirmation, no
    backup).
- **`update_and_save_spec`** — canonical add/remove path:
  - `--using pip|uv` (and default) → mutates the `{"pip": [...]}` sub-list of
    `dependencies` (add = dedupe-append; remove = drop entries whose base name,
    lowercased and stripped of `=<,>,!,~`, matches — `pkg_base_name`).
  - `--using mamba` → mutates the conda-string list (add = dedupe, inserted
    before the first pip sub-dict; remove = drop by lowercased base name).
- **`spec_display_name(spec_path)`** — reads `image_spec_header.display_name`;
  consulted at kernel-registration time so `create`/`restore`/`register`/
  `ensure` always agree on the display name.

---

## 9. Idempotency contract

- **Save hash** — `<shelf>/archives/last-save.sha256` (sha256 of the can).
  Written by `save` after a successful pack; read by `restore` (and transitively
  `ensure`).
- **Restore hash** — `$NBW_ROOT/.hubenv-restore/<name>.sha256`. Written by
  `restore` *after* a successful unpack, set to the shelf's save hash. A later
  `restore` with matching hashes is an **idempotent skip** (exit 0) unless
  `--force`.
- **`ensure`** is the canonical "available or restore" entry point: live → no-op
  skip; shelf → restore; neither → error + `hubenv create` suggestion.
- **`save`** has no hash-based skip: an existing can requires `--force`
  (the re-write of `last-save.sha256` still happens on every successful save).
- **`rm`** reports already-gone targets ("Already gone: …") and does not
  error on them.

---

## 10. Output discipline (stdout vs stderr)

**stdout is reserved for machine-readable / eval-able output** — `export …`
lines, tables, JSON, YAML specs, shell snippets. **Diagnostics go to the
logger on stderr.** A command's stdout must be safely consumable via
`$(…)` or `eval "$(…)"`. The `rm` prompt is the only interactive output, and
it is written to **stderr** (RE-13 resolved), keeping stdout clean.

Per-command stdout contracts (what a script may parse):

| Command | stdout contract |
|---|---|
| `create` | eval-able `export NBW_ACTIVE_ENV=…` / `export NBW_ENV_ROOT=…`; or the seeded YAML under `--dry-run` |
| `save` | one `Saved environment '<name>' to <path>` line (dry-run: `shelf:` / `can:` / `live env:` lines) |
| `restore` | eval-able exports; "already restored (idempotent skip)…" line when skipped; at-boot snippet lines |
| `ensure` | "already live (idempotent skip)" + exports, or restore's output |
| `register` | one summary line + exports |
| `activate` / `deactivate` | **only** the shell snippet (pure stdout) |
| `ls` / `info` | table or JSON (`--format`) |
| `status` / `doctor` | table or JSON (`--format`) |
| `export` | spec YAML / requirements text, or one "Exported spec …" line |
| `var ls` | table, `export …` lines (`--export`), or JSON |
| `var add` / `var rm` | one `Set …`/`Removed …` line per var + "Kernel refreshed…" |
| `data ls` | table or JSON |
| `data download/unpack/pack/clean` | one status line |
| `completions <shell>` | **only** the completion script |
| `install` / `uninstall` | dry-run: `Dry-run: would run:` + `Spec delta:` lines; action: relock suggestion (unless `--no-relock`) |
| `relock` | dry-run: resolved list; action: `Relocked N packages …` or `No pip packages …` |
| `rm` | deletion plan (stdout) + confirmation prompt (stderr) + per-target `Removed …`/`Already gone:` lines |

---

## 11. Exit code contract

| Code | Meaning |
|---|---|
| `0` | Success (including documented idempotent skips) |
| `1` | Any handled failure (not found, no writable pantry, refused delete, subprocess failure, validation failure, abort) |
| `2` | argparse usage errors (unknown flag/sub-command); the "Not implemented" dispatch path (unreachable for user input via the current parser) |
| `130` | Interrupted (Ctrl-C / `KeyboardInterrupt`) |

Handlers signal results by **returning int** and logging errors to stderr.
Only `cmd_env_create` raises `HubenvError` (caught by `main()`).

---

## 12. Environment state model

`status.py:_state_for` defines the canonical self-describing states; every
listing command must be consistent with them:

| live? | shelf? | can? | State string |
|---|---|---|---|
| ✅ | ✅ | ✅ | `live+archived` |
| ✅ | ✅ | ❌ | `live+spec-only` |
| ✅ | ❌ | ❌ | `live` |
| ❌ | ✅ | ✅ | `archived` |
| ❌ | ✅ | ❌ | `spec-only` |

Key invariant: **a shelf directory alone is not "archived"**.
`PantryStore.has_can(name)` (the presence of `archives/env-<name>.tar` under
the highest-priority matching shelf) is the *single* source of truth for
"restorable".

---

## 13. See also

- [`hubenv.md`](hubenv.md) — top-level behavior spec; the source of these
  contracts (§2–§4, §6, §7, §9) and the decomposition contract (§8).
- Command specs, one per feature area:
  [`hubenv-env-create.md`](hubenv-env-create.md),
  [`hubenv-env-save.md`](hubenv-env-save.md),
  [`hubenv-env-restore.md`](hubenv-env-restore.md),
  [`hubenv-env-install-uninstall.md`](hubenv-env-install-uninstall.md),
  [`hubenv-env-relock.md`](hubenv-env-relock.md),
  [`hubenv-env-rm.md`](hubenv-env-rm.md),
  [`hubenv-env-ensure.md`](hubenv-env-ensure.md),
  [`hubenv-kernel-and-shell.md`](hubenv-kernel-and-shell.md),
  [`hubenv-var.md`](hubenv-var.md),
  [`hubenv-data.md`](hubenv-data.md),
  [`hubenv-export-status-doctor.md`](hubenv-export-status-doctor.md),
  [`hubenv-inspection.md`](hubenv-inspection.md),
  [`hubenv-completions.md`](hubenv-completions.md).
- `docs/spec-format.md` — the two wrangler-spec forms this spec's §8
  references.
