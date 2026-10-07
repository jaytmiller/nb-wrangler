# Plan: Consolidating Pantry Definitions Between `nbw` and `hubenv`

## Objective

Create a single, unified pantry model that both `nbw` (spec-driven, notebook
image derivation) and `hubenv` (standalone PPE lifecycle management) use. The
goal is to eliminate the dual-pantry inconsistency where `hubenv`-installed
environments are invisible to `nbw` and vice versa.

## Background

Currently:

- **`nbw`** uses `NbwPantry` / `NbwPantrySet` / `NbwShelf` in `pantry.py`. A
  "shelf" is named after a wrangler spec ID and contains `wrangler-spec.yaml`,
  `archives/`, `notebook_repos/`, `data/`. Each shelf represents a curated
  notebook environment definition that can produce Docker images.

- **`hubenv`** uses `HubenvConfig` in `hubenv/config.py`. A "shelf" is named
  after a PPE (Persistent Platform Environment) and contains an implicit
  `.hubenv-spec.yaml` at `NBW_ROOT/envs/<NAME>/.hubenv-spec.yaml` and a
  restore-hash marker at `NBW_ROOT/.hubenv-restore/<NAME>.sha256`.

These are two separate concepts of "shelf" in the same `NBW_PANTRY` directory
tree. An environment installed by `hubenv env create myenv` does NOT create a
shelf in the `nbw` sense, and an environment managed by `nbw` via a wrangler
spec is not visible to `hubenv env ls`.

## Critical Finding: Shelf Name Derivation (BLOCKING)

### How `nbw` Derives Shelf Names

Per `docs/naming.md`, the `shelf_name` defaults to the fully resolved
`environment_name`:

```
spec_manager.shelf_name  =  spec_manager.get_resolved_environment_name()
                          =  kernel_name_to_env_name(spec_manager.get_resolved_kernel_name())
                               or spec_manager.image_name.replace(" ", "-")
```

When `kernel_name` is specified in the spec, the shelf name is the resolved
environment name (with the `python3` → `base` mapping applied).  When
`kernel_name` is unspecified, the shelf name falls back to the `image_name`
(with spaces replaced by dashes).  This ensures a canonical, deterministic
shelf name derived from the same source of truth as the environment name.

### How `hubenv` Derives Shelf Names

In `hubenv`, shelf names are the PPE name (e.g., `"myenv"`) — an arbitrary
user-chosen string. This is also the name of the live environment at
`${NBW_ROOT}/envs/<NAME>`.

### Alignment Strategy

When `hubenv` creates a PPE from a wrangler spec, it should compute the shelf
name using the same `SpecManager.shelf_name` property so that both systems
use identical shelf directory names for identical environments.  When
`hubenv` creates a PPE without a spec (standalone PPE name), the PPE name
becomes the shelf name directly (matching the resolved environment name for
that PPE).

### Unified Shelf Naming

With `docs/naming.md` defining `shelf_name` as the resolved `environment_name`
(falling back to `image_name`), both `nbw` and `hubenv` now use the same
canonical shelf name for the same environment:

| System | Shelf Name Source | Example | Env Name Source | Example |
|--------|-------------------|---------|-----------------|---------|
| `nbw` | `spec.resolved_environment_name` or `spec.image_name` | `base` or `RomanNexus-2026.2` | `spec.environment_name` | `base` or `RomanNexus-2026.2` |
| `hubenv` | PPE name (CLI arg) | `myenv` | PPE name (same) | `myenv` |

When `hubenv` creates a PPE from a wrangler spec, it computes the shelf name
using `SpecManager.shelf_name`, ensuring identical on-disk layout.  When
`hubenv` creates a standalone PPE (no spec), the PPE name is both the shelf
name and the environment name, matching the unified model.

**No mapping file is required** — name consistency is guaranteed by deriving
both from the same resolved environment name.

