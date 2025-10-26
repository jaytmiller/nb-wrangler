# 0.5.0  10-24-2025  Data and Shared Data Handing

- Added workflows and steps for collecting and curating data from notebook repos
- Validates refdata_dependencies.yaml files scraped from notebook repos.
- Collects data urls, sizes, archive hashes, env var definitions
- New CLI steps:
    - --data-collect
    - --data-validate-refdata-yaml
    - --data-download
    - --data-update-validation-info
    - --data-validate-local
    - --data-install (unpack)
    - --data-remove  (delete)
    - --data-repack  (repack and update spec metadata)
    - --data-env-vars
    - --data-list
- Idemotently downloads data using HEAD size, etag
- Validates locally using sha256
- Packs / Unpacks data / Updates internal metadata for changes
- Supports overriding env vars for data path resolution
- Populates environments with data env vars pointing to unpacked data

# 0.4.0  10-01-2025  Re-install and submit-for-build workflows

- Added workflow for pushing wrangler spec to GitHub to trigger build

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