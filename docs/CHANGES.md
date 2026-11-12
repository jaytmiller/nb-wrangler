**v0.11.0** change notes (since v0.10.0):

> `v0.10.0` above was still unreleased when this line was started, so 0.10.0 + 0.11.0 ship together; the split keeps the `hubenv` consolidation (0.10.0) and the new spec-format feature (0.11.0) legible per the version cadence rule.

### New Features

- **Per-repository `data: on|off` opt-out in the wrangler spec** (`nb_wrangler/constants.py`, `nb_wrangler/spec_manager.py`, `nb_wrangler/spec_validator.py`, `nb_wrangler/data_wrangler.py`; docs `docs/spec-format.md`, `docs/specs/data-off.md`). Each `repositories:` entry may carry an optional `data` field — `on`/`yes`/`true` (default when omitted) or `off`/`no`/`false`, case-insensitive; invalid values fail spec validation with a clear message. `data: off` excludes that repository from all data handling: `DataWrangler.collect()` no longer includes its `refdata_dependencies.yaml` in the data definition (its notebooks/packages are unaffected), saved `out.data.spec_inputs` entries for repositories turned off after curation are filtered out at read time, and every data step (`collect`, `list`, `download`, `delete`, `update`, `validate`, `unpack`, `pack`, `symlink`, `clean-symlinks`) on the `--data-curate` / `--data-reinstall` workflows or the isolated `--data-*` flag path is a logged success no-op (`<step> skipped: no enabled data declarations (data: off).`) with no download/unpack/network activity. When every declared repository is `data: off` and there is no image-wide `refdata_dependencies:`, `--data-curate` / `--data-reinstall` run to green end-to-end defining well-formed empty declarations (`out.data` = `spec_inputs: {}`, `spec_exports: {}`, `pantry_exports: {}`; exports files written with no `export` lines; environment registered with an empty env-var set). `dev_overrides.repositories.<name>.data` composes through the existing per-repo merge (dev-only opt-out under `--dev`, ignored under `--prod`). The image-wide `refdata_dependencies:` section is deliberately *not* suppressed by `data: off` (documented in `docs/spec-format.md`) — a full data-off spec sets `data: off` on every data-bearing repo and omits that section. The `data` key participates in `spec_sha256`: adopting or toggling it requires the usual re-stamp (`nbw --spec-update` / `hubenv relock`). Tests: `tests/test_data_flag_spec.py`, `tests/test_data_off_pipeline.py` (27 new tests; full unit suite 738 passing).

  - `hubenv:` **zero behavioral change by default** — the key is additive and absent in existing specs, so hubenv users see no difference; `hubenv data download/unpack/pack/clean` remain thin wrappers over the same nbw flag-driven path and inherit the no-op: for a fully data-off shelf spec these verbs exit `0` with a logged skip and no network/archive activity. No new imports of `nb_wrangler.hubenv` anywhere; hubenv stays inert for nbw users.

### Versioning

- `__version__` bumped `0.10.0` → `0.11.0` (nbw-significant additive spec-format change).
- `WRANGLER_SPEC_VERSION` **kept at 2.3**: the field is purely additive for v0.11.0 (specs without the key behave exactly as before). Note the reverse direction is not compatible — a pre-v0.11.0 validator rejects the key as an unknown repository keyword — so the field should be adopted only on v0.11.0+ toolchains.

---
**v0.10.0** (unreleased) change notes (since v0.9.5):

### Breaking Changes

- **Relaxed wrangler spec format: header name/python may now coexist with an inline mamba spec** (`nb_wrangler/spec_validator.py`, `nb_wrangler/hubenv/env_spec.py`): the validator previously rejected `kernel_name`/`python_version` in the `image_spec_header` when a second YAML document (inline mamba spec) was present; that mutual exclusivity is lifted. When both sides define a value, the header wins over the inline spec (hierarchy: CLI > wrangler spec header > inline mamba spec) and the override is logged at INFO. Saved shelf specs now always record the effective `kernel_name`/`python_version` in the header, including inline-form ones, so CLI `--name`/`--python` overrides are captured in the header. Every previously valid spec remains valid; `nbw` consumers (e.g. curation) read the header value first, which equals the effective value hubenv recorded.
- **`hubenv env ...` flattened to top-level verbs** (`nb_wrangler/hubenv/parser.py`, `nb_wrangler/hubenv/cli.py`). The former `hubenv env <verb>` command group — all 14 env verbs (`create`, `save`, `restore`, `ls`, `info`, `install`, `uninstall`, `relock`, `rm`, `ensure`, `register`, `unregister`, `activate`, `deactivate`) — is now invoked directly: `hubenv env create` → `hubenv create`, `hubenv env save` → `hubenv save`, and so on. `hubenv var ...` and `hubenv data ...` are unchanged. A bare `hubenv env` (with no verb) is no longer a valid command and is rejected with exit code `2`. Scripts and shell snippets that call `hubenv env ...` must be updated to the flat form.

