# Plan: Address Poor Radon Score of `nb_wrangler/ppe/cli.py`

## Current State

`nb_wrangler/ppe/cli.py` is a **2,543-line** monolith with **69 top-level definitions**
(68 functions + 1 class). Its radon metrics are poor:

| Metric | Value | Interpretation |
|---|---|---|
| MI (Maintainability Index) | **C (0.00)** | Severely unmaintainable |
| CC complexity grade C functions | 3 | `_dispatch_env`, `_cmd_env_restore`, `_cmd_env_rm` |

### Root Causes

1. **Giant single module** — all subcommand groups are in one file, making it
   impossible to navigate and inherently lowering MI.
2. **Long dispatch chains** — `_dispatch_env` uses 13 `if/elif` branches
   (grade C) to route to env subcommands.
3. **Complex command handlers** — `_cmd_env_restore` and `_cmd_env_rm`
   interleave multiple concerns (config, safety checks, execution, output,
   idempotency) leading to high cyclomatic complexity.
4. **Helper functions buried inline** — spec-manipulation helpers, dry-run
   builders, and table formatters are interspersed with command handlers
   rather than co-located by feature.

### Backward-Compatibility Constraints

228 references to `nb_wrangler.ppe.cli` exist in the test suite and must keep
working unless tests are updated:

- `from nb_wrangler.ppe.cli import main` — used everywhere
- `from nb_wrangler.ppe.cli import build_parser` — used everywhere
- `from nb_wrangler.ppe.cli import _spec_to_requirements`, `_spec_to_wrangler`,
  `_extract_python_version`, `_split_conda_pip`, `_is_safe_rm_path` — imported
  directly by tests
- `patch("nb_wrangler.ppe.cli._compile_pip_packages")`,
  `patch("nb_wrangler.ppe.cli.sha256_file")`,
  `patch("nb_wrangler.ppe.cli.data_manager.*")` — patched at the module path
- `patch("nb_wrangler.ppe.cli._list_kernelspecs")`,
  `patch("nb_wrangler.ppe.cli._check_mamba_availability")`,
  `patch("nb_wrangler.ppe.cli._check_pantry_writability")`,
  `patch("nb_wrangler.ppe.cli._check_efs_mount")`,
  `patch("nb_wrangler.ppe.cli._check_kernel_json_sanity")` — patched in doctor tests
- `pyproject.toml` entry point: `ppe = "nb_wrangler.ppe.cli:main"`

## Proposed Solution: Partition Into Subcommand Modules

### New Module Layout (`nb_wrangler/ppe/`)

