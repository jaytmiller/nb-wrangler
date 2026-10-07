# Plan: Adapting `hubenv` to `nb_wrangler` Conventions

## Context

`docs/conventions.md` documents the coding conventions used throughout the
`nb_wrangler` package. Section 1 explicitly states that `nb_wrangler/hubenv`
**does not yet adhere** to these conventions and is **not** considered an
exemplar. This document lays out a phased plan to close that gap.

## Current State of `hubenv`

| Area | Current Pattern | Convention Violated |
|------|-----------------|---------------------|
| CLI    | `hubenv/parser.py` — subcommand-based `argparse` with `add_subparsers` | §1: `nb_wrangler/cli.py` uses a **flag-based** parser with domain-prefixed flags (`env_*`, `packages_*`, `test_*`, `data_*`, `spec_`) and **argument groups**, not subcommands |
| Configuration | `HubenvConfig` (a `WranglerLoggable` subclass) wraps `NBW_PANTRY_DIRS` / `NBW_ROOT`; **not** a `WranglerConfig` subclass; uses its own config object | §2.1–2.5: `WranglerConfig` dataclass is the single config class; `HubenvConfig` is explicitly described as a "separate path" and "not the pattern other code should follow" |
| Bootstrap | `hubenv/_common.py:ensure_config()` — creates a minimal fallback `WranglerConfig` and sets it as the singleton; this is described as the "hubenv workaround" | §2.5: `ensure_config()` is documented as a workaround, not a convention to emulate |
| Logging | Uses `WranglerLoggable` (via `HubenvConfig`) to get `self.logger`; user-facing output uses `print()` directly | §3.4: stdout should be kept clean; diagnostic output goes to the logger (stderr). The conventions explicitly mention `print_exports` in `_common.py` as an example of proper stdout usage |
| Entry point | `hubenv` → `nb_wrangler.hubenv.cli:main` (correct, per §5) | No violation — entry point mapping is correct in `pyproject.toml` |

## Constraint

`hubenv` is a **subcommand-based CLI** by design — users type `hubenv env create`,
`hubenv env save`, `hubenv var ls`, etc. The central `nb_wrangler` CLI (`nbw`)
uses a **flag-based** interface (`--env-pack`, `--env-unpack`, `--spec-add`, etc.).
These are fundamentally different UX models. The goal of this adaptation is
**not** to make `hubenv` into `nbw`, but to make `hubenv`'s internal
architecture follow the *spirit* of the conventions where possible: using
`WranglerConfig` + the `args_config` singleton for configuration, using the
logger for diagnostics and `print()` only for user-facing stdout output, and
keeping the parser construction centralized.

## Analysis: Pantry Code — Do NOT Merge Into `nb_wrangler/pantry.py`

Before defining the configuration refactor, a key decision was evaluated:
whether hubenv's pantry logic should be moved into `nb_wrangler/pantry.py`
(which already contains `NbwPantry`, `NbwPantrySet`, `NbwShelf` used by `nbw`).

**Conclusion: Not a sound improvement.** The two pantry models serve different
conceptual purposes:

| Aspect | `nb_wrangler/pantry.py` (`nbw` CLI) | `nb_wrangler/hubenv/config.py` (`hubenv` CLI) |
|--------|-------------------------------------|----------------------------------------------|
| Shelf identity | Named after wrangler spec (`spec_manager.shelf_name`) | Named after PPE env name (arbitrary user string) |
| Spec model | Each shelf has a `wrangler-spec.yaml` | No wrangler spec; env state in `.hubenv-spec.yaml` |
| Archive structure | `archives/` with `env-*`/`repo-*`/`data-*`; `notebook_repos/`, `data/` | `archives/last-save.sha256` hash marker |
| Operations | Curate, pack, unpack, install — tied to wrangler spec workflow | Create, save, restore, ensure, rm — standalone env lifecycle |
| Inheritance | `NbwShelf` inherits `WranglerLoggable` + `WranglerEnvable` | `HubenvConfig` inherits `WranglerLoggable` only |

Merging would:
- Bloat `NbwPantry`/`NbwShelf` with hubenv-specific concepts (restore-hash
  markers, PPE lifecycle) foreign to the wrangler spec workflow.