### Behavior Changes

These tighten or correct `hubenv` behavior; scripts that relied on the old quirks must be updated (per the flatten precedent above we record the changes here rather than ship compatibility shims). See `docs/plans/hubenv-rough-edges-plan.md` and `docs/specs/hubenv.md` §7 (all 13 rough edges resolved in v0.10.0).

- **Strict flag parsing** (`nb_wrangler/hubenv/cli.py`): `parse_known_args` replaced with `parse_args`, so unknown flags/sub-commands (e.g. `hubenv create --nam demo`) are argparse usage errors with exit code `2` instead of being silently dropped.
- **Bare `hubenv var` / `hubenv data` now exit `1`** (previously `0`) when no sub-command is given (`nb_wrangler/hubenv/cli.py`).
- **`hubenv var add` no longer auto-creates a shelf** (`nb_wrangler/hubenv/var.py`): it requires an existing shelf spec and fails with exit `1` plus the hint "Create it first: hubenv create NAME --from-empty" (previously the empty-seed fallback silently created a spec-only shelf as a side effect). `var rm` behavior is unchanged (no-match remains a no-op).
- **`hubenv var ls --export --format json` is rejected** (`nb_wrangler/hubenv/var.py`): the two output modes are now mutually exclusive (usage error, exit `1`); previously JSON silently won over `--export`.
- **`hubenv create` reports seed failures cleanly** (`nb_wrangler/hubenv/env_create.py`): `--from-existing-env` probes no longer leak a raw `ValueError` traceback — the probe is wrapped in `HubenvError` ("Failed to seed spec for 'NAME': …", exit `1`), and the cheap target-existence probe now runs before the seed build (even under `--dry-run`).
- **`hubenv restore --at-boot` / `hubenv rm` no longer touch `~/.bashrc`** (`nb_wrangler/hubenv/env_restore.py`, `nb_wrangler/hubenv/env_rm.py`): `--at-boot` only writes `~/.hubenv/env-<name>.sh` and prints the `source` instruction for the user to add to their shell startup; `hubenv rm` now best-effort removes that snippet when it deletes an env.
- **`hubenv ensure --display-name` is now honored** (`nb_wrangler/hubenv/env_ensure.py`, `nb_wrangler/hubenv/env_restore.py`): the delegated kernel registration uses the supplied display name (falling back to the env name) instead of always the env name.
- **`hubenv export --to-requirements` warns on empty output** (`nb_wrangler/hubenv/export.py`): a spec with no pip packages still exits `0`, but now prints a stderr warning instead of a silent empty result.
- **`hubenv doctor` no longer checks EFS** (`nb_wrangler/hubenv/doctor.py`): the Linux-only `/proc/mounts`-based EFS check was removed; doctor now runs 4 checks (mamba/micromamba, pantry writability, kernel-JSON sanity, spec-only shelves). Non-EFS / non-Linux installs no longer see a red EFS row.
- **`hubenv rm` confirmation prompt goes to stderr** (`nb_wrangler/hubenv/env_rm.py`): the "Proceed? (y/N)" prompt was on stdout, mixing with the machine-readable plan print; it is now on stderr (answer still read from stdin).
- **`--name` no longer required for most `hubenv create` sources, and the file-stem fallback is gone** (`nb_wrangler/hubenv/parser.py`, `nb_wrangler/hubenv/env_create.py`, `nb_wrangler/hubenv/seeds.py`): `--from-mamba-spec` now defaults to the spec's own `name`, `--from-wrangler-spec` to the header `kernel_name` → `image_name` → inline mamba spec `name`, and `--from-existing-env` to the source environment's own name, making imports seamless. The name is now resolved by the strict hierarchy CLI > wrangler spec header > mamba spec; when a source defines no name at any level the seed fails with a clean error (exit `1`) instead of silently deriving a name from the spec file's stem. `--from-empty` and `--from-requirements` still require `--name` and now fail with a clean `HubenvError` ("`--name is required for --from-empty and --from-requirements`", exit `1`) instead of proceeding with an empty name.
- **`--python` now affects `--from-wrangler-spec` and `--from-existing-env`** (`nb_wrangler/hubenv/seeds.py`): for wrangler specs it overrides the header `python_version` (previously silently ignored); for existing-env imports, when `--python` is omitted, the source env's own Python pin (first conda dep starting with `python`) is restored as the first conda dependency instead of being dropped.
- **`--python` now also affects `--from-mamba-spec`** (`nb_wrangler/hubenv/seeds.py`): previously the CLI pin was ignored and the spec file's `python=` pin always won; now it resolves CLI > spec pin, the override is logged, and stale compiled pip lock entries are cleared on a pin change. Existing-env and wrangler imports share the same override path (`_resolve_python`), so the override log and lock-clearing apply uniformly.
- **`--display-name` now delegates to the wrangler spec header and is recorded** (`nb_wrangler/hubenv/seeds.py`, `env_create.py`, `env_spec.py`, `env_restore.py`, `env_ensure.py`): the kernel display name resolves as CLI > wrangler spec header `display_name` > env name (only wrangler sources carry a display-name field); the effective value is recorded in the saved shelf spec's header, and `create`/`restore`/`register`/`ensure` all register the kernel under it (CLI always wins). Previously the header's `display_name` was always the env name, and only the CLI value was honored at register time.

