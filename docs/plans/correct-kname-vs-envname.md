# Plan: Resolve `kernel_name` / `env_name` Concerns in nb-wrangler

## Overview

The root cause of most Points of Concern is that **kernel name** (a Jupyter concept for which kernel a notebook launches) and **environment name** (a conda/micromamba concept for the isolated environment) are treated as the same string throughout the codebase, with an undocumented exception (`python3` kernel → `base` env). This plan aims to:

1. **Separate the two concepts explicitly** in the code.
2. **Fix the known exception** (`python3` → `base`) consistently across all code paths.
3. **Fix the case-sensitivity mismatch** between conda env operations and Jupyter kernelspec operations.
4. **Fix the suffix-matching ambiguity** in `environment_exists`.
5. **Eliminate code duplication** by consolidating the kernel name resolution logic into a single canonical source.

## Phase 1: Introduce Explicit Env Name Semantics

### 1.1 Add a canonical `environment_name` concept on `SpecManager`

**File:** `nb_wrangler/spec_manager.py`

Add a new property `environment_name` that is the authoritative conda/micromamba environment identifier, distinct from `kernel_name`:

```python
@property
def kernel_name(self) -> str | None:
    """The Jupyter kernel name as it appears in notebook metadata."""
    ...  # existing logic (unchanged)

@property
def environment_name(self) -> str | None:
    """The conda/micromamba environment name used for environment operations.
    
    Normally identical to kernel_name, but follows the convention that the
    'python3' kernel and 'base' conda environment refer to the same thing.
    """
    kname = self.kernel_name
    if kname == "python3":
        return "base"
    return kname
```

**Rationale:** This moves the `python3 → base` mapping from `NotebookWrangler.env_name` into `SpecManager`, making it accessible to all consumers (`DataWrangler`, `Compiler`, etc.) consistently.

### 1.2 Deprecate `NotebookWrangler.env_name` and add `environment_name`

**File:** `nb_wrangler/wrangler.py`

Deprecate the `env_name` property and add a new `environment_name` property:

```python
import warnings

@property
def env_name(self):
    """Deprecated alias for environment_name.
    
    Kept for backward compatibility; will be removed in a future version.
    Use `environment_name` instead.
    """
    warnings.warn(
        "NotebookWrangler.env_name is deprecated and will be removed in a "
        "future version. Use environment_name or resolved_environment_name "
        "instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return self.environment_name

@property
def environment_name(self):
    """Conda/micromamba environment name (may differ from kernel_name for 'python3')."""
    return self.spec_manager.environment_name if self.spec_manager else None
```

**Impact on semantics:** `env_name` returning `"base"` for `kernel_name == "python3"` is now the **canonical** behavior, defined in one place. All code paths that previously used `env_name` should be updated to use `environment_name`. External scripts using `env_name` will see a `DeprecationWarning` but continue to work.

### 1.3 Centralize `resolved_kernel_name` and `resolved_environment_name` in the wrangler

**File:** `nb_wrangler/wrangler.py`

Refactor `resolved_kname` to use the canonical `environment_name`:

```python
@property
def resolved_kname(self) -> str | None:
    """Highest-priority available kernel name (kernel_name, not env_name)."""
    return (
        self.compiled_kernel_name
        or self.spec_manager.get_output_data("kernel_name")
        or self.spec_manager.kernel_name
    )

@property
def resolved_environment_name(self) -> str | None:
    """Highest-priority available environment name (with python3→base mapping)."""
    return kernel_name_to_env_name(self.resolved_kname)
```

**Key change:** `resolved_kname` no longer falls back to `env_name` (which had the mapping). It now resolves to the raw kernel name. Environment operations should use `resolved_environment_name`.

### 1.4 Update `DataWrangler.resolved_kname` to use `SpecManager.environment_name`

**File:** `nb_wrangler/data_wrangler.py`

