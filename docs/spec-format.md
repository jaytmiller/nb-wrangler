# Wrangler Spec Format

You can generate a basic default wrangler spec template using the `--spec-init` command:

```bash
nbw --spec-init my-spec.yaml
```

## Example Spec

Below is a prototype wrangler spec for TIKE in the new format:

```yaml
# Image header information
image_spec_header:
  image_name: TIKE 2025.07-beta
  deployment_name: tike
  kernel_name: tess
  display_name: TESS
  description: |
    This is a beta test of the latest TIKE packages. Use at your own risk!
  valid_on: 2025-07-02
  expires_on: 2025-10-02
  python_version: 3.11.13

# Repositories where notebooks are located
repositories:
  tike_content:
    url: https://github.com/spacetelescope/tike_content
    ref: main
  mast_notebooks:
    url: https://github.com/spacetelescope/mast_notebooks
    ref: main

# Named blocks for selecting notebooks
selected_notebooks:
  tike_lcviz:
    repo: tike_content
    root_directory: content/notebooks/lcviz-tutorial/
    include_subdirs: [ "." ]
    tests:
      papermill: false # This notebook is known to fail papermill tests
  tike_data_access:
    repo: tike_content
    root_directory: content/notebooks/data-access/
    include_subdirs: [ "." ]
  mast_kepler:
    repo: mast_notebooks
    root_directory: notebooks/Kepler
    include_subdirs:
      - identifying_transiting_planet_signals
      - instrumental_noise_4_electronic_noise

extra_mamba_packages:
  - pip
common_mamba_packages:
  - hdf5
extra_pip_packages:
  - boto3
common_pip_packages:
  - requests

apt_packages:
  - curl
  - vim

dockerfile_aux_sh: |
  # Install some extra stuff
  echo "Installing extra stuff..."
  apt-get update && apt-get install -y some-extra-pkg

system:
  spec_version: 1.0
  archive_format: .tar
  primary_repo: tike_content
  nb-wrangler:
    repo: https://github.com/spacetelescope/nb-wrangler.git
    ref: main
  spi:
    repo: https://github.com/spacetelescope/science-platform-images.git
    ref: main
```

## Sections of the Wrangler Spec

### **image_spec_header**
This section provides metadata about the image and Python environment.
   - **image_name**: A name for your image (e.g., `TIKE 2025.07-beta`).
   - **deployment_name**: The deployment name, which can be `tike`, `roman`, `jwebbinar`, or `wrangler`.
   - **kernel_name**: The kernel name, currently `tess`, `roman-cal`, or `masterclass` for SPI injection,  anything for wrangler.
   - **display_name**: The name as it will appear in the JupyterLab kernel selection list (e.g., `TESS`).
   - **description**: A brief description of the image and its purpose.
   - **valid_on** and **expires_on**: Dates specifying when the image becomes valid and when it expires, respectively.
   - **python_version**: The version of Python supported by the image (e.g., `3.11.13`). This is used for simple definition environments and is mutually exclusive with `environment_spec` or an inline mamba spec.

### **repositories**
This section defines a dictionary of the git repositories that contain notebooks. Each repository is given a short, memorable name that will be used to refer to it in the `selected_notebooks` section.

Each entry in `repositories` has the following fields:
- **url**: The URL of the git repository.
- **ref**: The git branch, tag, or commit hash to use (defaults to `main`).

### **dev_overrides**
This optional top-level section allows developers to temporarily override any top-level sections of the spec for development purposes without modifying the core production-ready configuration.

When the `--dev` CLI flag is used (or implicitly activated for curation workflows), `nbw` will apply these overrides. When the `--prod` flag is used, these overrides are explicitly ignored. When `--spec-disable-dev-overrides` is used, this section is deactivated.

The structure of `dev_overrides` mirrors the top-level sections it intends to override. For example, to override `repositories` (including `url` for forked development), `refdata_dependencies`, and `system.spi`:

```yaml
dev_overrides:
  repositories:
    your_repo_name:
      url: https://github.com/your-fork/your_repo_name # Override URL for forked development
      ref: your-dev-branch
    another_repo:
      ref: another-dev-ref
  refdata_dependencies:
    other_variables:
      YOUR_VAR: "dev_value"
  system:
    spi:
      ref: your-spi-dev-branch
```


### **selected_notebooks**

This section is a dictionary of "selection blocks". Each block has a unique name and defines a set of rules for selecting notebooks from the declared repositories. This is the heart of the wrangler spec as it also implies Python package (per-notebook `requirements.txt`) and data requirements (global per-repo `refdata_dependencies.yaml`).

Each selection block has the following fields:

  - **repo**: The name of a repository defined in the `repositories` section.
  - **root_directory**: Defines the root directory within the repository where the notebooks are stored.
  - **include_subdirs**: A list of subdirectories or regex patterns under `root_directory` to include.
  - **exclude_subdirs**: A list of subdirectories or regex patterns under `root_directory` to exclude.
  - **tests**: An optional dictionary to specify test configurations. For example, `tests: { papermill: false }` will disable the default `papermill` test for notebooks in this block.

The combination of `root_directory`, `include_subdirs`, and `exclude_subdirs` is flexible and allows different selection styles:

1. Pick notebook directories directly under `root_directory` as individual `include_subdirs` lines.  This avoids the clutter of repeating `root_directory` with each notebook in an otherwise simple explicit list.
2. To keep things simple, leave `root_directory` as an empty string and just include the full path from the root of the repo to the notebook directory in `include_subdirs`.
3. Use regular expressions in `include_subdirs` and `exclude_subdirs` to select notebooks based on patterns. For example, `include_subdirs: [".*"]` will include all notebooks under the `root_directory`.

> **Note on orphan `requirements.txt` files:** In addition to notebooks, `requirements.txt` files are discovered by globbing under `selected_notebooks` selections — including directories that contain only a `requirements.txt` and no notebooks. Such files are logged with an "(orphan)" prefix in the debug output. This allows package-only directories to contribute dependencies to the environment even when no notebooks are selected from them.

### **out**

This section is written to the spec by `nbw` during curation and contains the results of the curation process (found notebooks, resolved imports, compiled environment, etc.). Curators typically do not write to this section manually.

Known output fields include:

- **`data`**: Data dependencies collected from notebook repositories' `refdata_dependencies.yaml` files and the top-level `refdata_dependencies` section.
- **`repositories`**: Resolved repository information including `resolved_ref` for each repository.
- **`non_mamba_pip_package_files`**: A mapping of `requirements.txt` file paths to their expanded (sorted, version-pinned) package lists. This field is written during `--packages-compile` / `--curate` and reflects the pip requirements discovered via `SpecManager.get_requirements_files()` globbing, including orphan `requirements.txt` files in directories with no notebooks.
- **`spec_sha256`**: An sha256 hash of the spec when it was last saved, for integrity checking.
- **`date_updated`**: The timestamp when the spec was last updated.

### **refdata_dependencies**

This optional section allows for image-wide data dependencies defined directly in the wrangler spec. These dependencies are merged with any `refdata_dependencies.yaml` files discovered at the root of the notebook repositories.

This is useful for decoupling data definitions from specific notebook repositories, or for providing common data needed by all notebooks in the image.

The format follows the same structure as the repository-level `refdata_dependencies.yaml` files:
- **install_files**: A dictionary of data packages to download and unpack.
- **other_variables**: A dictionary of environment variables to set.

See [Reference Data Dependencies](refdata_dependencies.md) for more details on the format.

### **environment_vars**

Optional top-level dict of environment variable definitions authored directly in the wrangler spec, decoupled from data installation concerns. These take the same form as entries under `refdata_dependencies` -> `other_variables` — a mapping of `VAR_NAME: value`. Values may include `${VAR}` style resolution references. Variables defined here are merged into the nbw-spec data entry during `--data-curate` and flow through the normal `spec_exports` / `pantry_exports` pipeline, participate in cross-source env-conflict checking, and can be overridden via `dev_overrides.environment_vars`.

Example:

```yaml
environment_vars:
  MY_VAR: "hello"
  OTHER_PATH: "${HOME}/data"
dev_overrides:
  environment_vars:
    MY_VAR: "overridden"
    NEW_VAR: "new_value"
```


### **test_environment_vars**

Optional top-level dict of environment variables scoped only to the testing phase (notebook and import tests). These do **not** apply during curation, SPI build, or environment register steps. The format is the same as `environment_vars` — a mapping of `VAR_NAME: value`, where values may include `${VAR}` style resolution references that are resolved against the current `os.environ` at test time.

These variables are injected into `os.environ` just before each test run and can be overridden via `dev_overrides.test_environment_vars` when running with the `--dev` flag.

Example:

```yaml
environment_vars:
  DATA_DIR: "/opt/data"          # always available during curation
test_environment_vars:
  TEST_API_KEY: "mock_secret"     # only available during tests
  CRDS_PATH: "${HOME}/crds_mock/"
dev_overrides:
  test_environment_vars:
    TEST_API_KEY: "dev_key"       # overridden in dev mode
    NEW_TEST_VAR: "extra_value"   # added in dev mode
```

### **extra_mamba_packages**
A list of additional mamba packages required specifically by your curated kernel environment.

### **common_mamba_packages**
A list of additional mamba packages required by your curated kernel environment that are *also* required by the science platform's base environment. When using SPI injection (`--inject-spi`), these packages are written to `common-hints.mamba` to ensure they are available across all environments in the image.

### **extra_pip_packages**
A list of additional pip packages required specifically by your curated kernel environment.

### **common_pip_packages**
A list of additional pip packages required by your curated kernel environment that are *also* required by the science platform's base environment. When using SPI injection (`--inject-spi`), these packages are written to `common-hints.pip` to ensure they are available across all environments in the image.

### **apt_packages**
A list of system-level packages to be installed via `apt-get`. When using SPI injection (`--inject-spi`), these packages are written to `apt-packages.txt` and will be installed during the image build process.

### **dockerfile_aux_sh**
A block of text that will be written to `environments/dockerfile-aux.sh` as-is during SPI injection (`--inject-spi`). This is nominally used for custom bash commands that need to be executed during the image build process.