This replaces the previous **"BLOCKING ISSUE"** framing where `nbw` shelf names
were derived from `spec.image_name` and `hubenv` shelf names from PPE names,
requiring an explicit mapping file.  The updated naming convention eliminates
the divergence.

## Design Principle

**One environment = one shelf.** The unified model should ensure that wherever
`hubenv` creates/manages an environment, a corresponding `nbw`-compatible
wrangler spec is automatically maintained, and vice versa. The `NbwShelf` class
is the canonical representation; `HubenvConfig` should be reframed as a
higher-level facade over `NbwPantrySet` that adds PPE-specific operations.

## Phase 1: Unify Shelf Identity and Structure

### 1.1 Shelf Naming (Unified per `docs/naming.md`)

Per `docs/naming.md`, `shelf_name` defaults to the fully resolved
`environment_name` (falling back to `image_name`). Both `nbw` and `hubenv`
derive shelf names from the same source of truth:

- `nbw` shelves are named by `SpecManager.shelf_name` (resolved environment
  name, or `image_name` when `kernel_name` is unspecified).
- `hubenv` PPEs use the PPE name as both the environment name and shelf name.
  When a PPE is created from a wrangler spec, the spec's `shelf_name` property
  is used instead, ensuring identical on-disk layout.

**No mapping file is required** — name consistency follows from deriving both
systems' shelf names from the same naming convention.

### 1.3 Spec File Compatibility

