# Defining Environments

There are multiple methods of defining the Python environment.   Collectively they use a combination of
inputs from the spec and network resources.

Key variations of environment definition include:

1. Basic python environment with implied mamba baseline

2. Basic python environment with mamba and pip additions

3. Advanced environment with full mamba spec inlined + additions

4. Advanced environment with full mamba spec referenced as separate URI + additions

## Overall Approach

nb-wrangler mimics the approach taken by STSCI's notebook repositories in general, and to that end it
tends to minimize the mamba environment and emphasize usage of pip packages wherever possible.

One of the fundamental tasks of the wrangler is to combine dependencies coming from a variety of
sources into both base and mission environments for a two environment science platform image.
The mission environment is fully locked,  the base environment locking is a longterm goal 
unrealized at this time.  The baseline image structure is now fully generic and uses the wrangler
deployment of science-platform-images repo as we work towards retiring science-platform-images.

Our original bias for which packages to install with mamba can be summed up as:  (1) Python itself 
(2) Python build tools (3) non-Python libraries and tools (4) uv/pip packages includeing the wrangler
and dependencies.

## Base Environment Paradigms

`nb-wrangler` provides multiple methods for defining the base software environment. These are broadly
divided into a **Simple Definition** for `pip`-centric projects and **Advanced Definitions** for
projects requiring precise control over the Mamba environment.

### Method 1: Simple Definition (Implied Spec)

This is the standard and most straightforward method. You specify a `python_version` and a `kernel_name` 
in the spec's header. `nb-wrangler` uses this to create a minimal Mamba environment containing Python and
other core packages like `uv` and `pip`.

**Example:**

```yaml
image_spec_header:
  kernel_name: my-simple-env
  display_name: "My Simple Environment"
  python_version: "3.11"
# ... rest of spec
# MUST NOT specify top-level `environment_spec` or have a second YAML document.
```

### Advanced Definitions

For more complex environments, you can provide a complete Mamba environment specification using one of 
the following mutually exclusive methods. In all advanced methods, `python_version` and `kernel_name` 
must be omitted from the wrangler spec header.

#### Method 2: Inline Spec (via Concatenated File)

Your spec file can contain two separate YAML documents, separated by `---`. This is useful for quickly
embedding an existing `environment.yml` file directly into your wrangler spec without needing to fix
indentation.  Essentially `combined_wrangler_spec = basic_wrangler_spec YAML + '---' + mamba_spec YAML`.

**Rules:**

1. The `nb-wrangler` spec (the first document) **must not** contain `python_version` or `kernel_name`. 
It may optionally provide a `display_name`.

2. The Mamba spec (the second document) **must** contain a `name` field. This will be used as the 
environment's kernel name.

**Example `my-spec.yaml`:**

```yaml
image_spec_header:
  image_name: "My Inlined Env"
  description: "An environment defined by an inline Mamba spec."
  display_name: "My Inline Environment"  # Optional, defaults to the mamba name
# ... other wrangler spec fields ...
---
name: my-inline-env
channels:
  - conda-forge
dependencies:
  - python=3.10
  - numpy
  - pip:
    - rich
```

##### Method 3 & 4: External Spec (via `environment_spec` field)

This approach uses the `environment_spec` field to point to an externally defined Mamba environment file.
This is the most powerful method for reusing shared, version-controlled environments.

**Rules:**

1. The `nb-wrangler` spec **must not** contain `python_version` or `kernel_name`. It may optionally provide a `display_name`.

2. The Mamba spec referenced externally **must** contain a `name` field.

**A - By URI (URL or Local File)**

You can point to a network URI or a local file path.

**Example:**

```yaml
image_spec_header:
  display_name: "My External Environment"
# ...
environment_spec:
  uri: https://raw.githubusercontent.com/my-org/my-repo/main/environment.yml
```

You can also use a local file path, which is resolved relative to the location of the wrangler spec file.

