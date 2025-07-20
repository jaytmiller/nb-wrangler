# 0.2.0  07-20-2025 Baseline nb-curator Python project with injection

- Re-packaged prototype as spacetelescope/nb-curator Python project using pyproject.toml
- Re-partitioned and re-wrote prototype as full fledged multi-module package
- Added dedicated nbcurator and <target> environments
- Standardized isolated environment management around:
-- micromamba (small fast standalone little brother of mamba for native environment)
-- uv (Modern / pip package manager implemented in Rust for speed)
- Added dedicated nbcurator (runs tool) and spec'ed (notebook target) environments
- Added simple "nb-curator bootstrap" process requiring bash, curl, and git.
- Simplified usage with idempotent "automatic cloning" and "automatic target environment creation"
-- Automatically adds requirements for nb-curator to target environment
- Added one-stop --curate switch for --compile --install --test for notebook environment iteration
- Added "SPI injection" to populate the spec'ed science platform images deployment with curator outputs
-- Implictly includes extra micromamba/mamba and pip requirements imposed by SPI
- Directly integrated code implementing import testing and notebook testing

# 0.1.0 07-01-2025 Monolithic prototype for demo

- Used to define and implement initial YAML spec inputs and outputs
- Demo'ed basic functionality of environment compilation, installation, and testing