- Create method signature conflicts (hubenv returns `list[dict]`, `NbwPantrySet`
  prints and returns `bool`).
- Violate single-responsibility by coupling two different domain models.

**Recommended approach**: Keep hubenv's pantry logic in `hubenv/` — either as
the existing `HubenvConfig` (simplified to not be a config class) or extracted
to a dedicated `PantryStore` class. If hubenv needs to interoperate with
`NbwPantrySet`, it can instantiate it directly from `NBW_PANTRY_DIRS`.

---

## Phase 1: Configuration — Adopt `WranglerConfig` + `args_config` Singleton

**Goal**: Eliminate `HubenvConfig` as a config class; route configuration
through `WranglerConfig` + `args_config` singleton; extract pantry logic into
a separate store class.

### Steps

1. **Define hubenv-specific fields on `WranglerConfig`** (`nb_wrangler/config.py`)
   - Add `hubenv_command: str | None = None` — captures the subcommand path
     (e.g., `"env.create"`, `"var.ls"`).
   - Add `hubenv_args: argparse.Namespace | None = None` — holds the raw
     subcommand namespace so dispatch functions get their flags.
   - `quiet`, `verbose`, `debug`, `color`, `log_times` **already exist** on
     `WranglerConfig` — no changes needed.

2. **Add `hubenv_config_from_args()` factory** in `hubenv/config.py`
   - A standalone function (not a classmethod on `HubenvConfig`) that:
     - Constructs `WranglerConfig` with hubenv-specific fields populated.
     - Returns the config (caller does `set_args_config(config)`).

3. **Extract pantry logic to `PantryStore` class** in `hubenv/config.py`
   - Rename `HubenvConfig` → `PantryStore` (or keep `HubenvConfig` as a
     compatibility alias).
   - `PantryStore` is **not** a config class — it's a helper that takes
     `NBW_PANTRY_DIRS` and `NBW_ROOT` (from `constants.py`) and provides:
     `writable_pantries()`, `first_writable_pantry()`, `target_pantry()`,
     `find_shelves()`, `list_shelves()`, `list_live_envs()`,
     `hubenv_spec_path()`, `restore_hash_path()`.
   - `PantryStore` inherits `WranglerLoggable` (for logging) but is
     instantiated explicitly: `PantryStore()`, not via singleton.
   - `NBW_PANTRY` is intentionally not merged with `NbwPantrySet` (see
     analysis above).

4. **Remove `_common.py:ensure_config()` workaround**
   - The `ensure_config()` function creates a "minimal fallback"
     `WranglerConfig` when no `args_config` is set. This is documented as a
     workaround.
   - Instead, `cli.py:main` should **always** build a `WranglerConfig` from
     the parsed args and call `set_args_config()` before dispatching. There
     should be no fallback path — if config isn't set,
     `get_args_config()` should raise `AssertionError("Premature fetch ...")`
     as designed.
   - Command handlers that need config should call `get_args_config()` and
     read `.hubenv_command`, `.hubenv_args`, `.quiet`, etc.

### Files to modify
- `nb_wrangler/config.py` — add `hubenv_command` and `hubenv_args` fields
- `nb_wrangler/hubenv/config.py` — refactor: extract pantry methods to
  `PantryStore`, add `HubenvConfig.from_args`, or replace with a factory
  function
- `nb_wrangler/hubenv/_common.py` — remove or rewrite `ensure_config()`
- `nb_wrangler/hubenv/cli.py` — call `set_args_config()` early in `_main`

## Phase 2: CLI — Add Global Flags + Argument Groups

**Goal**: Add the global flags (`--quiet`, `--verbose`, `--debug`, `--color`,
`--log-times`) to the hubenv parser so `WranglerConfig.from_args` can read them,
and organize subcommands into argument groups matching the domain-prefixed
pattern where it makes sense.

### Steps

