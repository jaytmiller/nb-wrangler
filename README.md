# nb-wrangler

![nb-wrangler logo](docs/nb-wrangler-logo.png)

## Overview

nb-wrangler streamlines the process of curating JupyterLab notebooks, their runtime environments, and ultimately supports
automatically building and testing Docker images based on notebook requirements. It achieves this by:

- Bootstrapping a dedicated environment for nb-wrangler.
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

nb-wrangler aims to install 2-3 dedicated environments under `$HOME/.nbw-live`:

- **micromamba:** A self-contained installation tool, not a base environment.
- **nbwrangler:** A full micromamba environment containing nb-wrangler and its dependencies.
- **spec defined environment:** The notebook environment being curated.

These environments are independent of your existing Python environments and can be easily registered as notebook kernels in JupyterHub.

The location of nb-wrangler files can be changed by setting the `NBW_ROOT` environment variable. This is useful for team environments or relocating to faster storage.

## Installing

Bootstrapping the system creates the `$HOME/.nbw-live` directory and the nbwrangler environment under `$HOME`.

```bash
curl https://raw.githubusercontent.com/spacetelescope/nb-wrangler/refs/heads/main/nb-wrangler >nb-wrangler
chmod +x nb-wrangler
source ./nb-wrangler bootstrap
```

Afterward, the nbwrangler "curation" environment can be re-activated using:

```bash
source ./nb-wrangler environment
```

Consider adding the nb-wrangler bash script to your shell's PATH or RC file.

The target environment can be activated with:

```bash
source ./nb-wrangler activate ENVIRONMENT_NAME
```

Deactivate either nbwrangler or the target environment with:

```bash
source ./nb-wrangler deactivate
```

## Overall nb-wrangler usage

Overall usage of nb-wrangler entails two broad areas,  setting up notebooks and environments,  and setting
up supporting data.  Whether working on environments or data,  there are two phases for each area:
developing the wrangler spec (a process called curation),  and reinstalling systems based on the
wrangler spec.  To that end, the wrangler has 4 key workflows which are detailed more below but can
be invoked basically as follows:

```bash
# Phase 1  - curator work
./nb-wrangler spec.yaml  --curate
./nb-wrangler spec.yaml  --data-curate

# Phase 2  - user and/or system admin work
./nb-wrangler spec.yaml  --reinstall
./nb-wrangler spec.yaml  --data-reinstall
```

Note that each workflow consists of multiple interdependent steps executed in the correct sequence,
but individual steps are available for iteration as practical depending on the necessary prerequisite
steps having already been executed.  To save time the wrangler uses a basic approach to avoid repeating
previously accomplished work,  but in the presence of errors it may be necessary to delete part or all
of the existing installation before recovering.

## Curation

You the wrangler prepares a custom version of the `spec.yaml` file. Then, run:

```bash
nb-wrangler spec.yaml --curate [--verbose]
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/fnc-test-spec.yaml
INFO: 00:00:00.005 Running workflows ['curation'].
INFO: 00:00:00.000 Running spec development / curation workflow
INFO: 00:00:00.000 Setting up repository clones.
INFO: 00:00:00.000 Using existing local clone at references/science-platform-images
INFO: 00:00:00.000 Using existing local clone at references/mast_notebooks
INFO: 00:00:00.000 Using existing local clone at references/tike_content
INFO: 00:00:00.003 Found 8 notebooks in all notebook repositories.
INFO: 00:00:00.000 Processing 8 unique notebooks for imports.
INFO: 00:00:00.001 Extracted 7 package imports from 8 notebooks.
INFO: 00:00:00.000 Revising spec file /home/ai/nb-wrangler/fnc-test-spec.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/temps/fnc-test-spec.yaml.
INFO: 00:00:00.011 Generating mamba spec for target environment /home/ai/.nbw-live/temps/tike-2025.07-beta-tess-mamba.yml.
INFO: 00:00:00.000 Found SPI extra 1 mamba requirements files.
INFO: 00:00:00.001 Revising spec file /home/ai/nb-wrangler/fnc-test-spec.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/temps/fnc-test-spec.yaml.
INFO: 00:00:00.012 Found 8 notebook requirements.txt files.
INFO: 00:00:00.000 Found SPI extra 5 pip requirements files.
INFO: 00:00:00.000 w/o hashes.
INFO: 00:00:00.507 Compiled combined pip requirements to 352 package versions.
INFO: 00:00:00.000 Revising spec file /home/ai/nb-wrangler/fnc-test-spec.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/temps/fnc-test-spec.yaml.
INFO: 00:00:00.053 Creating environment: tess
INFO: 00:00:12.721 Environment tess created. It needs to be registered before JupyterLab will display it as an option.
INFO: 00:00:00.356 Registered environment tess as a jupyter kernel making it visible to JupyterLab as 'TESS'.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/mm/envs/tess/fnc-test-spec.yaml.
INFO: 00:00:00.045 Installing packages from: ['/home/ai/.nbw-live/temps/tike-2025.07-beta-tess-pip.txt']
INFO: 00:00:06.219 Package installation for tess completed successfully.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/mm/envs/tess/fnc-test-spec.yaml.
INFO: 00:00:00.045 Saving spec file to /home/ai/nb-wrangler/fnc-test-spec.yaml.
INFO: 00:00:00.050 Workflow spec development / curation completed.
INFO: 00:00:00.000 Running any explicitly selected steps.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:20
```

