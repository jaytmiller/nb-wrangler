# `hubenv create` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/env_create.py`, `nb_wrangler/hubenv/parser.py`,
> `nb_wrangler/hubenv/seeds.py`, `nb_wrangler/hubenv/env_spec.py`,
> `nb_wrangler/environment.py`, and `nb_wrangler/pantry.py`.
>
> Verified against `tests/hubenv/test_create.py`, `test_dry_run.py`,
> and `test_e2e.py` (Phase 1 + later).

---

## 1. Purpose

`hubenv create` seeds a mamba-spec dict from one of five mutually-exclusive
sources, then either prints the spec (dry-run) or brings the environment fully
into the hubenv "Persistent Platform Environment" (PPE) lifecycle:

1. build the live environment (via `mamba create`), or verify an
   already-installed environment exists for `--from-existing-env`;
2. persist the essentials — write the canonical shelf spec and register the
   Jupyter kernel — so the environment is usable in a future session.

Users who only need a throwaway live environment (CI, scratch) pass
`--ephemeral` to skip step 2 entirely.

Archiving the fresh environment into a pantry `can` is explicit: pass
`--save` to pack it immediately after step 2, or run `hubenv save <name>`
later (without `--save`, create prints a save reminder — see §5.2 step 3).

---

## 2. Command synopsis

```
hubenv create SOURCE [OPTIONS]
```

where at least one of the mutually-exclusive source flags must be present,
and exactly one (enforced by argparse `add_mutually_exclusive_group(required=True)`).

`--name NAME` is required for `--from-empty` / `--from-requirements` and
optional for the other three sources, where it defaults to the source's own
name via the hierarchy CLI > wrangler spec header > mamba spec (mamba spec
`name`, wrangler spec `kernel_name` or `image_name` or inline mamba spec
`name`, source environment name for `--from-existing-env`); no name at any
level is a clean error.

---

## 3. Arguments

### 3.1 Seed-source flags (mutually exclusive, exactly one required)