1. **Add global flags to `build_parser()`** in `hubenv/parser.py`
   - Add `--quiet` / `-q` (`action="store_true"`, `dest="quiet"`).
   - Add `--verbose` (`action="store_true"`, `dest="verbose"`).
   - Add `--debug` (`action="store_true"`, `dest="debug"`).
   - Add `--color` (`choices=["auto", "on", "off"]`, `default="auto"`,
     `dest="color"`).
   - Add `--log-times` (`choices=["none", "normal", "elapsed", "both"]`,
     `default="elapsed"`, `dest="log_times"`).
   - Add `--reset-log` (`action="store_true"`, `dest="reset_log"`).
   - These should go in a top-level "Global" argument group, not on
     subparsers, so they work as `hubenv --quiet env ls` and
     `hubenv env --quiet ls` (argparse allows global flags at the top level
     before the subcommand).

2. **Add a global `--version` flag**
   - `hubenv --version` should print the nb-wrangler version (from
     `constants.__version__`) and exit, matching the `nbw` CLI convention.

3. **Argument group organization**
   - The subcommands (`env`, `var`, `data`) already map to domain concepts.
     The argument group names in `build_parser()` should use domain-prefixed
     labels where they add clarity (e.g., "Environment Management" for `env`,
     "Data Management" for `data`). This is already mostly done; just ensure
     consistency.

### Files to modify
- `nb_wrangler/hubenv/parser.py` — add global flags + argument groups
- `nb_wrangler/hubenv/cli.py` — handle `--version` before dispatch

## Phase 3: Logging — Use Logger for Diagnostics, `print()` Only for stdout

**Goal**: Ensure all diagnostic/warning/error output goes through the logger
(stderr), and `print()` is reserved for user-facing stdout output (e.g.,
exports, table/json output).

### Steps

1. **Audit all `print()` calls** in `hubenv/` command modules
   - Identify which `print()` calls are:
     - **(a)** User-facing stdout (e.g., `print_exports`, table output, JSON
       output) — **keep** as `print()`.
     - **(b)** Diagnostic messages (errors, warnings, info) — **change** to
       `self.logger.error(...)` / `self.logger.warning(...)` /
       `self.logger.info(...)`.

2. **Ensure command modules use `WranglerLoggable` or `WranglerConfigurable`**
   - Command modules are currently standalone functions (e.g.,
     `cmd_env_create(args)`) that create `HubenvConfig()` directly.
   - They should instead get config + logger from the singleton:
     ```python
     from nb_wrangler.config import get_args_config
     from nb_wrangler.logger import get_configured_logger

     def cmd_env_create(args):
         config = get_args_config()
         logger = get_configured_logger()
         ...
     ```
   - Or, if command handlers are refactored into classes, inherit from
     `WranglerLoggable` + `WranglerConfigurable`.

3. **Remove `HubenvError` from `print()` usage**
   - `HubenvError` currently prints to stderr via `print(f"hubenv: {exc.message}",
     file=sys.stderr)`. This should use the logger:
     ```python
     except HubenvError as exc:
         logger.error(exc.message)
         return exc.exit_code
     ```
   - (Or keep the `print(..., file=sys.stderr)` pattern but note that this
     bypasses the logger's color/timestamps. The convention prefers the logger
     for all non-stdout diagnostic output.)

### Files to modify
- `nb_wrangler/hubenv/cli.py` — use logger for error handling
- `nb_wrangler/hubenv/env_create.py`
- `nb_wrangler/hubenv/env_save.py`
- `nb_wrangler/hubenv/env_restore.py`
- `nb_wrangler/hubenv/env_ls.py`
- `nb_wrangler/hubenv/env_info.py`
- `nb_wrangler/hubenv/env_pkg.py`
- `nb_wrangler/hubenv/env_relock.py`
- `nb_wrangler/hubenv/env_rm.py`
- `nb_wrangler/hubenv/env_ensure.py`
- `nb_wrangler/hubenv/env_save.py`
- `nb_wrangler/hubenv/env_restore.py`
- `nb_wrangler/hubenv/export.py`
- `nb_wrangler/hubenv/var.py`
- `nb_wrangler/hubenv/data.py`
- `nb_wrangler/hubenv/status.py`
- `nb_wrangler/hubenv/doctor.py`

## Phase 4: `WranglerLogger` Return Values

**Goal**: Adopt the convention where `logger.error()` returns `False` and
`logger.warning()` returns `True`, used for short-circuit control flow.