### Bug Fixes

- **`nb-wrangler act` regression fixed** (`nb-wrangler`, `nb_wrangler/cli.py`). Since the `hubenv env ...` flattening, `act` delegated to the removed `python -m nb_wrangler.hubenv.cli env activate ...` form, which the CLI rejected (usage error) — and with stderr swallowed, `nb-wrangler act NAME` **silently failed to activate**. `act` now delegates to the `nbw` CLI like `setenv`/`deact` do (`python -m nb_wrangler NAME --env-activate --quiet`), removing the nb-wrangler script's last runtime dependency on the `hubenv` CLI. This required additive name-based activation support in the `nbw` CLI: a new `_activate_by_name()` path (`nb_wrangler/cli.py`) treats the positional argument as a live environment name when it is not an existing file or explicit URI and the environment exists, emitting the shared shell-activation snippet; spec-based activation (`nbw SPEC --env-activate`) is unchanged. Tests: the delegation contract in `tests/test_nbwrangler_bash_delegation.py` now asserts the `nbw` CLI form (and no `hubenv` in the argv), and new `TestNbwActivateByName` cases in `tests/test_activation.py` cover the name path (existing env, spec file, URI, unknown name).
- **Spec-hash stability: one canonical `spec_sha256` algorithm** (`nb_wrangler/spec_manager.py` — new `canonical_spec_sha256()` / `legacy_spec_sha256()`; `nb_wrangler/hubenv/env_spec.py`). The branches historically computed `spec_sha256` over different serializations that could disagree with each other and with stored hashes depending on which dumps had run earlier in the same process (ruamel comment state, absent-vs-blank hash key) — validation could fail on unmodified specs and re-stamped hashes could disagree across runs. There is now a single canonical digest: the spec (including any inline mamba document) converted to plain Python data (JSON round-trip strips all ruamel comment/quote metadata) with `system.spec_sha256` present-and-blank, which `SpecManager.add_sha256()` stamps, `SpecManager.validate_sha256()` / `_stored_hash_is_valid()` check (non-mutating), and hubenv's seed stamping (`env_spec._compute_spec_sha256()`) shares, so the two apps agree by construction in any process history. `validate_sha256()` accepts, for **one release of migration grace**, a stored hash that matches the legacy candidate (the stored file's own text with the hash line blanked); anything else fails with a pointer to `nbw --spec-update` / `hubenv relock` to re-stamp. The shipped `sample-specs/` were re-stamped to the canonical digest (hash line only — every other byte preserved, including the previously-unstable `tike-wrangler-k1.yaml` case). New regression suite: `tests/test_spec_hash_stable.py` (9 tests: dump-history stability incl. two-document and commented specs, absent-vs-blank normalization, non-mutation, shipped-sample validation, stamp→save→reload→validate round-trip, legacy acceptance, rejection, hubenv/nbw parity).
- **`tabulate` demoted from hard dependency to the optional `hubenv` extra** (`pyproject.toml`, `nb_wrangler/hubenv/{_common,env_info,status,doctor}.py`). Only `hubenv status`, `hubenv info`, and `hubenv doctor` use `tabulate`; it is now imported lazily via a guarded `tabulated()` helper in `nb_wrangler/hubenv/_common.py` (which raises a clean error with the install hint — `pip install tabulate` or `pip install 'nb-wrangler[hubenv]'` — when absent). Plain `nbw` installs no longer pull the dependency (keeps the "hubenv must not widen the nbw footprint" rule); the mypy override for it is retained.

