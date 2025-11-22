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

## Science Platform Pre-install

Before installing/bootstrapping on the Science Platform, set the environment variable `NBW_ROOT` to temporary container storage:

```sh
export NBW_ROOT=/tmp/nbw-live
```

This is required for adequate cloud performance when creating Python
environments and should be done at the start of each session. This step 
can be skipped for local installations.

## Installation

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

To activate the environment for a specific notebook or set of notebooks, use:

```bash
source ./nb-wrangler activate <ENVIRONMENT_NAME>
```

To deactivate the current environment, run:

```bash
source ./nb-wrangler deactivate
```

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
- **`--test, --test-imports, --test-notebooks`:** Tests the notebook imports and 
  notebooks themselves in the context of the environment and data installation.


Example:
```bash
# Reinstall the software environment
./nb-wrangler spec.yaml --reinstall

# Reinstall the data
./nb-wrangler spec.yaml --data-reinstall

# Run both import and notebook tests
./nb-wrangler spec.yaml --test-all
```

Note that particularly for curation but also for reinstallation
there is the assumption that tests may fail and it may be necessary
to circle back to earlier steps, make fixes, and iterate.

## Advanced Usage

### Test Failures and Process Iteration

If you encounter errors in the test phase and need to circle back to
earlier steps,  depending on what work needs to be repeated,  you may
need to `--reset-curation` to remove artifacts of earlier runs which
would otherwise short circuit the required repeat work as "already performed".

Environment curation can be reset like this:

```sh
nb-wrangler spec.yaml --reset-curation [--delete-repos]
```

This results in resetting the spec, deleting the environment, clearing package
caches, and any other required cleanup needed before resuming curation of
modified inputs.

Similarly for data curation you can:

```sh
nb-wrangler spec.yaml --data-reset-spec --data-delete both [--delete-repos]
```

### Build Submission

After you have curated a spec, you can submit it to a build service to automatically create a container image.

```bash
gh auth login
./nb-wrangler spec.yaml --submit-for-build
```

For more information, see the [Build Submission documentation](docs/submit.md).

### SPI Injection

`nb-wrangler` can also inject the package and test requirements from a spec into the classic Science Platform Images (SPI) repository layout. This is a transitional feature to support older build processes.

See the [SPI Injection documentation](docs/inject-spi.md) for more details.

## Configuration Options

`nb-wrangler` provides a wide range of command-line options to customize its behavior. Here are some of the most common ones, grouped by function:

### Workflows

Workflows are commands that execute an ordered sequence of steps to accomplish some end-to-end task:

- `--curate`: Run the full curation workflow to define notebooks and Python environment.
- `--reinstall`: Reinstall an environment from a spec.
- `--reset-curation`: Delete installation artifacts like the environment, install caches, and spec updates. Sometimes needed to iterate --curate, particularly after revising notebook repos.
- `--data-curate`: Curate data dependencies.
- `--data-reinstall`: Reinstall data dependencies.
- `--submit-for-build`: Submit a spec for an automated image build.
- `--inject-spi`: Inject a spec into the SPI repository.

### Testing
- `-t`, `--test-all`: Run all tests.
- `--test-imports`: Test package imports.
- `--test-notebooks`: Test notebook execution.
- `--jobs`: Number of parallel jobs for notebook testing.
- `--timeout`: Timeout for notebook tests.

### Environment Management
- `--env-init`: Create and kernelize the target environment.
- `--env-delete`: Delete the target environment.
- `--env-pack`: Pack the environment into an archive.
- `--env-unpack`: Unpack an environment from an archive.
- `--env-register`: Register the environment as a Jupyter kernel.
- `--env-unregister`: Unregister the environment from Jupyter.

### Package Management
- `--packages-compile`: Compile package requirements.
- `--packages-install`: Install packages into the environment.
- `--packages-uninstall`: Uninstall packages from the environment.

### Repository Management
- `--clone-repos`: Clone notebook repositories.
- `--repos-dir`: Directory for cloned repositories.
- `--delete-repos`: Delete cloned repositories.

### Spec Management
- `--spec-reset`: Reset the spec file to its original state.
- `--spec-add`: Add the spec to the pantry (a local collection of specs).
- `--spec-list`: List available specs in the pantry.
- `--spec-select`: Select a spec from the pantry.

For a full list of options, run `./nb-wrangler --help`.


## Input Formats

`nb-wrangler` uses several input formats to define the environment:

- **Wrangler Spec (`spec.yaml`):** The main YAML file that defines the notebook repositories and Python environment. See the [spec format documentation](docs/spec-format.md).
- **Notebook Repo:** A Git repository containing Jupyter notebooks.  e.g. [TIKE Content](https://github.com/spacetelescope/tike_content) or [Roman Notebooks](https://github.com/spacetelescope/roman_notebooks) 
- **Science Platform Images (`SPI`):**  The GitHub repository where code for the docker images for the Science Platforms is kept.  [Science Platform Images](https://github.com/spacetelescope/science-platform-images)
- **Refdata Spec (`refdata_dependencies.yaml`):** A YAML file in a notebook repository that specifies data dependencies. See the [refdata dependencies documentation](docs/refdata_dependencies.md).
- **Notebook (`.ipynb`):** Jupyter notebooks.
- **Requirements (`requirements.txt`):** A file specifying Python package dependencies for a notebook in it's notebook directory.
- **Supporting Python (`.py`):** Any supporting Python files (`.py`) included in a notebook's directory to factor out lengthy custom code from the notebook.

The goal of "wrangling" is to combine these inputs, resolve any conflicts, and produce a single, unified environment that can run all the specified notebooks.

## Future Development

- More comprehensive documentation for configuration options.
- Improved error handling and user feedback.
- Advanced use cases and integrations.