| Flag | Value | Meaning |
|---|---|---|
| `--from-empty` | *(none)* | Build a minimally-populated spec. Dependencies: pinned python (if `--python` given) + `pip`. |
| `--from-requirements` | `FILE…` (zero or more, `nargs="*"`) | Parse each named file's non-blank, non-`#`-prefixed lines into a `pip:` dependency section. |
| `--from-mamba-spec` | `FILE` (single) | Load a valid mamba/conda-spec YAML; override its `name` with `--name` (default: the spec's own `name` — a spec without a `name` field is an error); keep channels and dependencies as-is. |
| `--from-wrangler-spec` | `FILE` (single) | Read `image_spec_header.python_version`, `extra_mamba_packages`, and `extra_pip_packages` from a fully-formed wrangler spec; rebuild a mamba-spec dict. |
| `--from-existing-env` | `ENV_NAME` (single) | Export the package set of an existing mamba environment via `mamba env export` + `pip freeze`; build a mamba-spec dict from that. The env itself is not (re)created — it must already exist in mamba. |

### 3.2 Common flags

| Flag | Required / Default | Description |
|---|---|---|
| `--name` | required for `--from-empty` / `--from-requirements`; optional (derived default) otherwise | Name of the target environment (mamba env name, shelf name, kernel name — all the same string). Defaults via the hierarchy CLI > wrangler spec header > mamba spec to the source's own name: the mamba spec's `name`, the wrangler spec's `kernel_name` (then `image_name`, then inline mamba spec `name`), or the imported environment name for `--from-existing-env`; no name at any level is a clean error. |
| `--display-name` | optional, `None` | Jupyter kernel display name. Resolves CLI > wrangler spec header `display_name` > env name (only the wrangler source has a spec field); the effective value is recorded in the saved shelf spec header and is what `create`/`restore`/`register`/`ensure` register the kernel under (CLI always wins). |
| `--python` | optional, `None` | Python version pin (e.g. `3.11`). Appended as `python=3.11` conda dependency for `--from-empty` and `--from-requirements`; resolves CLI > source pin for `--from-wrangler-spec` (header/inline), `--from-mamba-spec` (the spec's `python=` dep, previously ignored), and `--from-existing-env` (the source env's pin). Overrides are logged, and stale compiled pip lock entries are cleared when the pin changes. |
| `--pantry` | optional, `None` | Pantry directory to target. When set, `PantryStore(paths=[Path(value)])` is used so the shelf spec is written under that specific pantry and is not resolved via the default `NBW_PANTRY_DIRS` chain. When omitted, the first writable pantry is used. |
| `--ephemeral` | optional, `False` | Build the live environment only; skip shelf-spec persistence and kernel registration. Use for temporary or CI scratch envs. |
| `--dry-run` | optional, `False` | Build and print the seeded mamba-spec dict as YAML to stdout (internal `_hubenv_*` flags stripped — §5.1); return 0 without installing, writing any shelf spec, registering any kernel, or modifying the filesystem. |
| `--save` | optional, `False` | After a fully successful build + persist, archive the new environment into a pantry can by delegating to the shared `_do_save` (documented in `hubenv-env-save.md` §4) with `force=False` — so an **existing** can is an error (exit `1`) *after* the environment has already been created. Without `--save`, create prints a `hubenv save` reminder instead (see §5.2 step 3). |

### 3.3 Global flags (inherited from top-level hubenv parser)

`-q/--quiet`, `--verbose`, `--debug`, `--color`, `--log-times`, `--reset-log`
— applied before dispatch; they configure the log output, not the create behavior.

---

## 4. Seed-dict construction (`build_seed_dict`)

All five seed builders return a dict of this shape:

```python
{
    "name": str,           # --name, or derived from the source (see §3.2)
    "channels": list[str], # always ["conda-forge"] unless overridden by the source
    "dependencies": list,  # conda string deps + optional {"pip": [str, …]} dict
}
```

**Every builder guarantees the baseline `TARGET_PACKAGES` pip section**: the
`pip` conda package appears in `dependencies`, and a single `{"pip": […]}`
sub-dict contains every `TARGET_PACKAGES` entry (e.g. `uv`, `pip`,
`ipykernel`, `jupyter`, `cython`, `setuptools`, `wheel`) merged with any
packages the source already listed (existing packages first, de-duplicated,
order-preserved). This ensures the created environment can support hubenv
functions (e.g. kernel registration via `ipykernel`).

### 4.1 `seed_from_empty(name, python)`

```
dependencies = [f"python={python}"?] + ["pip", {"pip": TARGET_PACKAGES}]
```

A `{"pip": TARGET_PACKAGES}` sub-dict is always appended so an empty
environment installs at least the minimum packages needed to support
hubenv functions in it (e.g. `ipykernel` for kernel registration).

### 4.2 `seed_from_requirements(name, files, python)`

```
deps = [f"python={python}"?, "pip", {"pip": [pkg1, pkg2, …]}]
```

Each file's non-blank, non-`#`-prefixed lines (stripped) are collected in file
order into the single `pip:` list, then the baseline `TARGET_PACKAGES` are
merged in (existing packages first, de-duplicated). **The `{"pip": [...]}`
entry is always present** — even when `files` is empty (zero-arg
`--from-requirements`), the pip list contains at least the
`TARGET_PACKAGES` baseline.

### 4.3 `seed_from_mamba_spec(name, path, python, display_name)`
 
The YAML file is loaded; `spec["name"]` is overridden with *name* when it is
not `None` (otherwise defaulted to the file's own `name`; if that is absent
the seed fails with a clean error asking for `--name`), and the baseline
`TARGET_PACKAGES` are merged into the `pip:` section (created if absent).
`channels` and `dependencies` from the file are otherwise kept as-is, except
the `python=` dep when *python* (i.e. `--python`) is given: the CLI pin then
replaces the file's pin (logged, stale compiled pip lock entries cleared) —
previously the CLI pin was ignored and the file's pin always won.  If the
file omits `channels`, the resulting dict will not have the key (mamba will
use its own default channels).

### 4.4 `seed_from_wrangler_spec(name, path, python, display_name)`

Reads the wrangler spec YAML, which may be **one or two documents** (simple vs
inline form — see `docs/spec-format.md`):

- **Form detection**: `load_all` splits the file; a second YAML document (an
  inline mamba seed) yields the **inline** form, otherwise **simple**.
- **Inline form**: the seed is built from doc 2 (its `name`/`channels`/`dependencies`
  recipe, kept byte-intact) with the resolved name/python applied (stale python
  pin cleared, with a descriptive log); doc 1's
  `extra_mamba_packages`/`extra_pip_packages` layer on top. The resulting seed
  is marked `INLINE_FLAG` so it re-saves as the two-doc form with the header
  recording the effective `kernel_name`/`python_version`.
- **Simple form**: the seed is derived from doc 1's header (`kernel_name`,
  `python_version`) + `extra_mamba_packages`/`extra_pip_packages`.
