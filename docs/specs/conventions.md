# Project Conventions

This document captures the coding conventions for command-line parsing, configuration management, and logging used throughout the `nb_wrangler` package (excluding `nb_wrangler/hubenv`, which does not yet adhere to these conventions).

## Scope

The conventions below are derived from the following source files:

| Concern        | Key Files                                              |
|----------------|--------------------------------------------------------|
| CLI parsing    | `nb_wrangler/cli.py`, `nb_wrangler/__main__.py`        |
| Configuration  | `nb_wrangler/config.py`                                |
| Logging        | `nb_wrangler/logger.py`                                |
| Constants      | `nb_wrangler/constants.py`                             |
| Entry points   | `pyproject.toml`                                       |

The `nb_wrangler/hubenv` subpackage uses a different CLI architecture (subcommand parsers in `hubenv/parser.py`) and a separate `HubenvConfig` (`hubenv/config.py`). It is **not** considered an exemplar of `nb_wrangler` conventions and is intentionally excluded from the mappings below.

---

## 1. Command-Line Parsing (CLI)

### 1.1 Framework and Structure

- **Library**: `argparse` from the Python standard library (`nb_wrangler/cli.py:1`).
- **Parser factory**: All argument definitions are centralized in `build_parser()`, which returns the fully populated `ArgumentParser`. New arguments should be added here (or in helper functions it calls), not scattered in `main` or command modules.
- **Entry point**: `cli.py:main` parses `argv` (defaulting to `sys.argv[1:]`), dispatches to the appropriate handler, and returns `0` on success or non-zero on failure. `nb_wrangler/__main__.py` delegates to `cli:main` so `python -m nb_wrangler` works.

### 1.2 Argument Styles

- **Flags**: Boolean options use `action="store_true"` with `dest` derived from the flag's long form (e.g., `--dev` → `args.dev`).
- **Choices**: Enum-like options use `choices=[...]`, e.g., a `--color` option that accepts `["auto", "on", "off"]`.
- **Nargs**: List-valued options use `nargs="*"` (zero or more) or `nargs="+"` (one or more) depending on whether the argument is required.
- **Metavars**: Positional or value-bearing arguments use explicit `metavar` strings so usage messages read cleanly (e.g., `metavar="WORKFLOW"`).
- **Required groups**: Mutually exclusive or required selections (e.g., seed sources in `hubenv/parser.py:_add_create_args`) use `add_mutually_exclusive_group(required=True)`.

### 1.3 Workflow Flags

- Workflow flags are **prefixed by domain** (`env_`, `packages_`, `test_`, `data_`, `spec_`) and map 1:1 to steps in a workflow pipeline. This makes the mapping from CLI flag to workflow step explicit and grep-able.
- Flags default to `False`/`None`/`""`/empty-list, so a default run performs no side-effecting steps. Workflows are activated only when a flag is set.
- Example: `--env-init` sets `args.env_init = True`; `WranglerConfig.from_args` reads that field and stores it on the config object, which the wrangler inspects to decide whether the "initialize environment" step runs.

### 1.4 Argument Groups

- `argparse` argument groups are used to organize help output into logical sections (e.g., "environment management", "packages", "testing"). Each group typically contains domain-prefixed flags.
- Custom help strings use sentence-style descriptions without a trailing period for short `--help` text, and full sentences (often with "default:" hints) for longer descriptions.

### 1.5 Defaults and Types

- Default values are specified inline at the `add_argument` call (e.g., `default=False`, `default="."`).
- `from_args` performs light post-processing: converting path strings to `Path` objects, stripping/splitting whitespace-joined lists (e.g., `spi_image_test` is `.strip().split()` if a string, or passed through if already a list), and computing derived booleans (e.g., `prod` is set to `True` unless `--dev` is also `True`).
- `str` defaults for paths (e.g., `.repos_dir`) are stored as strings on the config dataclass, with `Path` construction deferred to the consumer — this avoids `Path` serialization issues if the config is ever dumped.

---

## 2. Configuration Management

### 2.1 The `WranglerConfig` Dataclass