### Steps

1. Audit command handlers for control flow based on `print()` + `return 1`.
2. Replace with `return self.logger.error(...)` pattern where appropriate:
   ```python
   if not some_condition:
       return logger.error("Something went wrong")
   return False
   ```
3. Replace with `return self.logger.info(...)` pattern where appropriate:
```python
if condition:
    logger.info(...)
    return True
```

4. Replace with `return self.logger.warning(...)` pattern where appropriate:
```python
if condition:
    logger.warning(...)
    return True
```

## Phase 5: Documentation Updates

**Goal**: Update `docs/conventions.md` to remove the exclusion clause for
`hubenv` and document the hubenv-specific patterns.

### Steps

1. **Section 1 (Introduction)**: Remove or rewrite the sentence stating that
   `hubenv` does not adhere to conventions. Replace with: "`hubenv` follows the
   same CLI, configuration, and logging conventions as the main `nb_wrangler`
   package, with additional subcommand-based dispatch (see §8)."

2. **Add Section 8: `hubenv` Subcommand CLI**
   Document that:
   - `hubenv` uses subcommand-based argparse (`hubenv env create`, etc.) as a
     different UX model from the flag-based `nbw` CLI.
   - Global flags (`--quiet`, `--verbose`, `--debug`, `--color`, `--log-times`)
     are available on the top-level parser.
   - Configuration flows through `WranglerConfig` + `args_config` singleton,
     with `hubenv_command` and `hubenv_args` fields capturing the subcommand
     path and namespace.
   - Pantry operations are handled by a `PantryStore` class (or equivalent),
     separate from `WranglerConfig`.
   - Error handling uses `HubenvError` for clean exit codes, with the logger
     for diagnostic output.

3. **Section 2.5 (hubenv Configuration)**: Update to reflect that `HubenvConfig`
   is no longer a separate config class — `WranglerConfig` is used for all
   configuration, and pantry operations are handled by a separate store class.

4. **Section 7 (Where Not to Look)**: The code matching nb_wrangler/\*.py is the exemplar of conventions.  The code matching nb_wrangler/hubenv/\*.py should be updated to the conventions of the exemplars.

## Phase 6: Tests

**Goal**: Ensure tests cover the new configuration and logging patterns.

### Steps

1. **Add tests for `WranglerConfig` with hubenv fields**
   - Test `WranglerConfig` with `hubenv_command` set.
   - Test `get_args_config()` / `set_args_config()` lifecycle in hubenv context.

2. **Add tests for pantry store**
   - Test `PantryStore.writable_pantries()`, `first_writable_pantry()`,
     `find_shelves()`, `list_shelves()`, `list_live_envs()` using fake/temp
     directories.

3. **Add tests for global flags**
   - Test `hubenv --quiet env ls` suppresses log output.
   - Test `hubenv --version` prints version and exits.
   - Test `hubenv --color off` disables color.

4. **Verify existing hubenv tests still pass** (if any exist in `tests/`).

## Execution Order

| Order | Phase | Priority | Description |
|-------|-------|----------|-------------|
| 1 | Phase 1 (Config) | High | Foundation — everything depends on config |
| 2 | Phase 2 (CLI) | High | Adds global flags needed by config and logging |
| 3 | Phase 3 (Logging) | Medium | Depends on config being set up |
| 4 | Phase 4 (Return values) | Low | Incremental improvement |
| 5 | Phase 5 (Docs) | Medium | Can be done in parallel, but final version reflects actual changes |
| 6 | Phase 6 (Tests) | High | Verify all changes |

## Risk Assessment

- **Breaking change**: Removing `HubenvConfig` is a breaking change for any
  external code that imports it. Mitigation: keep a thin compatibility shim
  that delegates to `WranglerConfig` + `PantryStore` and emits a deprecation
  warning.
- **Subcommand UX**: Do not convert subcommands to flags. The subcommand model
  is intentional for `hubenv`. The plan adapts the *internal architecture*,
  not the *user interface*.
- **Circular imports**: `hubenv/config.py` already imports from
  `nb_wrangler.config` and `nb_wrangler.logger`. Ensure the new
  `PantryStore` class doesn't create circular import chains.