- **Name**: CLI `--name` > header `kernel_name`/`image_name` > inline `name`
  (clean error if absent from every level).
- **Python**: CLI `--python` > header `python_version` > inline python. In the
  simple form a pin is required: absent from all sources → `ValueError` (wrapped
  in `HubenvError` on the `create` path).
- **Display name**: CLI `--display-name` > header `display_name` > env name.
  The effective value is recorded in the saved shelf spec header (and honored
  by `restore`/`register`/`ensure`).
- The baseline `TARGET_PACKAGES` are merged into the pip list (existing
  packages first, de-duplicated).

`pip` is always included exactly once in the conda deps, and the `{"pip": […]}` sub-dict is always present (at least the `TARGET_PACKAGES` baseline).

### 4.5 `seed_from_existing_env(name, env_name, python, display_name)`
 
Two subprocess calls:
1. `mamba env export -n <env_name> --no-builds` → parsed YAML
2. `mamba run -n <env_name> pip freeze` → package list
 
Parse rules:
- `name` is overridden with *name* when it is not `None` (otherwise the
  import defaults to *env_name* — seamless name reuse).
- `channels` are preserved from the export (default `conda-forge` if absent).
- All conda deps are kept **except** any entry starting with `python`; the
  source env's pin is the fallback.
- `python` resolves as CLI > source env's pin (logged on override, stale
  compiled pip lock entries cleared), so `--python` now genuinely overrides
  an imported env's python (previously the CLI value was already applied but
  without logging).
- `pip` (the conda package) is ensured to appear exactly once in deps.
- When `pip freeze` returned a non-empty list, those packages are placed in a
  trailing `{"pip": […]}` entry; in either case the baseline `TARGET_PACKAGES`
  are merged in so the pip section is always present (existing packages first,
  de-duplicated).

If either subprocess fails (non-zero return code), `ValueError` is raised with
the stderr text.

---

## 5. Execution paths

### 5.1 `--dry-run` (all sources)

1. `_probe_target(args)` — cheap existence probe (logs INFO if the target
   already exists; non-fatal)
2. `seed = _seed(args)` → dict (wraps `build_seed_dict`; RE-03)
3. `spec_yaml = yaml_dumps(_strip_internal_flags(seed))` → YAML string of the
   canonical mamba-spec shape: the hubenv-internal flags
   (`_hubenv_display_name`, `_hubenv_inline`) are removed, so stdout never
   carries keys that mamba would not understand (same guarantee as the install
   path in §5.2 step 1)
4. `print(spec_yaml)` to stdout
5. `return 0`

**No** environment is created. **No** shelf spec is written. **No** kernel is
registered. **No** file system side effects.

> **Note:** even for `--dry-run`, the target existence probe
> (`_probe_target`) and then the seed build (`_seed` → `build_seed_dict`)
> run *before* the dry-run branch, so the `--from-existing-env` source still
> executes its two read-only subprocesses (`mamba env export` and
> `pip freeze`) to build the spec. The other four sources are purely
> in-memory. A failed seed (e.g. the source env missing so the probes fail)
> raises `ValueError`/`OSError`, which `_seed` wraps in `HubenvError`
> ("Failed to seed spec for 'NAME': …") — a clean stderr message with exit
> 1 and no traceback (RE-03 resolved in v0.10.0).