```python
@property
def resolved_kname(self) -> str | None:
    """Helper to get kernel name, matching NotebookWrangler logic."""
    if self.compiled_kernel_name is not None:
        return self.compiled_kernel_name
    if not self.spec_manager:
        return None
    return self.spec_manager.get_resolved_kernel_name()
```

**Decision point:** DataWrangler's `_register_environment` calls `register_environment(kname, ...)` where the first arg is used as both the conda env name (for `env_run`) and the Jupyter `--name`. It should use `environment_name`.

## Phase 1.5: Fix `RequirementsCompiler` to Use Resolved Environment Name

### 1.5.1 Update compiler internal state to use environment name consistently

**File:** `nb_wrangler/compiler.py`

The `RequirementsCompiler` has several methods that work with environment names but currently use `self.spec_manager.kernel_name` in places where the environment name is needed. The compiler should be updated to:

1. Use `kernel_name_to_env_name()` for `env_run` calls (lines 135, 144) — these run commands in the target environment, so they need the environment name
2. Use `spec_manager.get_resolved_environment_name()` for the mamba spec `name` field (line 364) — this is the environment name that the mamba spec will use

**Current code:**
```python
# compiler.py:135 (env_run call)
result = self.env_manager.env_run(
    self.spec_manager.kernel_name, cmd, check=False, timeout=PIP_COMPILE_TIMEOUT
)

# compiler.py:364 (_get_base_mamba_spec, simple mode)
return {
    "name": self.spec_manager.kernel_name,
    "channels": ["conda-forge"],
    "dependencies": [f"python={self.spec_manager.python_version}"],
}
```

For a spec with `kernel_name: python3`, the `env_run` call passes `"python3"` to `env_run`.
Currently this works by accident: `env_run` calls `is_base_env_alias("python3")`,
which returns `True` due to the defensive entry in `is_base_env_name` at
`spec_manager.py:34`. This causes `env_run` to skip the `mamba run -n python3` prefix and run the
command in the current (base) environment.

**Fix:**

```python
from .spec_manager import kernel_name_to_env_name

class RequirementsCompiler(...):
    def __init__(self, spec_manager, repo_manager, python_path=sys.executable):
        super().__init__()
        self.spec_manager = spec_manager
        self.repo_manager = repo_manager
        self.python_path = python_path
    
    @property
    def resolved_environment_name(self) -> str | None:
        """The conda environment name for this compiler's spec, with python3→base mapping."""
        return kernel_name_to_env_name(self.spec_manager.kernel_name)
    
    def _run_pip_compile(self, ...):
        ...
        # Use resolved_environment_name instead of raw kernel_name
        result = self.env_manager.env_run(
            self.resolved_environment_name, cmd, check=False, timeout=PIP_COMPILE_TIMEOUT
        )
        ...
        result = self.env_manager.env_run(
            self.resolved_environment_name, cmd, check=False, timeout=PIP_COMPILE_TIMEOUT
        )
        ...
    
    def _get_base_mamba_spec(self) -> dict:
        ...
        # Use resolved_environment_name for the mamba spec name
        return {
            "name": self.resolved_environment_name,
            "channels": ["conda-forge"],
            "dependencies": [f"python={self.spec_manager.python_version}"],
        }
```

**Note on `consolidate_environment` (line 179-203):** This method gets `kernel_name` from
`base_mamba_spec.get("name")`, which for inline/external specs comes from the spec file.
This is correct for advanced mode — the mamba spec file's `name` field is authoritative.
No change needed here.

### 1.5.2 Correct `inject()` parameter handling — use environment name consistently

**File:** `nb_wrangler/injector.py`, lines 112-127

The `SpiInjector.inject()` method receives `resolved_environment_name` from
`wrangler.py:1104`:

```python
# wrangler.py:1104
return self.injector.inject(self.resolved_environment_name, exports_str)
```

This is **correct** — the SPI `environments/` directory is organized by
**environment name** (not kernel name). For a python3 kernel,
`resolved_environment_name` is `"base"`, so the injector looks for
`environments_path / base / base.yml` and `environments_path / base / base.pip`.