> **Warning:** Using a local file path (`uri: ../my-env.yml`) is convenient for development but makes your
 spec non-portable. For any spec that will be shared or version-controlled, using a **URL** or 
 **Repository Path** is the recommended best practice.

**B - By Repository Path**

You can point to a file within a git repository that is already listed in the top-level `repositories` block of your spec.

**Example:**

```yaml
repositories:
  my-notebook-repo:
    url: https://github.com/my-org/my-notebooks.git
    ref: main
# ...
image_spec_header:
  display_name: "My Repo Environment"
# ...
environment_spec:
  repo: my-notebook-repo
  path: environment.yml
```

### Notebook Repo Requirements.txt

Each notebook directory is permitted to define it's own  `requirements.txt`
file to define pip dependencies which will nominally be resolved and downloaded in aggregate (all notebook
requirements combined) by `uv pip install`. As-of this writing `uv pip install` results in much improved 
version resolution and download times, as well as high quality version resolution feedback which is critical
for resolving difficult package conflicts which result from combining requirements sources.

### Inlined extra_mamba_packages

It is possible to add a list of extra mamba packages directly to the wrangler spec as `extra_mamba_packages`
and these will be added to the environment by mamba in addition to those specified in the base mamba spec.

### Inlined common_mamba_packages

Likewise, `common_mamba_packages` allows you to specify mamba packages that should be installed in both your
curated environment and the science platform's base environment (when using SPI injection).

### Inlined extra_pip_packages

Likewise it is possible to inline extra pip packages by adding `extra_pip_packages` to the wrangler spec and
these will nominally be added by `uv pip` in addition to those specified by the base mamba spec and/or
requirements.txt files.

### Inlined common_pip_packages

Similarly, `common_pip_packages` specifies pip packages that should be installed in both your curated environment
and the science platform's base environment.

### Inlined apt_packages

You can also specify system-level packages to be installed via `apt-get` by adding `apt_packages` to the wrangler
spec. These packages will be collected into `apt-packages.txt` during the SPI injection process (`--inject-spi`) and
installed during the subsequent image build.

### Inlined dockerfile_aux_sh

You can specify a block of text to be written to `environments/dockerfile-aux.sh` by adding `dockerfile_aux_sh` to
the wrangler spec. This content is written as-is and is typically used for custom bash commands during the SPI
injection process (`--inject-spi`).

### Notebook Repo Helper Modules

Lastly,  it's possible for each notebook directory to define local `.py` helper modules directly although
this is not particularly recommended.  By convention,  a top level `shared` directory can also be used to 
store globally available helper modules,  but with the expectation that any notebook importing them will
symlink from the notebook directory (where it is expected to run) to the globally shared file.

### SPI (science-platform-images) Packages

As a final note,  the science platforms impose common requirements in the form of mamba and pip packages which
are collected from selected directories on https://github.com/spacetelescope/science-platform-images.
These help support the standard lab environment and platform extensions,  and while it is possible to opt out
using --packages-omit-spi (both mamba and pip are ommitted), this will most likely result in divergence from
standard science platform behavior and/or

## Notebook and Environment Reinstallation

At some later time and/or different location you can re-install a wrangler spec which was developed
using `--curate` as follows:

```sh
nbw fnc-test-spec.yaml --reinstall
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/fnc-test-spec.yaml
INFO: 00:00:00.038 Running workflows ['reinstall'].
INFO: 00:00:00.000 Running install-compiled-spec workflow
INFO: 00:00:00.000 Running step _validate_spec.
INFO: 00:00:00.029 Running step _spec_add.
INFO: 00:00:00.000 Running step _initialize_environment.
INFO: 00:00:00.010 Creating environment: tess
INFO: 00:00:07.306 Environment tess created. It needs to be registered before JupyterLab will display it as an option.
INFO: 00:00:00.412 Registered environment tess as a jupyter kernel making it visible to JupyterLab as 'TESS'.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/mm/envs/tess/fnc-test-spec.yaml.
INFO: 00:00:00.065 Running step _install_packages.
INFO: 00:00:00.000 Installing packages from: ['/home/ai/.nbw-live/temps/tike-2025.07-beta-tess-pip.txt']
INFO: 00:00:02.211 Package installation for tess completed successfully.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/mm/envs/tess/fnc-test-spec.yaml.
INFO: 00:00:00.054 Workflow install-compiled-spec completed.
INFO: 00:00:00.000 Running any explicitly selected steps.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:10
```

