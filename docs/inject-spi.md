# Science Platform Images (SPI) Injection

> **Note:** SPI Injection is an advanced topic related to building Docker images that contain a wrangler defined environment.
            It is relevant to both GitHub Actions that build science platform images,  and for local Docker builds to use for
            various kinds of standard or ad hoc testing.  If all you need is to run the GitHub Curate or Reinstall actions,
            this section may not be useful to you.  If you're doing wrangler or SPI framework or hardcore spec development,
            you may find it more convenient to work locally than to run GitHub workflows that require committed specs,
            committed repos, and leave behind persistent GHCR artifacts you don't want.

## Overview

Science Platform Images (SPI) Injection (`--inject-spi`) is a wrangler workflow that extracts portions of a wrangler spec and applies them to the appropriate locations within the science platform images repository to define a corresponding image build.  SPI Injection proper stops once `nb-wrangler` has completed a source code update. In essence, SPI Injection mirrors the process of transferring package and notebook requirements from Jira to an SPI repository checkout, allowing for the initiation of an image PR. From this point forward, an SPI Injection build functions as a standard SPI build.  These SPI functions (or their equivalent) are used to implement both GitHub workflows and local test/debug builds. In it's current incarnation, the artifacts injected into the repo clone are generally not saved, but the spec from which they originate is added to the built image at `/opt/environments/nbw-wrangler-spec.yaml`.

## Prerequisites

To perform SPI Injection, you will need:

- An installation of `nb-wrangler`.

- A complete `nb-wrangler` spec for the desired SPI image.

For image building and testing tasks you will need:

- Familiarity with Docker and git, and a ready-to-go Docker installation
   available at your terminal command line.  The command "docker" must be
   fully functional.

- Knowledge of how to configure and perform a standard SPI build.

## Example SPI Injection Workflow

The base injection command is straightforward:

```bash
$ nbw --clone --repos-dir spi-references --inject-spi specs/roman/RomanNexus-2026.2.yaml
INFO: 00:00:00.000 Using spec defined by NBW_SPEC = /home/ai/nb-wrangler-images/specs/roman/RomanNexus-2026.2.yaml
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler-images/specs/roman/RomanNexus-2026.2.yaml
INFO: 00:00:00.036 NBW_OVERRIDES_MODE is set to --dev.
INFO: 00:00:00.000 For other workflows or isolated steps, default --dev to False unless explicitly specified.
INFO: 00:00:00.000 Final value --dev is set to True. --prod is set to False.
INFO: 00:00:00.000 Running any explicitly selected steps.
INFO: 00:00:00.000 Explicit Step _spi_inject_reqs
INFO: 00:00:00.000 Initiating SPI injection into references/science-platform-images for wrangler kernel RomanNexus-2026.2...
INFO: 00:00:00.000 Injecting references/science-platform-images/deployments/wrangler/MISSION_VERSION
INFO: 00:00:00.000 Injecting references/science-platform-images/deployments/wrangler/environments/nbw-exports.sh
INFO: 00:00:00.000 Injecting references/science-platform-images/deployments/wrangler/environments/common-hints.mamba
INFO: 00:00:00.000 Injecting references/science-platform-images/deployments/wrangler/environments/common-hints.pip
INFO: 00:00:00.000 Injecting references/science-platform-images/deployments/wrangler/environments/dockerfile-aux.sh
INFO: 00:00:00.000 Injecting 7 assets into references/science-platform-images/deployments/wrangler/environments...
INFO: 00:00:00.000 Processing asset 1: assets/generic/catalog-schema-browser.ipynb -> /opt/environments from https://github.com/spacetelescope/nb-wrangler-images.git
INFO: 00:00:00.775 Processing asset 2: assets/roman/cost-dashboard.ipynb -> /opt/environments from https://github.com/spacetelescope/nb-wrangler-images.git
INFO: 00:00:00.655 Processing asset 3: assets/generic/stop_server_ext.json -> /etc/jupyter/jupyter_server_config.d/ from https://github.com/spacetelescope/nb-wrangler-images.git
INFO: 00:00:00.628 Processing asset 4: assets/generic/stop_server_ext.json -> /srv/jupyter/ from https://github.com/spacetelescope/nb-wrangler-images.git
INFO: 00:00:00.604 Processing asset 5: assets/generic/jp_app_launcher.yaml -> $HOME/.local/share/jupyter/jupyter_app_launcher/ from https://github.com/spacetelescope/nb-wrangler-images.git
INFO: 00:00:00.619 Processing asset 6: assets/generic/post-start-hook -> /opt/environments from https://github.com/spacetelescope/nb-wrangler-images.git
INFO: 00:00:00.632 Processing asset 7: assets/generic/test -> /opt/environments from https://github.com/spacetelescope/nb-wrangler-images.git
INFO: 00:00:00.680 SPI injection complete.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:04
```