| New Module | Lines (est.) | Purpose |
|---|---|---|
| `cli.py` | ~120 | Thin facade: `main()`, `PpeError`, `build_parser()` + dispatch, re-exports |
| `parser.py` | ~200 | `build_parser()` + all `_add_*_args`/`_add_*_subcommands` functions |
| `env_args.py` | ~160 | `_add_env_subcommands`, `_add_rm_args`, `_add_ensure_args`, etc. |
| `var_args.py` | ~120 | `_add_var_subcommands`, `_add_var_ls_args`, `_add_var_add_args`, `_add_var_rm_args` |
| `data_args.py` | ~100 | `_add_data_subcommands`, `_add_data_ls_args`, etc. |
| `var.py` | ~180 | `dispatch`, `cmd_var_ls`, `cmd_var_add`, `cmd_var_rm` + helpers |
| `data.py` | ~120 | `dispatch`, `cmd_data_ls`, `cmd_data_download`, etc. |
| `env_create.py` | ~130 | `cmd_env_create`, `_build_seed_dict`, `_import_existing_env`, spec-saving helpers |
| `env_save.py` | ~60 | `cmd_env_save`, `_persist_save_hash`, `_print_no_writable_pantry` |
| `env_restore.py` | ~100 | `cmd_env_restore`, `_find_restore_shelf`, `_read_save_hash`, `_write_at_boot_snippet` |
| `env_ls.py` | ~80 | `cmd_env_ls`, `_print_ls_table`, `_print_ls_json`, `_print_shadowing_warnings` |
| `env_info.py` | ~70 | `cmd_env_info`, `_print_info_table`, `_print_info_json` |
| `env_pkg.py` | ~120 | `cmd_env_install`/`uninstall`, `_do_pkg_action`, `_run_*_action`, dry-run helpers |
| `env_spec.py` | ~100 | `_load_ppe_spec`, `_save_ppe_spec`, `_update_and_save_spec`, `_update_spec_packages`, list-manipulation helpers |
| `env_relock.py` | ~80 | `cmd_env_relock`, `_do_relock`, `_compile_pip_packages`, `_read_compiled_versions` |
| `env_rm.py` | ~110 | `cmd_env_rm`, `_resolve_rm_targets`, `_is_safe_rm_path`, `_do_rm`, cleanup |
| `env_ensure.py` | ~60 | `cmd_env_ensure`, `cmd_env_register`, `cmd_env_unregister`, `_EnsureArgs` |
| `export.py` | ~110 | `cmd_export`, `_format_export`, `_spec_to_requirements`, `_spec_to_wrangler`, spec conversion |
| `status.py` | ~100 | `cmd_status`, `_aggregate_status`, `_build_status_envs`, table/json output |
| `doctor.py` | ~180 | `cmd_doctor`, `_run_doctor_checks`, `_check_*`, `_detect_efs_mount`, kernel checks |
| `completions.py` | ~15 | `cmd_completions` (rename existing `completions.py` module's content or delegate) |

> **Note:** `completions.py` already exists and holds `generate_completion`. The
> `cmd_completions` function will move to a new `completions_cmd.py` module to
> avoid a name clash.

### Backward-Compatibility Strategy

`cli.py` becomes a **thin facade** that:

1. Keeps `main()` and `PpeError` defined locally (or re-exported).
2. Re-exports `build_parser` from `parser.py`.
3. Re-imports (with `from … import *` or explicit `from … module import func`)
   every function that tests import directly or patch:
   - `_compile_pip_packages`, `_do_relock` ← from `env_relock.py`
   - `sha256_file` ← re-imported from `nb_wrangler.utils` (it's already imported there)
   - `data_manager` ← re-imported from `nb_wrangler`
   - `_list_kernelspecs`, `_check_mamba_availability`, `_check_pantry_writability`,
     `_check_efs_mount`, `_check_kernel_json_sanity` ← from `doctor.py`
   - `_spec_to_requirements`, `_spec_to_wrangler`, `_extract_python_version`,
     `_split_conda_pip` ← from `export.py`
   - `_is_safe_rm_path` ← from `env_rm.py`

This ensures all existing `patch("nb_wrangler.ppe.cli.X")` and
`from nb_wrangler.ppe.cli import X` references remain valid.

### Complexity Reduction per Problem Function

#### `_dispatch_env` (grade C → B)
Replace the 13-branch `if/elif` chain with a **dispatch dict**:

```python
_ENV_DISPATCH = {
    "create":   cmd_env_create,
    "save":     cmd_env_save,
    "restore":  cmd_env_restore,
    "ls":       cmd_env_ls,
    "info":     cmd_env_info,
    "install":  cmd_env_install,
    "uninstall":cmd_env_uninstall,
    "relock":   cmd_env_relock,
    "rm":       cmd_env_rm,
    "ensure":   cmd_env_ensure,
    "register": cmd_env_register,
    "unregister": cmd_env_unregister,
}
```

This converts 13 branches into a single dict lookup + call.

#### `_cmd_env_restore` (grade C → B)
Split into focused helpers:

| New function | Responsibility |
|---|---|
| `_cmd_env_restore` (simplified) | Orchestrate: ensure config, find shelf, delegate steps |
| `_check_restore_archive` | Validate can-path exists, print error |
| `_check_idempotent_skip` | Idempotency hash comparison |
| `_do_restore_unpack` | Unpack + record hash + register kernel |

#### `_cmd_env_rm` (grade C → B)
Split into focused helpers:

| New function | Responsibility |
|---|---|
| `_cmd_env_rm` (simplified) | Orchestrate: resolve → dry-run → safety → execute |
| `_validate_rm_targets` | Check readonly + safe-path (returns error list) |
| `_confirm_and_rm` | Prompt + execute + return result |

### Implementation Steps

1. **Create the new module files** — one branch at a time, copying functions
   from `cli.py` with minimal changes (rename `_` prefix to public if desired,
   but keep `_`-prefixed names for backward compatibility).

2. **Refactor complex dispatch functions** — convert `_dispatch_env` and
   `_dispatch_data`/`_dispatch_var` to dict-based dispatch.

3. **Reduce `_cmd_env_restore` and `_cmd_env_rm`** by extracting helpers.

4. **Rewrite `cli.py` as a thin facade** — keep `main()` + `PpeError`, import
   everything from submodules, re-export patched functions.

5. **Update test patch paths** — where tests patch
   `nb_wrangler.ppe.cli.X`, either keep the re-export in `cli.py` OR update
   the test to patch the new module path (preferred for long-term clarity).

6. **Run lint + tests** — `make lint/radon`, `make unit-test` for ppe tests.

7. **Verify entry point** — `ppe --help` works via `pyproject.toml` entry point.

### Files Created/Modified

- **Created (19 new files):** all modules listed above
- **Modified:** `nb_wrangler/ppe/cli.py` (rewritten as facade, ~120 lines)
- **Modified:** `tests/ppe/*.py` (update patch/import paths where appropriate)
- **Modified:** `pyproject.toml` (no change needed — entry point stays
  `nb_wrangler.ppe.cli:main`)

### Expected Outcome

| Metric | Before | After (target) |
|---|---|---|
| MI score | C (0.00) | A (40+) |
| Grade C functions | 3 | 0 |
| `cli.py` lines | 2,543 | ~120 |
| Largest module | 2,543 | ~200 |
| Average module SLOC | N/A | ~100-150 |