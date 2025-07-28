# nb-curator

DRAFT DRAFT DRAFT  -- subject to weekly/daily change top to bottom

## Overview
nb-curator streamlines the process of curating JupyterLab notebooks, their runtime environments, and ultimately supports automatically building and testing Docker images based on notebook requirements. It achieves this by:

- Bootstrapping a dedicated environment for nb-curator.
- Loading, saving, and validating notebook curation specifications.
- Cloning associated notebook and image build repositories.
- Creating a dedicated environment to manage notebook package dependencies.
- Compiling loose `requirements.txt` files into versioned dependencies for the target environment.
- Installing notebook dependencies in the target environment.
- Explicitly testing all top-level notebook imports in the installed environment.
- Running notebooks headless within the target environment.
- Injecting relevant package, test, and notebook output into an external notebook image build system.
- Submitting completed specifications and/or related image build pull requests to trigger automatic builds.
- Performing various cleanup tasks, such as removing clones, packages, and environments.

The project utilizes foundational tools:

- **micromamba:** A lightweight, self-contained version of mamba (a free, open-source alternative to conda).
- **uv:** A new, fast pip-like package installer written in Rust.

nb-curator aims to install 2-3 dedicated environments under `$HOME/.nbc-live`:

- **micromamba:** A self-contained installation tool, not a base environment.
- **nbcurator:** A full micromamba environment containing nb-curator and its dependencies.
- **spec defined environment:** The notebook environment being curated.

These environments are independent of your existing Python environments and can be easily registered as notebook kernels in JupyterHub.

The location of nb-curator files can be changed by setting the `NBC_ROOT` environment variable. This is useful for team environments or relocating to faster storage.

## Installing

Bootstrapping the system creates the `$HOME/.nbc-live` directory and the nbcurator environment under `$HOME`.

```bash
curl https://raw.githubusercontent.com/spacetelescope/nb-curator/refs/heads/main/nb-curator >nb-curator
chmod +x nb-curator
./nb-curator bootstrap
source ./nb-curator environment
```

Afterward, the nbcurator "curation" environment can be re-activated using:

```bash
source ./nb-curator environment
```

Consider adding the nb-curator bash script to your shell's PATH or RC file.

The target environment can be activated with:

```bash
source nb-curator activate ENVIRONMENT_NAME
```

Deactivate either nbcurator or the target environment with:

```bash
source nb-curator deactivate
```

## Curation

The curator prepares a custom version of the `spec.yaml` file. Then, run:

```bash
nb-curator spec.yaml --curate [--verbose]
```

## Basic Flow

The curator executes steps in a sequence, allowing for skipping steps that have already completed. This enables iteration without repeatedly recompiling and reinstalling packages. If any step fails, the process exits with an error. Most features are controlled by command-line options.

- **Spec Management:** Loads, validates, updates, and saves the YAML notebook specification. Validation is currently incomplete but checks for required keywords.
- **Repository Management:** Optionally clones Git repositories for notebooks if a local clone doesn't exist; otherwise, it updates existing clones. `--repos-dir` specifies the directory for cloning, defaulting to a `notebook-repos` subdirectory of the current directory.
- **Notebook Discovery:** Searches for notebooks based on directory paths and include/exclude patterns.
- **Requirements Gathering:** Locates `requirements.txt` files within notebooks to specify Python package version constraints.
- **Environment Creation:** Automatically creates a basic Python environment for package installation and testing.
- **Target Environment Initialization:** Optionally initializes a target environment to facilitate requirement compilation, package installation, and testing. This includes creating a JupyterLab kernel required for notebook testing or use in JupyterLab.
- **Package Compilation:** If `--compile` is specified, creates both a conda environment `.yml` file and a locked pip `requirements.txt` file by compiling all discovered notebook requirements. If `--compile` is not specified, it uses the last compiled package set from the specification.
- **Package Installation:** If `--install` is specified, installs the compiled packages in the conda environment. After installation, it attempts to import packages listed in notebook files for basic sanity checks.
- **Notebook Testing:** If `--test-notebooks` is specified, runs notebooks matching a comma-separated list of names or regular expressions. If no notebooks or regexps are provided, it runs all notebooks. This is a headless crash test that runs up to `--jobs [n]` notebooks in parallel, with a `--timeout [seconds]` to terminate runaway notebooks.
- **Repository Cleanup:** If `--delete-clones` is specified, removes all cloned repositories.
- **Spec Reset:** If `--reset-spec` is specified, removes the output section from the `spec.yaml` file.
- **Environment Deletion:** If `--delete-env` is specified, removes the entire target environment. This dedicated environment approach prevents contamination between iterations.
- **CI Submission:** If `--submit-for-build` is specified, the specification is forwarded to the CI pipeline, key information is provided to the build framework, and a corresponding image is automatically built and pushed to the hub (pending further development).
- **Output Injection:** If `--spi-inject` is specified, extracts key output information (e.g., mamba and pip requirements, import tests, supported notebooks) from the specification and injects it into a clone of the science platform images build, enabling manual builds.

## Missing Topics

- **Detailed explanation of `spec.yaml` structure:** While mentioned, a more detailed breakdown of the YAML file's sections and their purpose would be beneficial.
- **Configuration options:** A more comprehensive list of available configuration options and their effects.
- **Error handling:** More information on how the tool handles various errors and provides feedback to the user.
- **Advanced usage:** Potential use cases beyond basic curation, such as automated testing workflows or integration with other tools.