### 5.2 Build + persist (default, all sources)

After `_seed(args)` (RE-03) produces the seed, `cmd_env_create`:

1. **Build the live env**:
   - `--from-existing-env`: `_onboard_existing_env` — verify the source env
     exists via `em.environment_exists(args.from_existing_env)`.
     **Not found** → ERROR log `"Environment '<env>' not found in mamba."`, `return 1`.
   - other four sources: `install_environment(args.name, yaml_dumps(seed))`:
     a. Write `spec_yaml` to a temporary file with prefix `<name>-` and suffix `.yaml`.
     b. `EnvironmentManager.create_environment(name, tmp_path)`:
        - Runs: `<mamba_cmd> create --yes -n <name> -f <tmpfile> --strict-channel-priority`
        - Timeout: `ENV_CREATE_TIMEOUT` (1800 s).
        - On success: INFO log `"Environment <name> created. ..."`
        - On failure: ERROR log `"Failed to create environment <name>:"` + output.
     c. Delete the temp file (best-effort, `unlink(missing_ok=True)`).
     d. Return `0` if `create_environment` succeeded, `1` otherwise.

   If the build step fails, `cmd_env_create` returns `1` immediately — **no**
   shelf spec is written and **no** kernel is registered.

2. **Persist essentials** (`_persist_essentials`), unless `--ephemeral`:
   a. `_build_store(args)` → `PantryStore(paths=[Path(args.pantry)])` when
      `--pantry` is set, otherwise `PantryStore()`; return `None` (with a
      clear error) when no writable pantry is available → `return 1`.
   b. `save_hubenv_spec(store, args.name, seed)` (delegates to
      `to_wrangler_yaml`):
      - Resolves shelf path: `<target_pantry>/shelves/<name>/nbw-wrangler-spec.yaml`.
      - Emits a full valid wrangler spec in the form the seed was created in
        (single-doc "simple", or two-doc "inline" when `INLINE_FLAG` is set);
        stamps a fresh `date_updated` and computes a valid `spec_sha256`.
      - Creates parent directories (`mkdir(parents=True, exist_ok=True)`).
      - Writes the YAML to disk, byte-exact vs nbw's `SpecManager.to_string`
        (`\n---\n` separator, no trailing newline), so the file passes
        `SpecManager.load_and_validate` + `validate_sha256`.
   c. `em.register_environment(args.name, display_name, {})` where
      `display_name = seed["_hubenv_display_name"] or args.name` — the resolved
      display name the seed builder recorded (CLI `--display-name` > wrangler
      spec header `display_name` > env name; §3.2, §4.4):
      - Runs: `mamba run -n <name> python -m ipykernel install --user --name '<name>' --display-name '<display_name>'`
      - On success: INFO log `"Registered environment <name> as a jupyter kernel making it visible to JupyterLab as '<display_name>'."`
      - **On failure** (`register_environment` returns `False`): its
        `handle_result` already logs ERROR `"Failed to register environment
        <name> as a jupyter kernel:"` with details; `_persist_essentials`
        returns `1` **without** printing exports or the "ready" INFO line, and
        `cmd_env_create` exits `1`. The shelf spec has already been written
        (step b) and the live env remains usable via
        `mamba activate <name>` — re-run kernel registration once ipykernel
        is installed in it.
   d. `print_exports(args.name, store)`:
      - `export NBW_ACTIVE_ENV=<name>`
      - `export NBW_ENV_ROOT=<live_envs_root>/<name>`
   e. INFO log `"Environment '<name>' is ready. Kernel '<display_name>' registered. Shelf spec: <path>"`.
   f. `return 0`

3. **Save or hint** (only reached without `--ephemeral`):
   a. `--save`: `_save_after_create(args)` → `_do_save(PantryStore(), name,
      args.pantry, force=False)` (documented in `hubenv-env-save.md` §4.3); on
      success logs INFO `"Environment '<name>' is archived and restorable."`
      and returns the save's exit code — in particular an **existing** can is
      exit `1` (hard-coded `force=False`) *after* the environment was created.
   b. No `--save`: `print_save_hint(name)` — WARNING log on stderr
      `"Not archived yet. Run `hubenv save <name>` to create the restoreable
      can."` — then `return 0`.