- **Decision**: When `hubenv` creates a PPE, it should write a wrangler spec
  (`wrangler-spec.yaml`) to the shelf that is compatible with `nbw`. This
  spec should be an implicit/default spec (e.g., a minimal env spec with the
  PPE's package delta) if no explicit spec is provided.
- The `.hubenv-spec.yaml` file (PPE seed + delta) stays as a PPE-specific
  companion file, but the primary `wrangler-spec.yaml` must also be written.
- `NbwShelf.spec_path` is already `wrangler-spec.yaml` — no change needed.
- The spec must include a `image_name` field set to the PPE name so `nbw`
  can discover it via the spec, even though the shelf directory is named
  by the PPE name.

### 1.4 Archive Structure Alignment

- **Current**: `hubenv` uses `archives/last-save.sha256` for restore-hash
  tracking. `nbw` uses `archives/env-*`, `archives/repo-*`, etc.
- **Decision**: Keep both. The `last-save.sha256` is a hubenv-specific marker
  that can coexist with nbw archives in the same `archives/` dir. Add a
  method to `NbwShelf` to read/write the restore hash, OR keep it as a
  filesystem convention that both code paths agree on.

## Phase 2: Refactor `HubenvConfig` → `PantryStore` + `NbwPantrySet` Adapter

### 2.1 Extract Pantry Logic

- Rename `HubenvConfig` → `PantryStore` (or keep as alias).
- `PantryStore` becomes a **facade** over `NbwPantrySet`, not a parallel
  implementation:
  ```python
  from nb_wrangler.pantry import NbwPantrySet

  class PantryStore:
      def __init__(self):
          self._pantries = NbwPantrySet.from_env()

      @property
      def primary(self) -> NbwPantry:
          return self._pantries.primary

      def writable_pantries(self) -> list[Path]:
          return [p for p in self._pantries.paths if self.is_writable(p)]

      def find_shelves(self, name: str) -> list[NbwShelf]:
          # Search all pantries for a shelf with the given name
          ...

      def list_shelves(self, ...) -> list[dict]:
          # Convert NbwPantrySet shelf data to dict format for hubenv use
          ...
  ```

### 2.2 Bridge Methods

Methods on `PantryStore` that bridge to `NbwPantrySet`:

| `PantryStore` (hubenv) | `NbwPantrySet` (nbw) | Notes |
|---|---|---|
| `writable_pantries()` | `.paths` + `os.access` | Filter to writable |
| `first_writable_pantry()` | `.path` (primary) | With writability check |
| `target_pantry()` | `.path` (primary) | With forced-path override |
| `find_shelves(name)` | `.get_shelf(name)` per pantry | Return all matches |
| `list_shelves()` | `.shelf_names()` per pantry | Convert to dict format |
| `list_live_envs()` | — | New: scan `NBW_ROOT/envs` |
| `restore_hash_path(name)` | — | New method on `NbwShelf` or `PantryStore` |
| `hubenv_spec_path(name)` | `.spec_path` | `NbwShelf.spec_path` already exists |

### 2.3 Live Environment Tracking

`NBW_ROOT/envs/` is where both systems should place live (installed)
environments. Currently:

- `nbw` uses `env_manager` to manage envs in `${NBW_ROOT}/mm/envs/`.
- `hubenv` uses `${NBW_ROOT}/envs/<NAME>`.

- **Decision**: Standardize on `${NBW_ROOT}/envs/<NAME>` as the canonical live
  environment location for BOTH `nbw` and `hubenv`. Update `NbwShelf` to
  reference this path (via `env_manager` or directly).

## Phase 3: Automatic Spec Maintenance

### 3.1 `hubenv env create`

When creating a new PPE:
1. Resolve target pantry via `PantryStore`.
2. Get or create `NbwShelf(pantry_path / "shelves" / <SHELF_NAME>)`.
   - The shelf directory is named using `SpecManager.shelf_name` (or the
     PPE name for standalone PPEs), consistent with `nbw`'s naming.
     No divergence exists — both systems use the same canonical shelf name.
3. Write a minimal wrangler spec (`wrangler-spec.yaml`) that captures the
   PPE's seed environment. The spec's `image_name` field is set to the PPE
   name so it can be discovered by `nbw`.
4. Set `NbwShelf.set_wrangler_spec()`.
5. Write `.hubenv-spec.yaml` alongside for PPE-specific state.
6. Proceed with PPE creation.

### 3.2 `hubenv env save`

When saving a PPE environment:
1. Pack the environment archive into `NbwShelf.archive_root`.
2. Write/update `wrangler-spec.yaml` to reflect the saved state (package list
   from the environment).
3. Write `archives/last-save.sha256`.

### 3.3 `hubenv env rm`

When removing a PPE:
1. Call `NbwPantrySet.delete_shelf(name)` to remove the shelf directory.
2. Remove the live env at `${NBW_ROOT}/envs/<NAME>`.
3. Remove the restore-hash marker.

## Phase 4: Make `nbw` Aware of hubenv-managed Envs

### 4.1 `nbw env ls` / `nbw env spec-list`

- `NbwPantrySet.list_shelves()` already lists all shelf directory names. Since
`hubenv` creates `NbwShelf` entries (via the shelf directory), PPE-managed
shelves will appear in `nbw`'s listing.

Since both systems now use the unified naming from `docs/naming.md`, shelf
directory names are consistent: both are derived from the resolved environment
name (or PPE name for standalone PPEs). There is no longer a naming divergence
to document.

To distinguish PPE-managed shelves:
- Check for presence of `.hubenv-spec.yaml` at
  `${NBW_ROOT}/envs/<SHELF_NAME>/.hubenv-spec.yaml`.
- Alternatively, parse the `wrangler-spec.yaml` and check for a
  `hubenv_managed: true` field or similar marker.

### 4.2 `nbw env restore`

- Should detect hubenv-managed shelves (presence of
  `${NBW_ROOT}/envs/<NAME>` or `archives/last-save.sha256`) and allow
  restoring them into `NBW_ROOT`.

## Phase 5: Update Command Modules

### 5.1 `hubenv/` command modules

Each command module that currently instantiates `HubenvConfig()` should:
1. Get config from `get_args_config()` (the singleton `WranglerConfig`).
2. Instantiate `PantryStore()` for pantry/shelf operations.
3. Use `NbwPantrySet` methods through `PantryStore` facade.

### 5.2 `_common.py` cleanup

- Remove `ensure_config()` workaround — `cli.py:main` should always call
  `set_args_config()` before dispatch.
- Update `print_exports()` to use `PantryStore` or accept `NBW_ROOT` directly.
- Keep `print_no_writable_pantry()` and `print_shadowing_warnings()` — these
  are presentation-layer and fine as-is, but route diagnostics through logger.

## Phase 6: Tests

### 6.1 PantryStore facade tests
- `test_pantry_store_writable_pantries`
- `test_pantry_store_find_shelves_multi_pantry`
- `test_pantry_store_list_shelves_format`

### 6.2 Cross-compatibility tests
- `test_hubenv_create_nbwb_visible` — create env via hubenv, verify shelf
  appears in `NbwPantrySet.list_shelves()`.
- `test_nbw_spec_hubenv_visible` — create shelf via `NbwPantrySet`, verify
  hubenv can find it via `PantryStore.find_shelves()`.
- `test_hubenv_save_updates_wrangler_spec` — save a PPE, verify
  `wrangler-spec.yaml` is updated on the shelf.

### 6.3 Existing tests
- Run full test suite to catch regressions in `pantry.py`, `wrangler.py`,
  `data_wrangler.py` which depend on `NbwPantrySet`.

## Files to Modify

| File | Change |
|------|--------|
| `nb_wrangler/hubenv/config.py` | Refactor `HubenvConfig` → `PantryStore` facade over `NbwPantrySet` |
| `nb_wrangler/hubenv/_common.py` | Remove `ensure_config()`, update helpers |
| `nb_wrangler/hubenv/cli.py` | Call `set_args_config()` early in `_main` |
| `nb_wrangler/hubenv/env_create.py` | Use `PantryStore` + `NbwShelf.set_wrangler_spec()` |
| `nb_wrangler/hubenv/env_save.py` | Update spec on save, use `NbwShelf` archives |
| `nb_wrangler/hubenv/env_restore.py` | Use `NbwShelf.unpack_environment()` |
| `nb_wrangler/hubenv/env_ls.py` | Use `PantryStore.list_shelves()` (already dict format) |
| `nb_wrangler/hubenv/env_rm.py` | Use `NbwPantrySet.delete_shelf()` |
| `nb_wrangler/pantry.py` | Add `restore_hash_path()` to `NbwShelf` if needed; ensure live env path consistency |
| `nb_wrangler/config.py` | (No changes — hubenv fields already planned from Phase 1) |
| `tests/` | Add cross-compatibility and facade tests |

## Execution Order

| Step | Phase | Description |
|------|-------|-------------|
| 1 | §2.1 | Extract `PantryStore` facade (read-only, wraps `NbwPantrySet`) |
| 2 | §2.2 | Add bridge methods; verify hubenv can read existing pantries |
| 3 | §3.1–3.3 | Add automatic spec writing to `env_create`/`env_save`/`env_rm` |
| 4 | §5 | Update all command modules to use `PantryStore` |
| 5 | §4 | Make `nbw` aware of hubenv envs (listing annotations) |
| 6 | §6 | Write tests; run full suite |
| 7 | §5.1 | Remove `ensure_config()` workaround |

## Risk Assessment

- **Breaking `nbw`**: Changes to `NbwPantrySet` are minimal — we're primarily
  *adding* hubenv-awareness, not changing existing `nbw` behavior. The
  facade pattern isolates changes to `hubenv/`.
- **Spec compatibility**: The implicit wrangler spec written by `hubenv` must
  be a valid spec that `nbw` can parse. Start with a minimal env spec template.
- **Live env path divergence**: `${NBW_ROOT}/envs/` vs `${NBW_ROOT}/mm/envs/`.
  Aligning on `envs/` is a breaking change for existing `nbw` environments.
  May need a migration step or path aliasing.