The original code at `wrangler.py:1104` passes `resolved_environment_name`
(not `resolved_kname`), and this is the right thing to do. The only issue is
that the parameter in `inject()` is named `kernel_name`, which is misleading:

```python
# injector.py:112 - misleading parameter name
def inject(self, kernel_name: str, env_exports: str) -> bool:
    ...
    kernel_path = self.environments_path / kernel_name
    env_yml = kernel_path / f"{kernel_name}.yml"
    env_pip = kernel_path / f"{kernel_name}.pip"
```

**Fix:** Rename the parameter from `kernel_name` to `environment_name` for
clarity:

```python
def inject(self, environment_name: str, env_exports: str) -> bool:
    ...
    env_path = self.environments_path / environment_name
    env_yml = env_path / f"{environment_name}.yml"
    env_pip = env_path / f"{environment_name}.pip"
```

**Rationale:** The `environments/` directory contains subdirectories named after
conda/micromamba environments, not Jupyter kernel names. Since we're now
explicitly separating these two concepts, the parameter name should reflect
that it receives an environment name. This is a non-breaking change since it
only affects internal naming.

**Note on the historical context:** The original wrangler code used
`kernel_name` for this parameter because (a) it was defined directly by the
spec in some form, and (b) `environment_name` and `kernel_name` were being used
interchangeably. Now that we're correcting this, the parameter should be named
`environment_name`.

## Phase 2: Fix Environment Operations to Use Environment Name

### 2.1 Update all environment operations in `wrangler.py` to use `resolved_environment_name`

**File:** `nb_wrangler/wrangler.py`

Replace `self.resolved_kname` with `self.resolved_environment_name` in:
- `_create_environment` (line ~925): `create_environment(self.resolved_environment_name, ...)`
- `_install_packages` (line ~956): `install_packages(self.resolved_environment_name, ...)`
- `_uninstall_packages` (line ~956, if applicable)
- `env_manager.environment_exists(self.resolved_environment_name)` (line ~913)
- `env_manager.delete_environment(self.resolved_environment_name)` (line ~1075)
- `env_manager.unregister_environment(self.resolved_environment_name)` (line ~1071)
- `_register_environment`: `register_environment(self.resolved_environment_name, ...)` (line ~1122)
- `injector.inject(self.resolved_environment_name, ...)` — uses environment name (correct, see Phase 1.5.2)

**Decision point — `inject`:** The injector uses the environment name to construct file paths like `environments_path / environment_name / f"{environment_name}.yml"`. The `environments/` directory is organized by environment names, so this is correct.

### 2.2 Fix `_delete_environment` guard

**File:** `nb_wrangler/wrangler.py`

```python
def _delete_environment(self) -> bool:
    """Unregister its kernel and delete the test environment."""
    if not self.resolved_environment_name:
        return self.logger.warning("No kernel name found to delete. Skipping.")

    if self.resolved_environment_name in ["base", "python3"]:
        return self.logger.warning(
            "Skipping base environment deletion and de-registration."
        )
    ...
```

This replaces the buggy `env_name.startswith("python")` check with an explicit list.

## Phase 3: Fix Case Sensitivity in Jupyter Kernelspec Operations

### 3.1 Preserve original case in `jupyter kernelspec` operations

**File:** `nb_wrangler/environment.py`

In `_jupyter_kernel_exists`, do case-insensitive comparison but preserve the original case for operations:

```python
def _jupyter_kernel_exists(self, env_name: str) -> bool:
    ...
    specs = json.loads(stdout).get("kernelspecs", {})
    # Case-insensitive match because Jupyter lowercases kernel names in kernelspecs
    spec_names = {k.lower() for k in specs}
    exists = env_name.lower() in spec_names
    ...
```

In `unregister_environment`, look up the actual registered name:

```python
def unregister_environment(self, env_name: str) -> bool:
    ...
    if not self._jupyter_kernel_exists(env_name):
        ...
    # Find the exact registered name (case-sensitive) for the uninstall command
    cmd = "jupyter kernelspec list --json"
    result = self.wrangler_run(cmd, check=False)
    specs = json.loads(stdout).get("kernelspecs", {})
    kernel_name_exact = env_name  # fallback
    for name in specs:
        if name.lower() == env_name.lower():
            kernel_name_exact = name
            break
    cmd = self._condition_cmd(f"jupyter kernelspec uninstall -y {kernel_name_exact}")
    ...
```

**Alternative, simpler approach:** Just preserve the original case everywhere and document that kernel names should be used as-is. The `--lower()` calls were likely added to handle a specific edge case that may no longer be relevant. This is the smaller change — let's go with **removing the `.lower()` calls** and documenting that case must match.

## Phase 4: Fix `environment_exists` Suffix Matching and Remove Defensive Entries

### 4.1 Replace suffix matching with exact matching

**File:** `nb_wrangler/environment.py`

```python
def environment_exists(self, env_name: str) -> bool:
    """Return True IFF `env_name` exists as a conda/micromamba environment."""
    self.logger.debug(f"Checking existence of {env_name}.")
    if self.is_base_env_alias(env_name):
        return True
    envs = self.get_existing_envs()
    # Use exact match; conda env names are case-sensitive
    return env_name in envs
```

**Impact on semantics:** This is a **behavioral change**. The old suffix matching allowed `env_name` to match a longer env name (e.g., `"nexus"` matching `"nbw_romannexus"`). This could break if any existing workflows depend on this. However, the prefix check (`env.startswith(str(NBW_MM))`) was the primary filter, so the suffix match was secondary. We should verify no specs rely on this.

**Decision point:** We could keep prefix-based matching (env must start with `NBW_MM_`) and then do exact match on the remainder. Or just do exact match entirely. Exact match is safer and clearer.

### 4.2 Remove defensive `"python"` and `"python3"` entries from `is_base_env_name`

**File:** `nb_wrangler/spec_manager.py`

```python
def is_base_env_name(env_name: str | None) -> bool:
    """Return True if *env_name* refers to the base conda environment.

    Only 'base' is treated as an alias for the base environment. The
    'python3' and 'python' kernel names are handled by
    ``kernel_name_to_env_name`` which maps them to 'base' before they
    reach this function.
    """
    return env_name == "base"
```

**Prerequisites:** Phase 1.5.1 must be completed first so that the compiler
no longer relies on the defensive entries. After this change:

- `is_base_env_alias("python3")` returns `False` instead of `True`
- `environment_exists("python3")` checks the filesystem instead of returning `True`
- `env_run("python3", ...)` uses `mamba run -n python3` instead of running in base
- `env_live_path("python3")` resolves to `nbw_mm_dir/envs/python3` instead of `nbw_mm_dir`
- `mm_envs_dir("python3")` resolves to `nbw_mm_dir/envs` instead of `nbw_mm_dir`

In the normal wrangler flow, these paths are never hit with `"python3"` because
`kernel_name_to_env_name` maps it to `"base"` first. The change only affects
direct calls to these functions with raw kernel names.

## Phase 5: Consolidate Mamba Spec Name Handling

### 5.1 Ensure mamba spec `name` is always set to environment name

**File:** `nb_wrangler/compiler.py`

For simple-mode specs (Method 1, line 364), the mamba spec `name` field uses
`self.spec_manager.kernel_name`. This should use the resolved environment name
instead (see Phase 1.5.1 for the fix).

For inline/external specs (Methods 2-4), the `name` field comes from the spec
file itself, which is correct — the mamba spec file is the authoritative source.

No additional changes needed beyond Phase 1.5.1.

### 5.2 Add validation cross-check for inline/external specs

**File:** `nb_wrangler/spec_validator.py`

For inline specs, add a check that `inline_mamba_spec` has a `name` field. For external specs, the validator currently can't check this (the spec hasn't been fetched), but we can add a post-compile validation step.

## Phase 6: Eliminate Code Duplication