Note that all --inject-spi does is copy various aspects of the spec and other web assets into the local clone of science-platform-images (SPI). In the above case the SPI source code clone is now ready for a wrangler image build. In principle developer can "cd" to the SPI clone root directory and go about a normal SPI image-build.  However, to make development a little more coherent, the wrangler has thin wrappers that can do that for you for all of the classic image-xxx scripts.


**Expert Tip**

If you're iterating a lot and in the examples below, two environment variables can come in handy:

- `NBW_SPEC` can be set to the path of the wrangler spec so you can stop typing it.
- `NBW_OVERRIDES_MODE` can be set to `--dev` or `--prod` so you don't have to remember to type it in contexts where the value is implied or needs to be overriden.

For brevity,  the examples blow assume they are set.

### Updating SPI Source Code

Perform the standard SPI injection with `--inject-spi` to add the appropriate details from the spec to the spi-references/science-platform-images clone.  That updated clone is the focal point for follow-on tasks below such as building an image.

```bash
$ nbw --inject-spi
```

### Build a Local Docker image

Build an image with the `--spi-image-build` command running the original SPI image-build script on your local Docker as a subprocess.

```bash
$ nbw --spi-image-build
```

### Run Wrangler Tests in the Image Container

Run SPI's `image-test` (actually test in the container) script using `--spi-image-test`.  This runs the wrangler `--test-imports` and/or `--test-notebooks` tests inside the resulting Docker container.

```bash
$ nbw --spi-image-test

$ nbw --spi-image-test='--test-notebooks --verbose --dev'

$ nbw --spi-image-test='--test-all --verbose --prod'
```

It's possible to pass parameters into the underlying image-test but they must be specified as
a single string starting with `--test-all`, `--test-imports`, or `--test-notebooks`. If you do not specify any parameters the image-test defaults are used which currently mean `--test-imports`.

This is similar to and built upon wrangler's `--test-imports` and `--test-notebooks` commands but the difference is that the --spi version is running inside the Docker container instead of in the local environment.

### Scan the Image for Vulnerabilities

Run SPI's `image-scan` on locally on the Docker image using `--spi-image-scan`.

```bash
$ nbw --spi-image-scan
```

**WARNING** SPI's `image-scan` automatically installs the scanner packages in your current environment if they are not already installed.  Currently they're just `mamba` packages but it might be surprising if you're not ready for it.  The current scanner is also fairly resource intensive so you'll need the required memory and disk space to run it adequately.

### Running Jupyter Lab Locally

Once the image has been built locally, you can launch Jupyter Lab in a Docker container for interactive development and testing against the actual environment defined by your spec:

```bash
$ nbw --spi-run-lab
```

This runs `jupyter lab` in an ephemeral container with port forwarding enabled. Choose "Shutdown Jupyter Lab" from the JupyterLab File menu to exit cleanly when you're done.

### GitHub Authentication (`gh auth login`)

To enable `nbw` to push branches and create Pull Requests on GitHub, you must first authenticate the GitHub CLI (`gh`). You can do this by running:

```bash
gh auth status

gh auth login
```

Follow the prompts to authenticate using your GitHub account. A standard GitHub CLI token will work.  This capability was a feature of the first generation build process but is now seldom used.