### New Features

- **`--pantry` on `export` and `var ls` / `var add` / `var rm`** (`nb_wrangler/hubenv/parser.py`, `_common.py`, `export.py`, `var.py`): these commands now accept `--pantry PATH` to scope pantry lookups to a single pantry (via `_common.store_for`), matching the other 7 pantry-aware verbs. `data *`, `status`, `doctor`, `register`/`unregister`, `activate`/`deactivate` intentionally remain default-chain only.
- **Shell completions match the flattened command tree** (`nb_wrangler/hubenv/completions.py`): the embedded command tree now covers all 20 top-level verbs (including `activate`/`deactivate`, previously missing) and no generated script suggests the removed `hubenv env <verb>` shape.
- **`--quiet-downloads` flag for CI pipelines** (`nb_wrangler/utils.py`, `nb_wrangler/pantry.py`, `nb_wrangler/config.py`): first released on the `0.9.x` line as 0.9.5 (section below) and carried into this consolidated line, so a user upgrading directly from 0.9.4 sees it here as well; see the 0.9.5 entry for the full description and tests.

---
**v0.9.5** change notes (since v0.9.4):

### New Features

- **`--quiet-downloads` flag for CI pipelines** (`nb_wrangler/cli.py`, `nb_wrangler/config.py`, `nb_wrangler/pantry.py`, `nb_wrangler/utils.py`). When passed, nb-wrangler's data downloads run with reduced wget output: wget's captured output is discarded on success, and on a failed download the output is printed to **stderr** along with the `DataDownloadError` (and included in the error message), so CI pipelines stay quiet on success yet remain debuggable after failures. Behavior without the flag is unchanged — wget output still goes directly to the terminal as before.
  - `robust_get()` gains a `reduced_output` parameter (`nb_wrangler/utils.py`); new helpers `_exc_output()` and `_report_wget_failure()` isolate the timeout/failure reporting paths, both of which surface captured output.
  - `WranglerConfig` gains the `quiet_downloads` field (`nb_wrangler/config.py`); `NbwShelf._quiet_downloads()` reads it and passes it through `NbwShelf.download_data()` (`nb_wrangler/pantry.py`).
  - New tests: `tests/test_quiet_downloads.py`, plus `quiet_downloads` coverage in `tests/test_config.py` and the `reduced_output` failure-path tests in `tests/test_utils.py`.

### Not included in this release (reverted on this line)

- **The "spec-update protocol consolidation" (commit `62ce658`) was reverted from the `0.9.x` line before cutting this release**, deliberately, so that this stable line and the `hubenv` development line (`plan-b-rebased`) can be consolidated without semantic conflict (see `docs/combine-branches.md` for the decision record). Concretely, 0.9.5 does **not** ship:
  - the `--reinstall`/`--data-reinstall` non-mutation fix for wrangler specs,
  - the `SpecManager.update_and_save()` designated save path,
  - the non-mutating `validate_sha256()` (deep-copy hash routine), or
  - the `SpiInjector.inject()` failure-on-archive-save hardening.
  - **The goals of that work are still met in the next release line (0.10.0)**, which achieves `--reinstall`/`--data-reinstall` non-mutation through content-aware spec saving (a save to an unchanged source spec is a byte-for-byte no-op). The held-back acceptance suite (`tests/test_readonly_specs.py`, 12 tests) and `docs/plans/readonly-specs-plan.md` are retained as the gate for re-implementing the remaining pieces on `main` after the branch consolidation.
- **v0.9.4** (tag `v0.9.4` / commit `dabd577`) was a version-bump-only release and therefore has no section of its own; this section covers everything since v0.9.3 that is not already noted above.

### Verification

- `make unit-test`: 298 passed (0.9.4 line was 310; the 12-test `tests/test_readonly_specs.py` suite was removed with the revert above).
- `make lint/black`, `make lint/flake8`, `make lint/radon`, `make lint/mypy`: clean.

---

**v0.9.3** change notes (since v0.9.2):

### Bug Fixes

- **`--packages-omit-spi` flag now effective** (`nb_wrangler/compiler.py`). The `packages_omit_spi` config flag was checked but had no effect during requirements compilation — SPI pip files were still included in the gathered `spi_pip_files` list. The flag is now respected: when `self.config.packages_omit_spi` is set, `spi_pip_files` is an empty list, skipping inclusion of SPI pip requirements.