- **Location**: `nb_wrangler/config.py`.
- **Pattern**: `WranglerConfig` is a `dataclass` (decorated with `@dataclass`) that holds all runtime configuration for a single invocation. Fields include `workflows`, `repos_dir`, `output_dir`, `prod`, `jobs`, `timeout`, and one field per workflow flag.
- **Defaults**: Simple defaults are expressed as dataclass field defaults (e.g., `jobs: int = 1`, `timeout: int = DEFAULT_TIMEOUT`). Path and mutable defaults use `field(default_factory=...)` or are set to `None` and resolved in `__post_init__`.
- **Post-init**: `__post_init__` normalizes fields that need derived values (e.g., resolving `repos_dir` to an absolute `Path`).

### 2.2 The Singleton Pattern: `args_config`

- A module-level global `args_config: WranglerConfig | None` holds the single active configuration for the process.
- **Access**: `set_args_config(cfg)` stores it; `get_args_config()` retrieves it and **asserts** it has been set (raising `AssertionError("Premature fetch ...")` if not). This prevents accidental use of a half-initialized config.
- **Lifecycle**: `main` (or a test) calls `WranglerConfig.from_args(args)` → `set_args_config(...)` early, before any component that needs config. From that point on, any module can call `get_args_config()`.
- **Why it matters**: Components like `WranglerLoggable`, `WranglerConfigurable`, and `EnvironmentManager` use `get_args_config()` to read their settings rather than receiving config via constructor arguments. This keeps call signatures clean but means config **must** be set before any of these classes are instantiated.

### 2.3 `from_args` Mapping

- `WranglerConfig.from_args(args: argparse.Namespace) -> WranglerConfig` is the bridge between the argparse namespace and the config dataclass.
- It reads attributes from the `Namespace` by name (e.g., `args.jobs`, `args.dev`, `args.timeout`) and passes them to the `WranglerConfig` constructor.
- It is the single place where CLI-specific post-processing (type coercion, derived flags, default overrides) lives. When adding a new CLI flag, add the corresponding dataclass field and a mapping line here.

### 2.4 `WranglerConfigurable` and `WranglerLoggable`