### 6.1 Move resolved kernel/env name logic to SpecManager or a shared context

**File:** `nb_wrangler/spec_manager.py`

Add methods to `SpecManager`:

```python
def get_resolved_kernel_name(self) -> str | None:
    """Get the most reliable kernel name available."""
    return self.get_output_data("kernel_name") or self.kernel_name

def get_resolved_environment_name(self) -> str | None:
    """Get the most reliable environment name available (with python3→base mapping)."""
    kname = self.get_resolved_kernel_name()
    if kname == "python3":
        return "base"
    return kname
```

**File:** `nb_wrangler/wrangler.py` and `data_wrangler.py`

Replace `resolved_kname` and `resolved_environment_name` properties with calls to `self.spec_manager.get_resolved_environment_name()` and `self.spec_manager.get_resolved_kernel_name()`.

This eliminates the triplication of logic across `NotebookWrangler.resolved_kname`, `DataWrangler.resolved_kname`, and `NotebookWrangler.env_name`.

## Phase 7: Testing

### 7.1 Add tests for the python3→base mapping

**File:** `tests/test_wrangler.py` (or new test file)

```python
def test_python3_kernel_maps_to_base_env():
    sm = SpecManager(...)
    sm.header["kernel_name"] = "python3"
    assert sm.kernel_name == "python3"
    assert sm.environment_name == "base"

def test_resolved_environment_name_python3():
    wrangler = NotebookWrangler(...)
    sm = wrangler.spec_manager
    sm.header["kernel_name"] = "python3"
    assert wrangler.resolved_environment_name == "base"
    assert wrangler.resolved_kname == "python3"
```

### 7.2 Add tests for case-sensitive env existence

```python
def test_environment_exists_case_sensitive():
    em = EnvironmentManager(...)
    # Create env "RomanNexus-2026.2"
    assert em.environment_exists("RomanNexus-2026.2") is True
    assert em.environment_exists("romannexus-2026.2") is False
```

### 7.3 Add tests for exact env existence (no suffix matching)

```python
def test_environment_exists_exact_match():
    em = EnvironmentManager(...)
    assert em.environment_exists("nbw_test") is True
    assert em.environment_exists("test") is False  # no longer matches suffix
```

### 7.4 Update tests for removed defensive entries

**File:** `tests/test_env_name_utils.py`, `tests/test_environment.py`, `tests/test_kernel_env_name.py`

Update tests that explicitly test for `python3`/`python` being treated as base
aliases:

- `test_env_name_utils.py:41`: `assert is_base_env_name("python3") is True` →
  `assert is_base_env_name("python3") is False`
- `test_environment.py:39`: `assert em.is_base_env_alias("python3") is True` →
  `assert em.is_base_env_alias("python3") is False`
- `test_environment.py:250-252`: `assert em.environment_exists("python3") is True` →
  should check the filesystem or be removed
- `test_kernel_env_name.py:250-252`: `assert em.environment_exists("python3") is True` →
  should check the filesystem or be removed

### 7.5 Add tests for compiler using resolved environment name

```python
def test_compiler_uses_resolved_env_name():
    """Compiler should use kernel_name_to_env_name, not raw kernel_name."""
    from nb_wrangler.compiler import RequirementsCompiler
    from nb_wrangler.spec_manager import kernel_name_to_env_name
    
    # Mock env_run to capture what environment name is passed
    captured_name = []
    def fake_env_run(env_name, cmd, **kwargs):
        captured_name.append(env_name)
        return MagicMock(stdout="out", returncode=0)
    
    compiler = RequirementsCompiler(spec_manager_with_python3_kernel, ...)
    compiler.env_manager.env_run = fake_env_run
    compiler._run_pip_compile(...)
    
    assert captured_name == ["base"]  # not "python3"

def test_compiler_mamba_spec_uses_env_name():
    """Simple-mode mamba spec should use environment name, not kernel name."""
    compiler = RequirementsCompiler(spec_manager_with_python3_kernel, ...)
    base_mamba_spec = compiler._get_base_mamba_spec()
    
    assert base_mamba_spec["name"] == "base"  # not "python3"
```

