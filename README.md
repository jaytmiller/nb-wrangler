# nb-wrangler

![nb-wrangler logo](docs/nb-wrangler-logo.png)

## Overview

`nb-wrangler` is a command-line tool that streamlines the curation of JupyterLab notebooks and their runtime environments. It automates the process of building and testing container images from notebook requirements, ensuring that notebooks have the correct dependencies to run successfully.

Key features include:

- **Environment Management:** Bootstraps its own dedicated Conda environments, isolated from your system's Python.
- **Dependency Resolution:** Compiles `requirements.txt` files from multiple notebooks into a single, consistent set of versioned dependencies.
- **Automated Testing:** Tests notebooks and their package imports to verify the environment.
- **Data Management:** Manages the data required to run notebooks.
- **Image Building:** Integrates with a build system to automatically create container images.
- **Local Installs:** Works equally well doing local installs with no Docker overhead or learning curve.

The project uses `micromamba` for environment management and `uv` for fast pip
package installation.

Note that while `nb-wrangler` was conceived as a way to streamline notebook
Docker image creation for JupyterHub, at it's core nb-wrangler is merely defining:

1. A set of notebooks particularly relevant to a science platform.
2. Any supporting data required to run those notebooks.
3. A Python environment capable of running the entire set of notebooks.
4. Tests to help verify the system is built correctly and correctly runs those
   notebooks.
5. Standard methods to locally install the notebooks, data, and Python
   environment and run the tests.

All of the above don't even build Docker images directly,  but nb-wrangler does
provide two ways to hand off the information to STScI's science-platform-images GitHub
repository which can autonomously or manually build an image from a wrangler
spec.

Two other points are worthy of note:

1. nb-wrangler can support easy installation of custom environments directly
   on the science platform that were not first pre-installed in the platform
   Docker image.  This can be exploited to set up shared global or team installations
   areas as well as personalized environments.
2. The network distribution and installation protocols used equally enable
   off-platform laptop users to set up the same environment locally in an easy
   manner.

## Installation

### Locally / On your laptop

To get started, bootstrap `nb-wrangler` to create the necessary environments and directories (by default in `$HOME/.nbw-live`):

```bash
curl https://raw.githubusercontent.com/spacetelescope/nb-wrangler/refs/heads/main/nb-wrangler >nb-wrangler
chmod +x nb-wrangler
./nb-wrangler bootstrap
```

After bootstrapping, you can activate and/or reactivate the `nbwrangler` environment with:

```bash
source ./nb-wrangler environment
```

This command sets up the shell environment and activates the `nbwrangler` Python environment so
that it (temporarily) replaces any other Python you had activated previously and is ready to
start executing wrangler commands.

**NOTE:** Throughout this documentation you'll see `./nb-wrangler` used to run the nb-wrangler
program.  This assumes that (a) nb-wrangler is in your current working directory and (b) nb-wrangler
is executable.  Other alternatives to this approach exist: nb-wrangler may already be installed
in a platform environment and automatically on your PATH.  Or you can put the nb-wrangler script
in a "bin" directory somewhere that is on your PATH.  In those alternate cases,  you can just
`source nb-wrangler ...` and drop the leading `./`.

### On the STScI Science Platform

This is viable but the exact environment settings and required workflows are still being formalized.

If you're curious contact octarine@stsci.edu and we will work out platform and image appropriate
instructions for doing in-situ development of platform environments using nb-wrangler.

## How It Works

The `nb-wrangler` workflow is divided into two main phases: **curation** and **reinstallation**.

### Phase 1: Curation

Curation is the process of defining the notebooks, Python packages, and data
required for a specific environment. This is done by creating a `nbw-spec.yaml`
file that describes the desired environment. Typically notebook repository
maintainers perform these steps in addition their fundamental roles of producing
correct notebooks, pip requirements, and installable data.

The main curation workflows are:

- **`--curate`:** Compiles notebook requirements, creates the mamba environment, and
  installs pip dependencies.
- **`--data-curate`:** Gathers data requirements from notebook repositories and
  adds them to the spec.
- **`--test, --test-imports, --test-notebooks`:** Tests the notebook imports and
  notebooks themselves in the context of the environment and data installation.

Example:
```bash
# Curate the software environment
./nb-wrangler spec.yaml --curate

# Test environment basics rapidly
./nb-wrangler spec.yaml --test-imports

# Curate the data dependencies
./nb-wrangler spec.yaml --data-curate

# Run each notebook headless using papermill
./nb-wrangler spec.yaml --test-notebooks

# Activate your new "target" environment!  Here kernel-name == mamba environment you are curating
source ./nb-wrangler activate <your-kernel-name>

# Deactivate your current environment
source ./nb-wrangler deactivate
```