As above with `--curate`  after `--reinstall` you should execute `--test-imports` to make sure the environment and
notebooks are working correctly.  Note that sometimes notebooks require data to run successfully so you may also 
need to `--data-reinstall` before you can successfully `--test-notebooks`.

## Other Curation Tips and Tricks

### Setting key nb-wrangler environment variables

During development,  your best chances of using nb-wrangler successfully are to create a fully
independent wrangler environment whereever you want to work,  it could be your laptop:

#### Laptop Env settings

```sh
# no changes needed,  nb-wrangler installs under $HOME in hidden .nbw-live and .nbw-pantry
# directories
```

#### Science Platform Env Settings

Another (potentially better) option could be on a science platform in an OPS or TEST environment
working solo from your personal $HOME directory:

```sh
export NBW_ROOT="/tmp/nbw-live"
export NBW_PANTRY="$HOME/.nbw-pantry"
```

**TIP:** Add env vars to .bashrc and .bash_profile to make sure they are always added to any new shells.

Note that the entire distinction between ROOT and PANTRY has to do with the underlying
performance and persistence of the associated storage.  The above setup is intended so
that NBW_ROOT is fast but not persistent, while NBW_PANTRY is persistent and unfortunately
slow as a consequence.  (Persistence refers to "not forgotten between notebook sessions
on the science platform."  Nevertheless, maye require unpacking to restore )

### Wrangling with custom tools

If you prefer not to use **micromamba** for setting up the base environment and **uv pip** for `pip` installs,
you can override these tools and fall back to the standard `mamba` and `pip`, which are sufficiently compatible
for the limited wrangler use‑cases.

To configure **nb‑wrangler** to use `mamba` and `pip` instead of `micromamba` and `uv pip`, set the following
environment variables:

```sh
export NBW_MAMBA_CMD="mamba"
export NBW_PIP_CMD="pip"
```

*While untested, swapping either tool independently should also work.*

The configuration above has been used in production at STScI to install **nb-wrangler** into an existing `mamba`
environment and to rely solely on `pip` as the package manager—avoiding a mixed setup of `pip` + `uv pip` (which
is anecdotally discouraged) and a mix of `micromamba` + `mamba`.  Stick to one toolchain or the other,  and this
really applies to default development IF you choose to start installing packages manually vs. using nb-wrangler.

That said, **micromamba** and **uv pip** are the default choices for wrangler development. They provide major
benefits in terms of speed for dependency‑constraint resolution and package installation, making local development
a much more pleasant experience.

### Bootstrapping

After setting env vars as above, See [README.md](../README.md) for instructions on bootstrapping
the nb-wrangler software. This will install a micromamba and an nbwrangler environment in a standalone
configuration isolated from any other Python environments you may have.

### Failures and Process Iteration

If you encounter errors in the test phase and need to circle back to
earlier steps,  depending on what work needs to be repeated,  you may
need to `--reset-curation` to remove artifacts of earlier runs which
would otherwise short circuit the required repeat work as "already performed".

Environment curation can be reset like this:

```sh
nbw spec.yaml --reset-curation [--delete-repos]
```

This results in resetting the spec, deleting the environment, clearing package
caches, and any other required cleanup needed before resuming curation of
modified inputs.  Removing the repos is optional but the simplest way to
get a robust update of upstream changes.

### Environment Cleanup

The `--env-kernel-cleanup` flag scans the user's Jupyter kernel registry for "dead" kernels—those pointing to
non-existent environments—and removes them. This helps maintain a clean and functional Jupyter environment.

```sh
nbw my-spec.yaml --env-kernel-cleanup
```