This phases identifies the exact notebooks to be included by the spec,  as well as the s/w packages
required to support those notebooks.  This information is added to the spec in exact detail to enable
high fidelity reproduction of the s/w environment and exact package versions for future installs.

## Automatic Testing

For both curation and reinstallation work flows it's useful to execute tests to demonstrate that the installation is
working correctly with the specified notebooks.  To that end,  nb-wrangler has additional switches which can be added
with the following effects:

- `--test-imports`  directs nb-wrangler to import the packages found imported by the notebooks. Fast, if the import succeeds the test passes.

- `--test-notebooks`  directs nb-wrangler to execute the specified notebooks headless. If the notebook raises an exception the test fails.

- `-t` directs nb-wrangler to run both `--test-imports` and `--test-notebooks`.

For example, you can iterate fairly rapidly with:

```bash
nb-wrangler spec.yaml --curate --test-imports
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/fnc-test-spec.yaml
INFO: 00:00:00.027 Running any explicitly selected steps.
INFO: 00:00:00.000 Running step _test_imports
INFO: 00:00:00.000 Testing 7 imports
INFO: 00:00:00.309 Import of astropy succeeded.
INFO: 00:00:00.188 Import of astroquery succeeded.
INFO: 00:00:08.436 Import of lcviz succeeded.
INFO: 00:00:01.641 Import of lightkurve succeeded.
INFO: 00:00:00.212 Import of matplotlib succeeded.
INFO: 00:00:00.119 Import of numpy succeeded.
INFO: 00:00:00.629 Import of s3fs succeeded.
INFO: 00:00:00.000 All imports succeeded.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:11
```

to verify that the notebook dependencies have been accounted for on some level, then switch to `--test-notebooks` 
for more meaningful checks and verification that empirically viable package versions are installed.

Note that successfully running notebooks may require correctly setting up local copies of data
which are nominally defined in the file `refdata_dependencies.yaml` at the root of each notebook
repository that requires it.  The wrangler automation for this is currently being developed,
check for it using `--help` but don't be surprised if you must do data setup manually for now.

## Reinstall

A finished spec can be used to re-install corresponding Python environments in any nb-wrangler installation as follows:

```bash
nb-wrangler spec.yaml --reinstall
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/fnc-test-spec.yaml
INFO: 00:00:00.024 Running workflows ['reinstall'].
INFO: 00:00:00.000 Running install-compiled-spec workflow
INFO: 00:00:00.032 Creating environment: tess
INFO: 00:00:06.159 Environment tess created. It needs to be registered before JupyterLab will display it as an option.
INFO: 00:00:00.369 Registered environment tess as a jupyter kernel making it visible to JupyterLab as 'TESS'.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/mm/envs/tess/fnc-test-spec.yaml.
INFO: 00:00:00.045 Installing packages from: ['/home/ai/.nbw-live/temps/tike-2025.07-beta-tess-pip.txt']
INFO: 00:00:01.766 Package installation for tess completed successfully.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/mm/envs/tess/fnc-test-spec.yaml.
INFO: 00:00:00.046 Workflow install-compiled-spec completed.
INFO: 00:00:00.000 Running any explicitly selected steps.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:08
```

