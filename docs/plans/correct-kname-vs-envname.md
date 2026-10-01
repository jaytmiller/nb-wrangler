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

### 1.2 Replace `NotebookWrangler.env_name` with `environment_name`

**File:** `nb_wrangler/wrangler.py`

Replace the `env_name` property with a thin wrapper or alias:

```python
@property
def env_name(self):
    """Deprecated alias for spec_manager.environment_name.
    Kept for backward compatibility; will be removed in a future version.
    """
    return self.spec_manager.environment_name if self.spec_manager else None
```

Or fully replace it:

```python
@property
def environment_name(self):
    """Conda/micromamba environment name (may differ from kernel_name for 'python3')."""
    return self.spec_manager.environment_name if self.spec_manager else None
```

**Impact on semantics:** `env_name` returning `"base"` for `kernel_name == "python3"` is now the **canonical** behavior, defined in one place. All code paths that previously used `env_name` should be updated to use `environment_name`.

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
    return (
        self.compiled_kernel_name  # compiler output already has the right value
        or self.spec_manager.get_output_data("kernel_name")  # stored at compile time
        or self.spec_manager.environment_name  # includes python3→base mapping
    )
```

**Key change:** `resolved_kname` no longer falls back to `env_name` (which had the mapping). It now resolves to the raw kernel name. Environment operations should use `resolved_environment_name`.

### 1.4 Update `DataWrangler.resolved_kname` to use `SpecManager.environment_name`

**File:** `nb_wrangler/data_wrangler.py`

```python
@property
def resolved_kname(self) -> str | None:
    """Helper to get kernel name, matching NotebookWrangler logic."""
    # Note: This is a bit of duplication, but necessary if we want DataWrangler
    # to be independent for environment registration.
    # In a fuller refactor, this state might live in a shared context.
    return (
        self.spec_manager.get_output_data("kernel_name")
        or self.spec_manager.environment_name
    )
```

**Decision point:** DataWrangler's `_register_environment` calls `register_environment(kname, ...)` where the first arg is used as both the conda env name (for `env_run`) and the Jupyter `--name`. It should use `environment_name`.

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
- `injector.inject(self.resolved_kname, ...)` stays as-is (inject needs the kernel name for file paths in SPI)

**Decision point — `inject`:** The injector uses `kernel_name` to construct file paths like `environments_path / kernel_name / f"{kernel_name}.yml"`. For `python3`, this would be `environments_path / python3 / python3.yml`. But if the env is named `base`, the path should be... well, this is SPI-specific. For now, keep using `resolved_kname` for inject, as SPI injection is about kernel spec paths, not conda env names.

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

## Phase 4: Fix `environment_exists` Suffix Matching

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

## Phase 5: Consolidate Mamba Spec Name Handling

### 5.1 Ensure mamba spec `name` is always set explicitly

**File:** `nb_wrangler/compiler.py`

In `consolidate_environment`, the code already sets `final_mamba_spec["name"] = kernel_name` (line 203). But `kernel_name` here comes from `base_mamba_spec.get("name")` (line 180), which for inline/external specs comes from the spec file, not from `spec_manager.kernel_name`. This is correct — the mamba spec file is the authoritative source for the environment name in advanced mode. No change needed here.

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

Replace `resolved_kname` and `resolved_environment_name` properties with calls to `self.spec_manager.get_resolved_environment_name()`.

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

## Semantic Impact Summary

| Current Behavior | Proposed Behavior | Breaking? |
|---|---|---|
| `env_name` returns `"base"` for `kernel_name == "python3"` | Centralized to `SpecManager.environment_name`; `resolved_kname` returns `"python3"` | No, but `resolved_kname` users must switch to `resolved_environment_name` |
| `resolved_kname` falls back to `env_name` (with mapping) | `resolved_kname` is kernel-accurate; new `resolved_environment_name` has the mapping | **Yes** — code using `resolved_kname` for env operations must change |
| `environment_exists` uses suffix matching | Exact matching only | **Yes** — any env found by suffix will no longer be found |
| Jupyter kernelspec operations lowercase names | Preserve original case | **Yes** — case-mismatched lookups that happened to work may now fail (but were incorrect) |
| Three places define kernel/env name resolution | Centralized in `SpecManager` | No |

## Implementation Order

1. **Phase 1** (SpecManager + centralization) — foundational
2. **Phase 4** (environment_exists fix) — independent
3. **Phase 3** (case sensitivity) — independent  
4. **Phase 2** (update wrangler.py references) — depends on 1
5. **Phase 5** (validation) — independent
6. **Phase 6** (eliminate duplication) — depends on 1
7. **Phase 7** (tests) — throughout

## Risks / Questions for Reviewer

1. **Does any production spec rely on the suffix-matching in `environment_exists`?** The `startswith(NBW_MM)` prefix check seems to be the primary filter; the suffix match appears to be an over-permissive fallback.

2. **For `inject()` in `injector.py`:** Should the SPI file paths use `kernel_name` or `environment_name`? For `python3`/`base`, the SPI path would change. Need to verify the SPI directory structure handles this.

3. **Backward compatibility of `env_name` property:** If we rename it to `environment_name`, external scripts or aliases that reference `env_name` will break. We should deprecate rather than remove, or confirm no external usage exists.

4. **The `resolved_kname` in `wrangler.py` line 1042** passes `kernel_name=self.resolved_kname` to `revise_and_save`. This stores the compiled kernel name in spec output. If we change what `resolved_kname` returns for `python3`, this will store `"python3"` instead of `"base"`. Is that the desired behavior for the spec output? (It should be — kernel_name is a kernel name, environment_name is the env name.)