For `--from-existing-env`, **no** call to `create_environment` is made —
the environment is assumed to already exist in mamba.

---

## 6. Exit codes

| Condition | Exit code |
|---|---|
| Dry-run success | `0` |
| Ephemeral build success (live env ready, no persistence) | `0` |
| Full success (build OK, spec saved, kernel registered, then save-or-hint step per §5.2 step 3) | `0` |
| Kernel registration failure (the `ipykernel install` inside `register_environment` exits non-zero) — build + shelf spec completed, **no** exports, no "ready" line | `1` |
| Install failure (mamba create non-zero) — no persistence | `1` |
| `--from-existing-env` source not found in mamba — no persistence | `1` |
| No writable pantry (and no valid `--pantry`) — build may have succeeded, but no spec/kernel | `1` |
| Seed probe/build fails (e.g. `--from-existing-env` source missing; `mamba env export` / `pip freeze` fail) | `1` — caught by `_seed` and re-raised as `HubenvError("Failed to seed spec for 'NAME': …", exit_code=1)`; `cli.main()` prints the clean message to stderr, no traceback (RE-03 resolved) |
| `--name` missing for `--from-empty` / `--from-requirements` (validated in `build_seed_dict`) | `1` — clean `HubenvError("--name is required for --from-empty and --from-requirements")` on stderr, no traceback |
| `--save`: target can already exists (hard-coded `force=False`) or can packing fails (see `hubenv-env-save.md` §5) — the environment is **already created** | `1` |

---

## 7. Side-effect summary by source

All five sources share the same default (build + persist) and opt-out
(`--ephemeral`) behavior. The only differences are which mamba step is run
and where the seed comes from.