- These **mixins** (defined in `config.py` and `logger.py`, respectively) provide `self.config` and `self.logger` to any class that inherits them. Both call `get_args_config()` in `__init__` (via `super().__init__()`), so any class using them **must** ensure `set_args_config` has been called first.
- `WranglerConfigurable` gives `self.config` and `self.spec_manager` (from the config's spec file).
- `WranglerLoggable` gives `self.logger` (a `WranglerLogger` instance configured from the config).
- `EnvironmentManager` (in `environment.py`) inherits both, so it gets config + logger for free. The same pattern applies to `NotebookWrangler`, `DataWrangler`, and other wrangler classes (see `wrangler_mixin.py`, which documents the required attributes: `config`, `logger`, `spec_manager`, `env_manager`).

### 2.5 `hubenv` Configuration (Separate Path)

- `HubenvConfig` (in `hubenv/config.py`) is a different, simpler class that wraps `NBW_PANTRY_DIRS` and `NBW_ROOT` constants from `nb_wrangler/constants.py`. It is **not** a `WranglerConfig` subclass and does **not** use the `args_config` singleton.
- `hubenv` commands obtain a `WranglerConfig` via `hubenv/_common.py:ensure_config()`, which either fetches the existing `args_config` or creates a minimal fallback and sets it. This is the hubenv workaround and is **not** the pattern other code should follow.

---

## 3. Logging

### 3.1 Logger Class

- **Location**: `nb_wrangler/logger.py`.
- **`WranglerLogger`**: A subclass of `logging.Logger` that adds application-specific behavior.
- **Instantiation**: Created via ` WranglerLogger.from_config(config)`, which reads `config.verbose`, `config.quiet`, `config.debug`, `config.log_times`, and `config.color` to set up handlers and formatters.
- **Singleton-like**: The logger is a module-level singleton accessed via `WranglerLogger.from_config(config)` (called once during config setup) and stored on `WranglerLoggable` instances as `self.logger`. Direct instantiation with flags (e.g., `WranglerLogger(quiet=True)`) is also supported for tests.

### 3.2 Log Levels and Quiet Mode

- `quiet=True` sets the root logger level to `WARNING` (so `INFO` and `DEBUG` messages are suppressed on stderr), but **does not** suppress `print()` to stdout. This is important: user-facing output (e.g., environment names, specs) goes through `print()`, while diagnostic output goes through the logger.
- `debug=True` enables `DEBUG`-level logging and includes timestamps.
- `verbose` is accepted as a config option but the logger primarily distinguishes quiet vs. non-quiet; verbose output is controlled by the level set from debug.

### 3.3 Color Modes

- The `color` config option accepts three values: `"auto"` (default), `"on"`, `"off"`.
- `ColorAndTimeFormatter` resolves `"auto"` by checking `sys.stderr.isatty()`: color is enabled only when stderr is a TTY.
- `"on"` forces color on regardless of TTY; `"off"` forces it off. An `AssertionError` is raised for any other value (`ColorAndTimeFormatter.__post_init__`).
- Color is applied to log message **levels** (INFO, WARNING, ERROR, etc.) via the `LEVEL_COLORS` dict, and to message prefixes via `ANSI_COLORS` (e.g., `"red-foreground"`).

### 3.4 Log Output and the Log File

- By default, log output goes to **stderr** (not stdout), so `stdout` is kept clean for machine-readable output that might be `eval`'d (e.g., `print_exports` in `hubenv/_common.py` prints `export` lines to stdout).
- A log file (`LOG_FILE`, defined in `constants.py`) may be used for debug logging when `debug=True`, capturing additional detail without cluttering the terminal.

### 3.5 Return Values

- Logger methods return booleans for use in short-circuit control flow: `logger.error(msg)` returns `False`, `logger.warning(msg)` returns `True`, `logger.info(msg)` returns `True`. Workflow steps use this pattern: `return self.logger.error("...")` immediately stops the workflow on failure.

### 3.6 Errors and Exceptions

- `WranglerLogger` accumulates `errors`, `warnings`, and `exceptions` on the instance during a run. `logger.exception(e, prefix)` both logs the exception and appends it to `logger.errors` (so it gets reported in a summary) and `logger.exceptions` (for debugging).
- `logger.elapsed_time` is a property that returns a formatted time string, used in debug summaries.

---

## 4. Constants and Shared Definitions

- **Location**: `nb_wrangler/constants.py`.
- **Purpose**: Central registry for default paths (`NBW_ROOT`, `NBW_PANTRY`, `NBW_MM`, `NBW_CACHE`, `NBW_PANTRY_DIRS`), command name constants (`CURATOR_COMMAND`, `MAMBA_COMMAND`, `PIP_COMMAND`), mode strings (e.g., `"pantry"` for `data_env_vars_mode`), and timeout constants (`DEFAULT_TIMEOUT`, `ENV_CREATE_TIMEOUT`, `INSTALL_PACKAGES_TIMEOUT`, `IMPORT_TEST_TIMEOUT`).
- **How to use**: Modules import specific names from `constants.py` (e.g., `from .constants import NBW_ROOT, DEFAULT_TIMEOUT`). New defaults should go here, not in individual modules.

---

## 5. Entry Points (`pyproject.toml`)

- **`nbw`**: Maps to `nb_wrangler.cli:main` — the main wrangler CLI.
- **`hubenv`**: Maps to `nb_wrangler.hubenv.cli:main` — the separate environment-management CLI.

---

## 6. Workflow Execution Pattern

The core wrangler classes (`NotebookWrangler`, `DataWrangler`) follow this pattern:

1. **`run_workflow(name, steps, continue_on_failure=False)`**: Logs the start, iterates over `steps` (no-argument callables returning `bool`), and short-circuits on the first `False` (unless `continue_on_failure=True`).
2. **Each step** calls subcommands via `EnvironmentManager.wrangler_run` or `env_run`, then uses `handle_result` to convert `CompletedProcess` results into success/failure booleans with appropriate log messages.
3. **Shared logic** lives in `WranglerWorkflowMixin` (`wrangler_mixin.py`), which provides `run_workflow`, `_get_environment_vars`, and `_register_environment`. It declares the type annotations (`spec_manager`, `config`, `logger`, `env_manager`) that subclasses must provide, and documents the required properties (`resolved_kname`, `resolved_environment_name`).

---

## 7. Where Not to Look for Conventions

The following paths deliberately deviate from the above and should **not** be used as references for new `nb_wrangler` code:

- `nb_wrangler/hubenv/**` — uses `hubenv/parser.py` for subcommand-based argparse, `HubenvConfig` instead of `WranglerConfig`, and `print()` for user output rather than following the mixed `print`/logger split. This is an intentional future-refactor target, not a convention to emulate.