The curation process involves:
1.  **Choosing notebooks:** Selecting the notebooks to be included in the environment.
2.  **Resolving dependencies:** Identifying and resolving any conflicts between Python packages.
3.  **Defining data sources:** Specifying the data required by the notebooks.
4.  **Testing:** Building the environment and testing the notebooks to ensure they run correctly.

### Phase 2: Reinstallation

Reinstallation is the process of creating a new environment from a completed `spec.yaml` file. This is useful for reproducing an environment on a different machine or for a different user.

The main reinstallation workflows are:

- **`--reinstall`:** Recreates the software environment from a spec.
- **`--data-reinstall`:** Installs the data required by the notebooks.
- **`--test, --test-imports, --test-notebooks`:** Tests the notebook imports and notebooks themselves within the defined environment and data.


Example:
```bash
# Reinstall the software environment
./nb-wrangler spec.yaml --reinstall

# Reinstall the data
./nb-wrangler spec.yaml --data-reinstall

# Run both import and notebook tests
./nb-wrangler spec.yaml --test-all

# Activate your new "target" environment!  Here kernel-name == mamba environment you are curating
source ./nb-wrangler activate <your-kernel-name>

# Deactivate your current environment
source ./nb-wrangler deactivate
```

For both curation and reinstallation there is the assumption that tests may fail and it may be necessary
to circle back to earlier steps, make fixes, and iterate.

For more information on notebooks and environment curation see [Managing Notebook Selection and Environment](docs/notebooks_and_environment.md)
For more information on supporting data see [Managing Notebook Reference Data](docs/data.md)

## Advanced Usage

### Build Submission

After you have curated a spec, you can submit it to a build service to automatically create a container image.

```bash
gh auth login
./nb-wrangler spec.yaml --submit-for-build
```
The `--submit-for-build` command requires a valid `GitHub Personal Access Token (PAT)` with the necessary permissions and collaborator status with the targeted SPI repo.
For more information, see the [Build Submission documentation](docs/submit.md).

### Development Overrides

To streamline development with custom branches without altering your core `spec.yaml`, `nb-wrangler` supports `dev_overrides`.

- The `dev_overrides` section in `spec.yaml` allows you to temporarily specify development branches for repositories.
- Use the `--dev` flag (or rely on implicit activation for curation workflows) to apply these overrides.
- Use `--finalize-dev-overrides` to remove the `dev_overrides` section when preparing for production.

For more details, see the [Spec Format documentation](docs/spec-format.md).

### SPI Injection

`nb-wrangler` can also inject the package and test requirements from a spec into the classic Science Platform Images (SPI) repository layout. This is a transitional feature to support older build processes.

See the [SPI Injection documentation](docs/inject-spi.md) for more details.

## Configuration Options

`nb-wrangler` provides a wide range of command-line options to customize its behavior. Here are some of the most common ones, grouped by function:

### Workflows

Workflows are commands that execute an ordered sequence of steps to accomplish some end-to-end task:

- `--curate`: Run the full curation workflow to define notebooks and Python environment.
- `--reinstall`: Reinstall an environment from a spec.
- `--reset-curation`: Delete installation artifacts like the environment, install caches, and spec updates.
- `--data-curate`: Curate data dependencies.
- `--data-reinstall`: Reinstall data dependencies.
- `--submit-for-build`: Submit a spec for an automated image build.
- `--inject-spi`: Inject a spec into the SPI repository.

### Environment Management
- `--env-init`: Create and kernelize the target environment.
- `--env-delete`: Delete the target environment.
- `--env-pack`: Pack the environment into an archive.
- `--env-unpack`: Unpack an environment from an archive.
- `--env-register`: Register the environment as a Jupyter kernel.
- `--env-unregister`: Unregister the environment from Jupyter.
- `--env-compact`: Compact the wrangler installation by deleting package caches.
- `--env-archive-format`: Override format for environment pack/unpack.
- `--env-print-name`: Print the environment name for the spec.

### Package Management
- `--packages-compile`: Compile package requirements.
- `--packages-install`: Install packages into the environment.
- `--packages-uninstall`: Uninstall packages from the environment.
- `--packages-omit-spi`: Don't include 'common' SPI packages.
- `--packages-diagnostics`: Show which requirements files are included and their required packages.