## Data Wrangling

Part of nb-wrangler's functionality is associated with managing the data required to test/run the spec'ed notebooks.

Like the creation of the basic s/w environment, data wrangler has two main phases:

### Data Curation

This is the process of updating the wrangler spec based on per-repository `refdata_dependencies.yaml` files which
define data requirements much as `requirements.txt` files define per-notebook package requirements.  This phase
will likely revolved around setting up the data archives,  setting up repo `refdata_dependencies.yaml` files, and
running the wrangler to import the information into the wrangler spec and augment it as needed:

```bash
./nb-wrangler sample-specs/roman-20.yaml --data-curate
```

### Data Reinstallation

Once data archives have been fully set up, notebook repos configured, and the wrangler spec updated based
on `refdata_dependencies.yaml` files, future users and system admins can install the spec'd data archives
and set up wrangler notebook environments using:

```bash
./nb-wrangler sample-specs/roman-20.yaml --data-reinstall
```

### More Data Curation Details

See [Data Curation](docs/data.md) for more information on wrangling data.

## Build Submission

After completing development of a spec, you can submit it to https://github.com/spacetelescope/science-platform-images
to automatically build a Docker image which becomes available for use on the relevant STScI science platforms.

```bash
gh auth login
nb-wrangler spec.yaml --submit-for-build [--verbose]
```

Build submission is a complex topic with some per-curator setup required to enable creating images.
For additional detail see [Submit for Build](docs/submit.md).


## Science Platform Images (SPI) Injection

Out of conservatism nb-wrangler supports a build mode called `SPI Injection` which essentially
injects the package and test requirements defined by a wrangler spec into the classic
science platform images repo layout we've been using for years. This leverages the wrangler
spec by completing the formerly manual developer task of copying package specs from Jira
to a mission environment's definition directories.  From that point forward however there is
no additional wrangler automation for this mode.  The build, scan, tagging, push, and PR'ing
all need to be completed manually. Nevertheless, while we're in the process of introducing
nb-wrangler,  SPI Injection may be handy if we're required to build two versions of the images,
wrangler and classic.  See [SPI Injection](docs/inject-spi.md) for more information on this
fallback / transition mode of builds.

## Basic Flow

The wrangler executes steps in a sequence, allowing for skipping steps that have already completed. This enables iteration without repeatedly recompiling and reinstalling packages. If any step fails, the process exits with an error. Most features are controlled by command-line options.

- **Spec Management:** Loads, validates, updates, and saves the YAML notebook specification. Validation is currently incomplete but checks for required keywords.
- **Repository Management:** Optionally clones Git repositories for notebooks if a local clone doesn't exist; otherwise, it updates existing clones. `--repos-dir` specifies the directory for cloning, defaulting to a `notebook-repos` subdirectory of the current directory.
- **Notebook Discovery:** Searches for notebooks based on directory paths and include/exclude patterns.
- **Requirements Gathering:** Locates `requirements.txt` files within notebooks to specify Python package version constraints.
- **Environment Creation:** Automatically creates a basic Python environment for package installation and testing.
- **Target Environment Initialization:** Optionally initializes a target environment to facilitate requirement compilation, package installation, and testing. This includes creating a JupyterLab kernel required for notebook testing or use in JupyterLab.
- **Package Compilation:** If `--compile-packages` is specified, creates both a conda environment `.yml` file and a locked pip `requirements.txt` file by compiling all discovered notebook requirements. If `--compile-packages` is not specified, it uses the last compiled package set from the specification.
- **Package Installation:** If `--packages-install` is specified, installs the compiled packages in the conda environment. After installation, it attempts to import packages listed in notebook files for basic sanity checks.
- **Data Curation:** Gathering requirements for data needed to support the spec'ed notebook repos.
- **Data Re-installation:** Downloading and installing the data defined by the wrangler spec, and updating the JupyterLab environment with the requred environment variables to refer to it.
- **Notebook Testing:** If `--test-notebooks` is specified, runs notebooks matching a comma-separated list of names or regular expressions. If no notebooks or regexps are provided, it runs all notebooks. This is a headless crash test that runs up to `--jobs [n]` notebooks in parallel, with a `--timeout [seconds]` to terminate runaway notebooks.
- **Repository Cleanup:** If `--delete-repos` is specified, removes all cloned repositories.
- **Spec Reset:** If `--spec-reset` is specified, removes the output section from the `spec.yaml` file.
- **Environment Deletion:** If `--env-delete` is specified, removes the entire target environment. This dedicated environment approach prevents contamination between iterations.
- **CI Submission:** If `--submit-for-build` is specified, the specification is forwarded to the CI pipeline, key information is provided to the build framework, and a corresponding image is automatically built and pushed to the hub (pending further development).
- **Output Injection:** If `--inject-spi` is specified, extracts key output information (e.g., mamba and pip requirements, import tests, supported notebooks) from the specification and injects it into a clone of the science platform images build, enabling manual builds.

