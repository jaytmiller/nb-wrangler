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