### Testing
- `-t`, `--test-all`: Run all tests (`--test-imports` and `--test-notebooks`).
- `--test-imports`: Test package imports.
- `--test-notebooks [REGEX]`: Test notebook execution. Can optionally take a comma-separated list of regex patterns to select specific notebooks.
- `--test-notebooks-exclude [REGEX]`: Exclude notebooks from testing using a comma-separated list of regex patterns.
- `--jobs INT`: Number of parallel jobs for notebook testing.
- `--timeout INT`: Timeout in seconds for notebook tests.

### Data Management
- `--data-collect`: Collect data archive and installation info and add to spec.
- `--data-list`: List data archives.
- `--data-download`: Download data archives to the pantry.
- `--data-update`: Update metadata for data archives (e.g., length and hash).
- `--data-validate`: Validate pantry archives against the spec.
- `--data-unpack`: Unpack data archives.
- `--data-pack`: Pack live data directories into archive files.
- `--data-reset-spec`: Clear the 'data' sub-section of the 'out' section of the spec.
- `--data-delete [archived|unpacked|both]`: Delete data archives and/or unpacked files.
- `--data-env-vars-mode [pantry|spec]`: Define where to locate unpacked data.
- `--data-print-exports`: Print shell exports for data environment variables.
- `--data-env-vars-no-auto-add`: Do not automatically add data environment variables to the runtime environment.
- `--data-select [REGEX]`: Regex to select specific data archives.
- `--data-no-validation`: Skip data validation.
- `--data-no-unpack-existing`: Skip unpack if the target directory exists.
- `--data-symlink-install-data`: Create symlinks from install locations to the pantry data directory.

### Notebook Clones
- `--clone-repos`: Clone notebook repositories.
- `--repos-dir`: Directory for cloned repositories.
- `--delete-repos`: Delete cloned repositories.

### Spec Management
- `--spec-reset`: Reset the spec file to its original state (preserves `out.data`).
- `--spec-add`: Add the spec to the pantry (a local collection of specs).
- `--spec-list`: List available specs in the pantry.
- `--spec-select [REGEX]`: Select a spec from the pantry by regex.
- `--spec-validate`: Validate the spec file.
- `--spec-update-hash`: Update spec SHA256 hash.
- `--spec-ignore-hash`: Do not add or verify the spec hash.
- `--spec-add-pip-hashes`: Record PyPI hashes for packages during compilation.

### Miscellaneous
- `--verbose`: Enable DEBUG log output.
- `--debug`: Drop into debugger on exceptions.
- `--profile`: Run with cProfile and print stats.
- `--reset-log`: Delete the log file.
- `--log-times`: Configure timestamps in log messages.
- `--color`: Colorize log output.

For a full list of options, run `./nb-wrangler --help`.


## Input Formats

`nb-wrangler` uses several input formats to define the environment:

- **Notebook (`.ipynb`):** Jupyter notebooks.
- **Wrangler Spec (`spec.yaml`):** The main YAML file that defines the notebook repositories and Python environment. See the [spec format documentation](docs/spec-format.md) for details on the new format, which uses a `repositories` dictionary and named `selected_notebooks` blocks.
- **Notebook Repo:** A Git repository containing Jupyter notebooks.  e.g., [TIKE Content](https://github.com/spacetelescope/tike_content), [Roman Notebooks](https://github.com/spacetelescope/roman_notebooks)
- **Science Platform Images (`SPI`):**  The GitHub repository where code for the docker images for the Science Platforms is kept.  [Science Platform Images](https://github.com/spacetelescope/science-platform-images)
- **Refdata Spec (`refdata_dependencies.yaml`):** A YAML file in a notebook repository that specifies data dependencies. See the [refdata dependencies documentation](docs/refdata_dependencies.md).
- **Requirements (`requirements.txt`):** A file specifying Python package dependencies for a notebook in its directory.
- **Supporting Python (`.py`):** Any supporting Python files (`.py`) included in a notebook's directory.

The goal of nb-wrangler is to combine these inputs, resolve any conflicts, and create a unified environment capable of running all specified notebooks.

Secondary goals,  include but are not limited to:

- Collecting, freezing, distributing, and re-installing **data** associated with notebook repos.
- Initializing notebook and terminal environment variables as spec'ed, partcularly regarding spec'ed/installed data which may be installed in a shared location.
- Building Docker images for curators or science platform admins or pipelines.
- Testiing environments (importing all requested package) and notebooks.
- Automating any/all of these tasks for notebook repos / curators and the science platforms.