## Semantic Impact Summary

| Current Behavior | Proposed Behavior | Breaking? |
|---|---|---|
| `env_name` returns `"base"` for `kernel_name == "python3"` | Centralized to `SpecManager.environment_name`; `resolved_kname` returns `"python3"` | No, but `resolved_kname` users must switch to `resolved_environment_name` |
| `resolved_kname` falls back to `env_name` (with mapping) | `resolved_kname` is kernel-accurate; new `resolved_environment_name` has the mapping | **Yes** — code using `resolved_kname` for env operations must change |
| `environment_exists` uses suffix matching | Exact matching only | **Yes** — any env found by suffix will no longer be found |
| Jupyter kernelspec operations lowercase names | Preserve original case | **Yes** — case-mismatched lookups that happened to work may now fail (but were incorrect) |
| `is_base_env_name` returns True for `base`, `python3`, `python` | Only `base` | **Yes** — direct calls with `python3`/`python` will no longer be treated as base |
| Compiler uses raw `kernel_name` for env operations | Uses `resolved_environment_name` | **Yes** — but only affects python3 specs, where the behavior is already correct |
| Simple-mode mamba spec `name` uses `kernel_name` | Uses `environment_name` | **Yes** — but only affects python3 specs, where the env is created as `base` |
| Three places define kernel/env name resolution | Centralized in `SpecManager` | No |
| `env_name` property exists without deprecation | Emits `DeprecationWarning`, redirects to `environment_name` | No — backward compatible, just warns |

## Implementation Order

1. **Phase 1** (SpecManager + centralization) — foundational
2. **Phase 1.5** (compiler + inject fixes) — must precede Phase 4
3. **Phase 2** (update wrangler.py references) — depends on 1
4. **Phase 4** (environment_exists + remove defensive entries) — depends on 1.5
5. **Phase 3** (case sensitivity) — independent
6. **Phase 5** (validation) — independent
7. **Phase 6** (eliminate duplication) — depends on 1
8. **Phase 7** (tests) — throughout

## Risks / Questions for Reviewer

1. **Does any production spec rely on the suffix-matching in `environment_exists`?** The `startswith(NBW_MM)` prefix check seems to be the primary filter; the suffix match appears to be an over-permissive fallback. *(OK — proceed with exact matching.)*

2. **`_get_base_mamba_spec` uses `kernel_name` as mamba spec `name` (compiler.py:364):** For python3 kernels, the mamba spec would have `name: python3`, but the environment is created as `base` (via `resolved_environment_name`). This is now fixed in Phase 1.5.1 — the compiler will use `resolved_environment_name` for the mamba spec name and `env_run` calls.

3. **Backward compatibility of `env_name` property:** If we rename it to `environment_name`, external scripts or aliases that reference `env_name` will break. *(Fixed — `env_name` is deprecated with a `DeprecationWarning`, not removed. The deprecation redirects to `environment_name`.)*

4. **The `resolved_kname` in `wrangler.py` line 1042** passes `kernel_name=self.resolved_kname` to `revise_and_save`. This stores the compiled kernel name in spec output. If we change what `resolved_kname` returns for `python3`, this will store `"python3"` instead of `"base"`. Is that the desired behavior for the spec output? *(OK — kernel_name should be the kernel name, not the environment name, in spec output.)*

5. **Compiler routines that work with environments should use `resolved_environment_name`:** All `env_run` calls in the compiler (lines 135, 144) and the mamba spec `name` field (line 364) should use the resolved environment name, not the raw kernel name. This is addressed in Phase 1.5.1.

6. **`wrangler.py:1104` passes `resolved_environment_name` (mapped to `base`) to `inject()`:** This is **correct** — the SPI `environments/` directory is organized by environment names. The only fix needed is to rename the parameter in `injector.py` from `kernel_name` to `environment_name` for clarity (Phase 1.5.2). The caller already passes the correct value.