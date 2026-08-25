**v0.9.1** change notes (since v0.9.0):

### Version & Logging

- **Unconditional version output** in wrangler log messages (`nb_wrangler/cli.py`). The wrangler now logs `Wrangler version:` at startup for every run, distinct from `--version` (which prints solely the version string and exits). This makes version identification easier when reviewing log output.
- **Migration Overview** comment added to the top of `docs/CHANGES.md`, documenting the ongoing factoring of production specs and image building out to the sister repository at [spacetelescope/nb-wrangler-images](https://github.com/spacetelescope/nb-wrangler-images.git); images are under [nb-wrangler-images public GHCR](https://github.com/spacetelescope/nb-wrangler-images/pkgs/container/nb-wrangler-images)).

### `--reinstall` Workflow

- **Dropped repo cloning from `--reinstall`**. The reinstall workflow no longer invokes `_prepare_all_repositories_locked`; since a prior `--curate` run already wrote resolved repository SHAs, notebook paths, and imports into the spec output, repos are not re-cloned during reinstall.

---

**v0.9.0** change notes:

### Migration Overview

`nb-wrangler` is in the process of factoring production specs and image building out to a sister repository `nb-wrangler-images` which is coming online *now* but with straggling  clean-up work to do removing dead functionality and documentation from `nb-wrangler` and updating it as needed at `nb-wrangler-images.`  Going forward all production specs will be CM'ed on GitHub's [spacetelescope/nb-wrangler-images](https://github.com/spacetelescope/nb-wrangler-images.git) and images will now be located under spacetelescopes [nb-wrangler-images public GHCR](https://github.com/spacetelescope/nb-wrangler-images/pkgs/container/nb-wrangler-images).

### New Features

- **Assets Injection** (`nb_wrangler/injector.py` + 207 lines, `tests/test_assets_injection.py`)
  - New `assets:` spec section bundles static files from git repos into Docker images during SPI injection/curation.
  - Supports flat syntax (single item) and grouped syntax (`items:` sub-list sharing common repo/ref).
  - `contents_only` flag copies directory contents rather than the directory itself.
  - Source paths support trailing `/` notation for contents-only mode plus glob patterns.
  - Generates `install-assets.sh` script in the environments directory.

- **System Commands Override** (`system.commands.{mamba, pip, favor}`)
  - New spec-level `system.commands: { mamba: ..., pip: ..., favor: ... }` section overrides Mamba/pip executables.
  - `favor` controls precedence when both env vars and spec define values: `spec` (default) or `environment`.
  - CLI flags (`--mamba-cmd`, `--pip-cmd`) always override both spec and env vars.

- **NBW_OVERRIDES_MODE** Environment Variable
  - Set to `--dev` or `--prod` to change default override behavior for all workflows (default is `--prod`).
  - Replaces earlier reliance on implicit heuristic detection of dev/prod mode.

- **Calver Tag Resolution** (repository checkout)
  - Automatic resolution of abstract tags (branch prefixes like `2026.2`) by listing git tags, sorting descending, and picking the highest matching prefix.
  - Falls back to partial SHA when full tag resolution fails.

- **YAML Type Normalization** (`nb_wrangler/yaml_typed_values.py`)
  - New module normalizes YAML values (dates, numbers, booleans) to strings via `yaml_typed_values.normalize_value()`, preventing type mismatches downstream.

- **Environment Variables in Spec** (`environment_vars`, `test_environment_vars`)
  - New top-level `environment_vars:` spec section, like variables in `refdata_dependencies.yaml` but specified directly in the wrangler spec; merged into refdata during data collection.
  - New `test_environment_vars:` spec section injects test-scoped env vars via `_inject_test_env_vars()` before notebook/import tests run.

- **`--print-repo-tags` Enhancement**
  - Now uses `git ls-remote --tags` (no clone required) to enumerate tags for each repo URL.
  - Version-prefix refs (e.g. `2026.2`) are resolved to the highest `x.y.z` tag with the greatest numeric `z`.
  - Non-version refs (e.g. `main`) are returned as-is when no matching tags are found.

### Spec & Validation

- **Spec Validation & Version Awareness**
  - Added warning when a spec's `system.spec_version` is greater than `WRANGLER_SPEC_VERSION`, signaling that the wrangler version may not recognize all features in the newer spec format — a prompt to upgrade nb-wrangler. A deprecation warning (existing behavior) still fires for older versions. Current supported version: `2.3`.
  - Added `_validate_dev_overrides_section()` allow-list validation: enforces that keywords under `dev_overrides` and `deactivated_dev_overrides` mirror the top-level spec schema, catching typos/unsupported keys early. Reuses `_check_allowed_keywords()` for recursive checking against `ALLOWED_KEYWORDS`.

- **Package-List Dev Overrides (full-replacement semantics)**
  - Added `extra_mamba_packages`, `common_mamba_packages`, `extra_pip_packages`, `common_pip_packages`, and `apt_packages` to the `_OVERRIDES_SCHEMA` whitelist. When present under `dev_overrides` in `--dev` mode, these lists **replace** (rather than append to) their top-level counterparts via the new `_overridden_list()` helper on `SpecManager`. In `--prod` mode overrides are never consulted. An empty override list clears the base entirely.

### Refactoring & API Changes

- **Selector-Based Path Data Structures**: `collect_notebook_paths()`, `NotebookImportProcessor.extract_imports()`, and `NotebookTester.filter_notebooks()` now use `list[dict[str, list[str]]]` format (selector_name → [paths]) instead of flat dictionaries.
  - `SpecManager.collect_notebook_paths()` signature changed: removed `repos_dir` parameter; now reads `self.config.repos_dir` internally.
  - `NotebookImportProcessor.extract_imports()` signature changed: takes `notebook_paths: list[dict[str, list[str]]]` (selector→files format); returns only `dict[str, list[str]]` (removed the `list[str]` unique imports return value).
  - `NotebookTester.filter_notebooks()` signature changed: takes `notebook_configs: list[dict[str, list[str]]]` (selector→files format).

- **Requirements.txt Discovery** (`SpecManager.get_requirements_files()`, new)
  - `requirements.txt` files are now discovered via `get_requirements_files()` (globbing configured `selected_notebooks` selections) under `self.config.repos_dir/<repo_name>`, not from `collect_notebook_paths()` results. Fixes discovery of orphan `requirements.txt` files in package-only directories (no notebooks). Returns `list[dict[str, list[str]]]`.
  - `SpecManager.flatten_req_data()` / `flatten_req_files()` (new methods) flatten the selector→files mapping into a flat list or dict.
  - Orphan handling: `_match_paths` logs "(orphan)" for `.txt` files whose parent directory has no `.ipynb` files.

- **Consolidate Environment Split**
  - `RequirementsCompiler.consolidate_environment()` no longer takes `notebook_paths` and no longer returns `non_mamba_pip_req_list` (now a 3-tuple instead of 4-tuple). The pip-file-gathering portion previously inside `consolidate_environment` is now handled by the new `RequirementsCompiler.consolidate_packages()` method, which calls `spec_manager.get_requirements_files()`.

### Configuration & CLI

- **`NBW_REPOS_DIR` support**: Repository directory default now configurable via `NBW_REPOS_DIR` env var (defaults to `references`).
- **`--quiet`/`-q` flag**: Suppresses all log output to stderr (stdout still visible for `--spec-name`, `--docker-list`, etc.).
- **Renamed**: `--finalize-dev-overrides` → `--spec-disable-dev-overrides`.
- **`--test-isolate-notebook` flag** (`config.py`, `environment.py`): Controls whether notebook tests run in an isolated temp copy or in-place (default is now in-place).
- **`--data-clean-symlinks` flag** (`cli.py`, `config.py`, `wrangler.py`): Controls cleanup of symlinks from spec locations to pantry installations; relies on `--data-env-vars-mode` to distinguish pantry vs spec modes. Environment variables track the selected notebook kernel/active environment within notebooks and terminal sessions.

### Behavior Changes

- **Default Image Registry**: Changed from generic to `spacetelescope/nb-wrangler-images`.
- **Default Environment Variables Mode**: Switched from `spec` to `pantry` (no longer creates refdata symlinks).
- **Default Notebook Testing**: Now in-place; replaced `test_directory_setup()` on-demand temporary tree copy with a conditional: isolated only when `--test-isolate-notebook` is set, otherwise uses the notebook's parent directory as `test_dir`.
- **`copy_shared_modules` Idempotency** (`utils.py`): Skips copying if the file or a like-named symlink already exists in the destination.
- **Registry Environment Variables** (`constants.py`): Reads `NBW_IMAGE_REGISTRY` and `NBW_IMAGE_PROJECT` env vars before applying default registry/project values.

### Infrastructure & Tooling

- **Timeout Increases** (all constants doubled or more):
  - `REPO_CLONE_TIMEOUT`: 300 → 7200
  - `INSTALL_PACKAGES_TIMEOUT`: 1800 → 3600
  - `PIP_COMPILE_TIMEOUT`: 600 → 1200
  - `IMPORT_TEST_TIMEOUT`: 60 → 120
  - `ARCHIVE_TIMEOUT`: 1200 → 3600
- **Bootstrap Script Fixes**: Commented out micromamba self-update (was hanging functional tests); added `set +x` to prevent debug output pollution; updated for `NBW_MAMBA_DEFAULT` vs `NBW_MAMBA_CMD` refactoring.
- **Pantry Read-Only Safety** (`tests/test_readonly_pantry.py`): Pantry on-demand directory creation avoids crashes when users/post-start-hook try to modify read-only pantries.
- **Dockerfile-aux.sh Auto-Cleanup** (`injector.py`): Added auto-code to `dockerfile-aux.sh` to remove itself after execution completes.
- **Asset/Symlink Cleanup Post-Install** (`injector.py`): Appends cleanup commands to end of `install-assets.sh`: removes the `/opt/environments/assets` staging directory and `install-assets.sh` itself after execution. Also simplified generated `install-assets.sh` code (removed unnecessary if/else branching; distinguished directory vs file destinations via `destination.endswith('/')` instead of runtime `os.path.isdir`).
- **Papermill Path Fix** (`notebook_tester.py`): Changed papermill invocation to pass the full notebook path instead of `os.path.basename()` only.
- **`resolve_var` Typo Fix** (`utils.py`): Corrected function name from `resolve_var` to `resolve_vars`.
- **`input()` Bug Fixes** (`notebook_tester.py`, `wrangler.py`): Fixed bugs in notebook location prompting and `input()` calls that crashed in non-tty contexts.
- **Notebook Progress Counter** (`notebook_tester.py`): Displays "X/Y notebooks" progress during notebook tester runs.
- **Bugfix: `override_pip_packages` Undefined Handling** (`compiler.py`): Fixes erroneous build-arg string when `override_pip_packages` is undefined.
- **Environment & Reset Curation Fix**: Fixed issue with deleting environments during `--reset-curation`; environment teardown now handles edge cases more gracefully (additional tests added to `test_environment.py`).

### Sample Specs & Tests

- **Sample Spec Updates**: Updated `specs/samples/RomanNexus-2026.2.yaml` to illustrate latest spec format (version 2.3) extensions, including new package-list override support and cleaned `dev_overrides` sections. Added baseline 2026.2 Roman spec for tagging dev. Added `specs/roman/astroquery-mast-test.yaml` and `specs/jwebbinar/jwebbinar-50.yaml`.

- **Tests Added (13 new/updated files)**:
  - `tests/test_assets_injection.py` — asset injection tests
  - `tests/test_config.py` (180 lines) — config parsing tests
  - `tests/test_constants.py` (148 lines) — constants validation tests
  - `tests/test_environment.py` — environment setup and teardown tests
  - `tests/test_logger.py` (108 lines) — logger tests
  - `tests/test_readonly_pantry.py` — read-only pantry safety tests
  - `tests/test_registry.py` — registry function tests
  - `tests/test_spec_manager_extended.py` (318 lines) — spec manager extended tests
  - `tests/test_spec_validator.py` (367 lines) — spec validator tests, including `TestPackageListDevOverrides` and `TestDevOverrideValidation`
  - `tests/test_tag_prefix_resolution.py` — calver tag resolution tests
  - `tests/test_utils.py` (368 lines) — utility function tests
  - `tests/test_yaml_typed_values.py` (82 lines) — YAML typed value normalization tests

---

**v0.8.1 Change Notes** (62 commits, ~5.9k lines added, ~1.4k lines deleted)

**Core Framework**
- Workflow resilience: `run_workflow()` now supports a `continue_on_failure` flag, allowing curation and data-reset workflows to complete remaining steps and report warnings instead of failing hard on individual step errors
- Re-enabled `self._env_compact` in the data-reset curation workflow pipeline (was commented out)

**Spec Handling & Data Manager**
- Refdata spec parsing now validates allowed keys (`install_files`, `other_variables`) and raises clear errors for unknown keywords
- `DataSection.data_path` handles None values gracefully (defaults to empty string)
- Moved spec file `nbw-wrangler-spec.yaml` from repo root into `specs/roman/nbw-wrangler-spec.yaml`

**URI Resolution (`utils.py`)**
- Rewrote `uri_to_local_path()` with proper scheme detection using `urllib.parse.urlparse()` instead of string prefix checks
- Improved `file://` URI and local path handling with FileNotFoundError for missing files
- Better error messages for unsupported URI schemes

**Compiler Changes**
- `extra_pip_packages.txt` and `common_pip_packages.txt` now written to the output directory via `utils.writelines()` instead of the current working directory (uses `tempfile` internally)
- Cleanup of pip packages files also respects `config.output_dir` path

**CLI Flags**
- Re-added `--env-compact` flag (was removed in a prior version)
- `--reset-curation` and `--data-reset-curation` now issue warnings for each failed step, making cleanup of incomplete curations more resilient

**Version & Dependencies**
- Version bump to 0.8.1
- Restored pandas version constraint to latest `3.x.y`
- Deactivated dev overrides for jwebbinar spec

**Specs**
- Renamed jwebbinar spec from `jwebbinar.yaml` to `jwebbinar-49.yaml`
- Created inline data and notebooks path in the updated jwebbinar-49 spec with embedded `refdata_dependencies`
- Established baseline "classic" image build specs for Jwebbinar and TIKE (targeting migration to wrangler generic builds)
- Removed `RomanNexus-2026.1.yml` spec from jwebbinar directory

**GitHub Actions / CI**
- Updated `.github/workflows/curate.yml` workflow
- Minor updates to `reinstall.yml`, `trigger-curate.yml.disabled`, and `trigger-remote-curate.yml.draft`

# 0.8.0 02-03-2026 Enhanced Testing and Environment Management

- Added regex support to `--test-notebooks` (and by extension `-t`, `--test-all`, `--test-imports`) allowing users to specify a subset of notebooks for testing.
- Added `--env-kernel-cleanup` command to scan and remove "dead" Jupyter kernels from the user's registry.

# 0.7.0  01-28-2026  RGES-Nexus wrangler image


# 0.6.0  12-18-2025  Roman-20 classic image build with data support


# 0.5.0  10-24-2025  Data and Shared Data Handing

- Added workflows and steps for collecting and curating data from notebook repos
- Validates refdata_dependencies.yaml files scraped from notebook repos.
- Collects data urls, sizes, archive hashes, env var definitions
- New CLI steps:
    - --data-collect
    - --data-download
    - --data-update
    - --data-validate
    - --data-unpack
    - --data-pack
    - --data-delete (both, archived, unpacked, "")
    - --data-select <regex> on (notebook repo, repo section, or archive URL)

    - --data-curate     (spec definition workflow)
    - --data-reinstall  (target system data installation)

- Downloads data and captures meta-data to spec
- Validates local re-installs using sha256 and archive length
- Packs / Unpacks data / Updates internal metadata for changes
- Populates environments with data env vars pointing to unpacked data

# 0.4.0  10-01-2025  Re-install and submit-for-build workflows

- Added `--submit-for-build` workflow for pushing wrangler spec to GitHub to trigger build.  This
  is v1.0 of the true wrangler image build paradigm and results in automatic image builds by GitHub Actions.
  This is in prototype-only mode and requires curator setup on github to enable submissions.

- Added `--inject-spi` workflow for dropping wrangler-defined requirements back into the standard
  locations in science-platform-images original deployments.  This updates the local science-platform-images
  clone in a way similar to that which a platform developer did during the original SPI build process,
  nominally hand-copying package and notebook requirements into the SPI codebase, then building and PR'ing
  those.  This is just a minimal short-cut and time-saver relative to classic builds under the assumption that the
  wrangler has already been used to define the requirements. Anything outside the scope of requirements-drop-in,
  including the image build and deployment itself, nominally still need to be handled with unchanged
  original processes.  This may include additional work such as updating the post-start-hook appropriately.

# 0.2.0  07-20-2025  Baseline nb-wrangler Python project with injection

- Re-packaged prototype as spacetelescope/nb-wrangler Python project using pyproject.toml
- Re-partitioned and re-wrote prototype as full fledged multi-module package
- Standardized isolated environment management around:
-- micromamba (small fast standalone little brother of mamba for native environment)
-- uv (Modern / pip package manager implemented in Rust for speed)
- Added dedicated nbwrangler (runs tool) and spec'ed (notebook target) environments
- Added simple "nb-wrangler bootstrap" process requiring bash, curl, and git.
- Simplified usage with idempotent "automatic cloning" and "automatic target environment creation"
-- Automatically adds requirements for nb-wrangler to target environment
- Added one-stop --curate switch for --compile --install --test for notebook environment iteration
- Added "SPI injection" to populate the spec'ed science platform images deployment with wrangler outputs
-- Implictly includes extra micromamba/mamba and pip requirements imposed by SPI
- Directly integrated code implementing import testing and notebook testing

# 0.1.0  07-01-2025 Monolithic prototype for demo

- Used to define and implement initial YAML spec inputs and outputs
- Demo'ed basic functionality of environment compilation, installation, and testing