### **system**
This section contains specifications for the system environment. It is updated by `nbw` automatically and should rarely need curator updates.

   - **spec_version**: The version of the specification being used (e.g., `2.3`). nb-wrangler validates this against its supported `WRANGLER_SPEC_VERSION`:
      - A spec version equal to `WRANGLER_SPEC_VERSION` is fully supported.
      - An older version triggers a deprecation warning suggesting an update.
      - A newer version triggers a warning that some features may not be recognized and nb-wrangler should be upgraded. See [Spec Validation](#spec-validation).
   - **archive_format**: The format used for archiving environments (e.g., `.tar`).
   - **primary_repo**: The name of the primary repository (must match a key in the `repositories` section). This repository is treated as the "owner" of the spec and is used to drive automated workflows.
   - **nb-wrangler**: A dictionary specifying the `nb-wrangler` repository to use for the curation process.
      - **repo**: The URL of the git repository.
      - **ref**: (Optional) The branch, tag, or commit hash to use.
   - **spi**: A dictionary specifying the Science Platform Images (SPI) repository to use.
      - **repo**: The URL of the git repository.
      - **ref**: (Optional) The branch, tag, or commit hash to use. Defaults to the repository's default branch.
   - **commands**: A dictionary for overriding Mamba and/or pip executables at the spec level. See [Custom Command Line Tools](#custom-command-line-tools) below. When using SPI injection (`--inject-spi`), these settings influence which `mamba`/`pip` commands are used during curation but are not injected into the SPI repo directly.
   - **spec_sha256**: An sha256 hash of the spec when it was last saved, for integrity checking. It is added by `nbw`.
   - **date_updated**: The timestamp when the spec was last updated.


### Custom Command Line Tools

The `system.commands` section in the wrangler spec allows overriding the Mamba and pip executables used during curation. This is useful when working with different mamba/pip implementations across environments or for testing.

```yaml
system:
  commands:
    mamba: /opt/micromamba/bin/micromamba   # Override the mamba executable
    pip: conda run -n base pip               # Override the pip executable
    favor: environment                         # See below
```

The `favor` field controls precedence when both this spec setting and the `NBW_MAMBA_CMD`/`NBW_PIP_CMD` environment variables are set:

- **`favor: spec`** (default): The spec values take priority over environment variables.
- **`favor: environment`**: The environment variables take priority over spec values.

Note that CLI flags `--mamba-cmd` and `--pip-cmd` always override both the spec and environment variable settings, regardless of `favor`.

For more details on precedence rules, see [Wrangling with Custom Tools](docs/notebooks_and_environment.md#wrangling-with-custom-tools).

### **assets**

The optional `assets` section allows you to bundle static files from git repositories into the Docker image for use during notebook runtime or testing. This is useful for including configuration files, reference data, or other resources that the notebooks need at runtime but cannot be distributed via pip or mamba.

During SPI injection (`--inject-spi`) or standard curation workflows, `nb-wrangler` will:
1. Clone the specified repository at the given ref
2. Copy selected source paths to a local staging area
3. Generate an `install-assets.sh` script that copies the staged assets into their final destination in the Docker image

Two syntaxes are supported:

**Flat syntax (single item):**
```yaml
assets:
  - repo: https://github.com/example/config-repo.git
    ref: main
    source: config/production/settings.yaml
    destination: /opt/app/config/settings.yaml
```

**Grouped syntax (shared repository, multiple sources):**
```yaml
assets:
  - repo: https://github.com/example/shared-configs.git
    ref: v1.2.3
    items:
      - source: config/prod/
        destination: /opt/app/config/
      - source: templates/
        destination: /opt/app/templates/
```

The flat syntax copies one file. Grouped syntax clones the repo once and then copies each source item listed under `items` to its respective destination. When using grouped syntax with directory sources (paths ending in `/`), the folder is copied into the destination rather than appended to it. Individual files are placed *inside* the specified destination path.

Each asset entry supports the following fields:
- **repo**: The URL of a git repository containing the assets. Must match a repo already declared in `repositories`, or can be a new URL cloned just for this purpose.
- **ref**: (Optional) The git branch, tag, or commit hash. Defaults to `main`.
- **source**: The path within the repository to copy. Supports glob patterns and directories.
- **destination**: The destination path inside the Docker image where assets will be installed.
- **contents_only**: (Optional, directory sources only) When `true`, copies the *contents* of a source directory into the destination rather than the directory itself.

Assets are processed during SPI injection or curation for use within the containerized notebook environment. For example:

```yaml
assets:
  - repo: https://github.com/example/data-store.git
    ref: latest
    items:
      - source: models/
        destination: /opt/app/models/
        contents_only: true
      - source: config/model-config.yaml
        destination: /opt/app/config/model.yaml
```

This example clones the repository, copies all files under `models/` into `/opt/app/models/`, and places a single configuration file at `/opt/app/config/model.yaml`.

### **Package-List Dev Overrides**

In addition to overriding scalar/section values (repositories, data definitions, SPI refs), `dev_overrides` also supports full-replacement overrides for the five top-level package-list fields: `extra_mamba_packages`, `common_mamba_packages`, `extra_pip_packages`, `common_pip_packages`, and `apt_packages`.

When a package list appears under `dev_overrides` **and** `--dev` mode is active, it **replaces** (rather than appends to) the top-level value. An empty override list clears the base list entirely. In `--prod` mode these overrides are ignored and the top-level lists are used as-is.

```yaml
# Production spec: base package set
extra_pip_packages:
  - boto3
common_pip_packages:
  - bqplot>=0.12.47,<0.13

dev_overrides:
  extra_pip_packages:          # replaces top-level list in --dev mode only
    - my-dev-fork-pkg @ git+https://github.com/myorg/boto3.git@feature-branch
  common_pip_packages: []       # clears all common pip packages for dev testing
```

These keys are validated against the spec's keyword allow-list, so unknown keywords inside a `dev_overrides` block (e.g. typos like `extra_mamba_package`) will produce an error during validation.