### Micromamba Environment Isolation Fixes

- **`wrangler_run` now injects `MAMBA_ROOT_PREFIX`** (`nb_wrangler/environment.py`). When a system-level micromamba is installed, shell init scripts set `MAMBA_ROOT_PREFIX` (and `MAMBA_EXE`) to the system installation. Without an explicit override, subprocess calls could find the wrong `micromamba` binary or look for environments in the wrong directory, leading to PEP 668 errors from system Python. `wrangler_run` now always sets `MAMBA_ROOT_PREFIX` to nb-wrangler's own `NBW_MM` directory in the subprocess environment.
- **Removed `MAMBA_ROOT_PREFIX` / `CONDA_ROOT_PREFIX` fallbacks from `NBW_ROOT` and `NBW_MM`** (`nb_wrangler/constants.py`). These fallbacks caused nb-wrangler to adopt a system-level micromamba's root prefix as its own installation directory, causing environment lookups to fail. `NBW_ROOT` and `NBW_MM` now default strictly to `~/.nbw-live` and `~/.nbw-live/mm` respectively.

- **`--quiet`/`-q` now suppresses startup version log** (`nb_wrangler/cli.py`). The `WranglerLogger` is now constructed with `quiet=args.quiet`, so the `Wrangler version:` INFO message is suppressed when `--quiet` is passed. Previously, version output was guarded by an `if not args.quiet` check that bypassed the logger's own quiet mode.
- **`--env-print-name --quiet` suppresses all output except environment name** (`nb_wrangler/cli.py`). Specifying no spec results in no output but exit status 1.

### Timeout Constants

- **New `PULL_TIMEOUT` constant** (`nb_wrangler/constants.py`). Docker `pull` operations now use a dedicated 1-hour (3600s) timeout (`PULL_TIMEOUT` in `constants.py`, imported into `registry.py`), instead of the generic `DEFAULT_TIMEOUT`.
- **Increased `DEFAULT_TIMEOUT`** from 300s to 600s.

### Tests Added

- `tests/test_environment.py` — `TestWranglerRunMambaRootPrefix` test class verifying that `wrangler_run` injects `MAMBA_ROOT_PREFIX` into the subprocess environment and respects explicitly provided `env` dicts.
- `tests/test_logger.py` — `test_quiet_suppresses_stderr`, `test_quiet_does_not_suppress_stdout`, and `test_non_quiet_outputs_to_stderr` tests for the `quiet` parameter on `WranglerLogger`.

---

**v0.9.2** change notes (since v0.9.1):

### Bug Fixes

- **Fixed `--packages-ignore-versions` path bug** (`nb_wrangler/compiler.py`). `_strip_versions_from_requirements` previously embedded the *full filesystem path* of each requirements file into the stripped output filename (e.g. `stripped_/home/.../aperture_photometry/requirements.txt_abc123.txt`). Path separators were interpreted as directory separators, so the stripped file was written to a nested path that never matched what the compiler subsequently looked for, causing a `FileNotFoundError`. The filename now uses only `Path(req_file).name`, keeping stripped files flat in the output directory while the sha256 hash continues to disambiguate duplicate basenames.

### Behavior Changes

- **`--print-repo-tags` now resolves tags against the live remote** (`nb_wrangler/wrangler.py`).
  _Provenance note: this rework was previously listed under v0.9.0, but per git history (commits `fdc3011`, `fb76b8b`) it first landed after the `v0.9.1` tag; the note was moved here for accuracy against the actual released code._
  - Uses `git ls-remote --tags <url>` (no clone required) to enumerate tags for each repo URL.
  - Version-prefix refs (e.g. `2026.2`) are resolved to the highest `x.y.z` tag with the greatest numeric `z`.
  - Non-version refs (e.g. `main`) are returned as-is when no matching tags are found.

---

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

- **`--print-repo-tags` flag** added to print one `url ref` line per spec repository. As of this release it printed the spec's `ref`/`resolved_ref` without querying remotes; the `git ls-remote --tags` rework shipped in **v0.9.2** (see those notes).

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

- **Sample Spec Updates**: Updated `sample-specs/RomanNexus-2026.2.yaml` to illustrate latest spec format (version 2.3) extensions, including new package-list override support and cleaned `dev_overrides` sections. Added baseline 2026.2 Roman spec for tagging dev. Added `specs/roman/astroquery-mast-test.yaml` and `specs/jwebbinar/jwebbinar-50.yaml`.

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
