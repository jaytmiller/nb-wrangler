**v0.9.0** change notes:

**62 new commits**, **5,947 insertions**, **229 deletions** across 24 files.

### Major New Features

1. **Assets Injection** (`nb_wrangler/injector.py` + 207 lines, `tests/test_assets_injection.py`)
   - New `assets:` spec section to bundle static files from git repos into Docker images during SPI injection/curation
   - Supports flat syntax (single item) and grouped syntax (`items:` sub-list sharing common repo/ref)
   - `contents_only` flag for copying directory contents rather than the directory itself
   - Source paths support trailing `/` notation for contents-only mode + glob patterns
   - Generates `install-assets.sh` script in the environments directory

2. **System Commands Override** (`system.commands.{mamba, pip, favor}`)
   - New spec-level `system.commands: { mamba: ..., pip: ..., favor: ... }` section to override Mamba/pip executables
   - `favor` controls precedence when both env vars AND spec define values: `spec` (default) or `environment`
   - CLI flags (`--mamba-cmd`, `--pip-cmd`) always override both spec and env vars

3. **NBW_OVERRIDES_MODE** Environment Variable
   - Set to `--dev` or `--prod` to change default override behavior for all workflows (default is `--prod`)
   - Replaces earlier reliance on implicit heuristic detection of dev/prod mode

4. **Calver Tag Resolution** (repository checkout)
   - Automatic resolution of abstract tags (branch prefixes like `2026.2`) by listing git tags, sorting descending, and picking highest matching prefix
   - Falls back to partial SHA when full tag resolution fails
   - Added `tests/test_tag_prefix_resolution.py`

5. **YAML Type Normalization** (`nb_wrangler/yaml_typed_values.py`)
   - New module that normalizes YAML values (dates, numbers, booleans) to strings via `yaml_typed_values.normalize_value()`
   - Prevents type mismatches between YAML-typed and string comparison downstream

6. **Default Image Registry Change**
   - Default registry changed from generic to `spacetelescope/nb-wrangler-images`

7. **Default Environment Variables Mode Changed**
   - Default env-vars mode switched from `spec` to `pantry` (no longer creates refdata symlinks)

8. **Bootstrap Script Fixes**
   - Commented out micromamba self-update (was hanging functional tests)
   - Added `set +x` to prevent debug output pollution
   - Updated for NBW_MAMBA_DEFAULT vs NBW_MAMBA_CMD refactoring

9. **Pantry Read-Only Safety** (`tests/test_readonly_pantry.py`)
   - Pantry on-demand directory creation added to avoid crashes when users/post-start-hook tries to modify read-only pantries

10. **`--quiet`/`-q` Flag**
    - Suppresses all log output to stderr (stdout still visible for --spec-name, --docker-list etc.)

11. **`--print-repo-tags` Enhancement**
    - Resolves and outputs `resolved_ref` from the spec's `out.repositories:` section if available

12. **Renamed**: `--finalize-dev-overrides` -> `--spec-disable-dev-overrides`

13. **Environment Variables** (`environment_vars`, `test_environment_vars`)
     - New top-level `environment_vars:` spec section, like variables in refdata_dependencies.yaml but specified directly in the wrangler spec; merged into refdata during data collection
     - New `test_environment_vars:` spec section to inject test-scoped env vars via `_inject_test_env_vars()` before notebook/import tests run

14. **`--test-isolate-notebook` Flag** (`config.py`, `environment.py`)
     - Controls whether notebook tests run in an isolated temp copy or in-place (default is now in-place)

15. **Default Notebook Behavior Changed to In-Place** (`environment.py`)
     - Replaced `test_directory_setup()` on-demand temporary tree copy with conditional: isolated only when `--test-isolate-notebook` is set; otherwise uses notebook's parent directory as test_dir

16. **`copy_shared_modules` Idempotency** (`utils.py`)
     - Skips copying if the file or a like-named symlink already exists in the destination

17. **Bugfix: `override_pip_packages` Undefined Handling** (`compiler.py`)
     - Fixes erroneous build-arg string when `override_pip_packages` is undefined

18. **Papermill Path Fix** (`notebook_tester.py`)
     - Changed papermill invocation to pass the full notebook path instead of `os.path.basename()` only

19. **Registry Environment Variables** (`constants.py`)
     - Added reading of `NBW_IMAGE_REGISTRY` and `NBW_IMAGE_PROJECT` env vars before applying default registry/project values

20. **`--data-clean-symlinks` Flag** (`cli.py`, `config.py`, `wrangler.py`)
     - Controls cleanup of symlinks from spec locations to pantry installations; relies on `--data-env-vars-mode` to distinguish pantry vs spec modes
     - Nutshell:  roman_notebooks "refdata" symlink is going away,  look at the environment variables to identify where the data is
     - Environment variables will track the selected notebook kernel / active environment within notebooks and terminal sessions.

21. **Notebook Progress Counter** (`notebook_tester.py`)
     - Displays "X/Y notebooks" progress during notebook tester runs

22. **Dockerfile-aux.sh Auto-Cleanup** (`injector.py`)
     - Added auto-code to `dockerfile-aux.sh` to remove itself after execution completes, preventing leftover build artifacts

23. **Asset/Symlink Cleanup Post-Install** (`injector.py`)
     - Appends cleanup commands to end of `install-assets.sh`: removes the `/opt/environments/assets` staging directory and `install-assets.sh` itself, eliminating `/opt/environments` clutter

24. **Fix: `resolve_var` Typo** (`utils.py`)
     - Corrected function name from `resolve_var` to `resolve_vars` in wrangler utils

25. **Fix: `input()` Bugs in Non-TTY Context** (`notebook_tester.py`, `wrangler.py`)
     - Fixed bugs in notebook location prompting and `input()` calls that crashed in non-tty contexts

### Tests Added (13 new/updated files)
- `tests/test_assets_injection.py` — asset injection tests
- `tests/test_config.py` (180 lines) — config parsing tests
- `tests/test_constants.py` (148 lines) — constants validation tests
- `tests/test_environment.py` — environment setup and teardown tests
- `tests/test_logger.py` (108 lines) — logger tests
- `tests/test_readonly_pantry.py` — read-only pantry safety tests
- `tests/test_registry.py` — registry function tests
- `tests/test_spec_manager_extended.py` (318 lines) — spec manager extended tests
- `tests/test_spec_validator.py` (367 lines) — spec validator tests
- `tests/test_tag_prefix_resolution.py` — calver tag resolution tests
- `tests/test_utils.py` (368 lines) — utility function tests
- `tests/test_yaml_typed_values.py` (82 lines) — YAML typed value normalization tests
- `specs/roman/RomanNexus-2026.2.yaml` (new baseline 2026.2 Roman spec for tagging dev)
- `specs/roman/astroquery-mast-test.yaml`
- `specs/jwebbinar/jwebbinar-50.yaml`

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