## Configuration Options

The following command-line options are available:

- `--curate`: Execute the curation workflow for spec development to add compiled requirements.
- `--submit-for-build`: Submit fully elaborated requirements for image building.
- `--reinstall`: Install requirements defined by a pre-compiled spec.
- `-t`, `--test`: Test both imports and all notebooks.
- `--test-imports`: Attempt to import every package explicitly imported by one of the spec'd notebooks.
- `--test-notebooks`: Test spec'ed notebooks matching patterns (comma-separated regexes) in target environment. Default regex: .*
- `--verbose`: Enable DEBUG log output
- `--debug`: Drop into debugging with pdb on exceptions.
- `--profile`: Run with cProfile and output profiling results to console.
- `--log-times`: Include timestamps in log messages, either as absolute/normal or elapsed times, both, or none.
- `--color`: Colorize the log.
- `--env-init`: Create and kernelize the target environment before curation run. See also --env-delete.
- `--env-delete`: Completely delete the target environment after processing.
- `--env-pack`: Pack the target environment into an archive file for distribution or archival.
- `--env-unpack`: Unpack a previously packed archive file into the target environment directory.
- `--env-register`: Register the target environment with Jupyter as a kernel.
- `--env-unregister`: Unregister the target environment from Jupyter.
- `--env-archive-format`: Format for pack/unpack, nominally one of: .tar.gz, .tar.xz, .tar, .tar.bz2, .tar.zst, .tar.lzma, .tar.lzo, .tar.lz
- `--env-compact`: Compact the wrangler installation by deleting package caches, etc.
- `--packages-compile`: Compile spec and input package lists to generate pinned requirements and other metadata for target environment.
- `--packages-omit-spi`: Include the 'common' packages used by all missions in all current SPI based and mission environments, may affect GUI capabilty.
- `--packages-install`: Install compiled base and pip requirements into target/test environment.
- `--packages-uninstall`: Remove the compiled packages from the target environment after processing.
- `--jobs`: Number of parallel jobs for notebook testing.
- `--timeout`: Timeout in seconds for notebook tests.
- `--inject-spi`: Inject curation products into the Science Platform Images repo clone at the specified existing 'deployment'.
- `--clone-repos`: Clone notebook repos to the directory indicated by --repos-dir.
- `--repos-dir`: Directory where notebook and other repos will be cloned.
- `--delete-repos`: Delete --repo-dir and clones after processing.
- `--spec-reset`: Reset spec to its original state by deleting output fields.
- `--spec-validate`: Validate the specification file without performing any curation actions.
- `--spec-ignore-hash`: Spec SHA256 hashes will not be added or verified upon re-installation.
- `--spec-add-pip-hashes`: Record PyPi hashes of requested packages for easier verification during later installs.

## Missing Topics

- **Detailed explanation of `spec.yaml` structure:** While mentioned, a more detailed breakdown of the YAML file's sections and their purpose would be beneficial.
- **Configuration options:** A more comprehensive list of available configuration options and their effects.
- **Error handling:** More information on how the tool handles various errors and provides feedback to the user.
- **Advanced usage:** Potential use cases beyond basic curation, such as automated testing workflows or integration with other tools.
```