| | `--from-empty` | `--from-requirements` | `--from-mamba-spec` | `--from-wrangler-spec` | `--from-existing-env` |
|---|---|---|---|---|---|
| Calls mamba `create` | ✅ | ✅ | ✅ | ✅ | ❌ |
| Probes existing env | — | — | — | — | ✅ `env export` + `pip freeze` + `env exists` |
| Creates live env (default) | ✅ | ✅ | ✅ | ✅ | ❌ (must pre-exist) |
| Writes shelf spec (default) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Writes shelf spec (`--ephemeral`) | ❌ | ❌ | ❌ | ❌ | ❌ |
| Registers kernel (default) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Registers kernel (`--ephemeral`) | ❌ | ❌ | ❌ | ❌ | ❌ |
| Prints exports (unless `--ephemeral`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Temp spec file created/deleted | ✅ | ✅ | ✅ | ✅ | ❌ |
| Packs a pantry can (with `--save`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Packs a pantry can (without `--save`) | ❌ | ❌ | ❌ | ❌ | ❌ |

`--save` is orthogonal to the source flag: when the build + persist succeed, it
archives the just-created environment into a pantry can *after* persistence
(§5.2 step 3; behavior documented in `hubenv-env-save.md` §4.3). Without
`--save`, the save hint is printed instead (§10.3).

---

## 8. Edge cases

- `--from-existing-env`: if the source environment does not exist in mamba
  (checked via path existence at `NBW_MM/envs/<name>`), the command exits
  `1` with a clear error and no shelf spec is written.
- Ordering (RE-03 resolved): `_probe_target` runs **before** the seed work
  (even under `--dry-run`); the seed build itself wraps `build_seed_dict`
  in `except (ValueError, OSError)`, so a failed `mamba env export` /
  `pip freeze` yields a clean `HubenvError` message
  ("Failed to seed spec for 'NAME': …") with exit `1` — never an unhandled
  traceback.
- If the build step (`create_environment` or the existence check) fails,
  `_persist_essentials` is never reached — no spec write, no kernel
  registration.
- `--ephemeral` short-circuits before `_persist_essentials`; the live env is
  fully usable via `mamba activate <name>` but no shelf spec exists and the
  kernel is not visible to JupyterLab.
- `--save` combinations that never reach the save step: with `--dry-run` the
  command returns at the print step, and with `--ephemeral` at the persist
  step — in both cases `--save` is **silently ignored** (the parser accepts
  the combination with no error) and no can is packed.
- Kernel registration failure: the command exits `1` *after* the shelf spec
  has been written (and, unless `--ephemeral`, after the live env was built);
  no exports are printed and the "ready" INFO line is not logged (see §5.2
  step 2c). The live env remains usable via `mamba activate <name>`, and the
  can can still be packed later via `hubenv save <name>`.
- Building into a non-writable pantry (or all default pantries read-only)
  returns `1` after a clear error; the build step (if any) still ran.

---

## 9. Pantry interaction

- All sources (unless `--dry-run` or `--ephemeral`) instantiate a
  `PantryStore` via `_build_store`:
  - With `--pantry PATH`: `PantryStore(paths=[Path(PATH)])`. The shelf spec
    is written under `PATH/shelves/<name>/nbw-wrangler-spec.yaml`.
  - Without: `PantryStore()` — uses the default `NBW_PANTRY_DIRS`; the first
    writable pantry is used.
- If no writable pantry is available, the command returns `1` with a clear
  error and the spec / kernel steps are skipped.
- `print_exports` uses `PantryStore.live_envs_root` (default `NBW_MM/envs`)
  to print `NBW_ENV_ROOT`.
- The live env is created at `NBW_MM/envs/<name>` by mamba itself.

---

## 10. Output (stdout) examples

### 10.1 `--from-empty --dry-run --name demo --python 3.11`

```yaml
name: demo
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - pip:
      - uv
      - pip
      - ipykernel
      - jupyter
      - cython
      - setuptools
      - wheel
```

### 10.2 `--from-requirements req.txt --name demo --python 3.11 --dry-run`
(if `req.txt` contains `numpy>=1.20` and `pandas`)

```yaml
name: demo
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - pip:
      - numpy>=1.20
      - pandas
      - uv
      - pip
      - ipykernel
      - jupyter
      - cython
      - setuptools
      - wheel
```

(The list under the inline `pip:` mapping is indented one level deeper than the
surrounding list, exactly as `ruamel.yaml` renders it — the two `- pip` lines
above are the conda `pip` *package*, the `pip:` line is the sub-dict holding the
pip *packages*.)

### 10.3 `--from-existing-env astro-py --name myproject --display-name "My Project"`
(success — after mamba export + pip freeze + shelf spec write + kernel register)

```
export NBW_ACTIVE_ENV=myproject
export NBW_ENV_ROOT=/home/user/.nbw-live/mm/envs/myproject
```

(Shown without `--save`; on stderr the closing INFO log line
`"Environment 'myproject' is ready. Kernel 'My Project' registered. Shelf spec: <path>"`
is followed by the WARNING save hint
`"Not archived yet. Run `hubenv save myproject` to create the restoreable can."`
With `--save`, the hint is replaced by the can packing (its INFO/ERROR output
per `hubenv-env-save.md` §6) and the closing INFO `"Environment 'myproject'
is archived and restorable."` on success.)

### 10.4 `--from-empty --name demo --ephemeral`

No exports are printed; the only user-visible effect is the INFO log
`"Environment 'demo' is ready (ephemeral). No shelf spec was written and no
kernel was registered."` on stderr.

---

## 11. What is NOT done (out of scope for the current implementation)

- No data archive download, no notebook-repo clone (those are `hubenv data`).
- No validation of the resulting live environment (`--from-*` install paths
  trust mamba to have succeeded).
- No confirmation prompt; creating an env whose shelf spec already exists
  overwrites the file unconditionally (`save_hubenv_spec` uses
  `mkdir(exist_ok=True)`).
- `--ephemeral` + `--from-existing-env` still runs the read-only probes
  (`mamba env export` + `pip freeze`); it only skips the spec write and
  kernel registration.
