# Science Platform Images (SPI) Injection

## Overview

Science Platform Images (SPI) Injection is a semi-automated workflow which enables
extracting portions of a wrangler spec and dropping them into the appropriate locations
in the science platform images respository to define a corresponding image build.

Unlike true "wrangler" image builds which are fully automatic and built by a pipeline,
SPI Injection really stops as soon as nb-wrangler has performed a source code update.
In other words,  SPI Injection is the equivalent of transferring package and notebook
requirements from Jira to an SPI repo checkout where they can start defining an image
PR.   From that point forward, an SPI Injection build is just a classic SPI build.
From that perspective,  SPI injection is a fallback mode and minor time saver relative
to the new wrangler pipeline...  should wrangler images prove to be problematic in some way.

## Prerequisites

Since SPI Injection really just converts a wrangler spec into an SPI repo update, to
perform one all that you will need is:

1. An installation of nb-wrangler.
2. A completed nb-wrangler spec for an SPI image.

However,  to make practical use of the output, what you really need in addition is:

3. Familiarity with Docker and GitHub workflows and instlations of both Docker and git.
4. Knowledge of how to configure and perform a classic SPI build.
5. Access to an image repository to which you can push your final built image,  classically ECR.
6. Access to science-platform-images on GitHub so you can PR your build changes.

## Example SPI Injection Workflow

Here's an example workflow that demonstrates how to use SPI injection assuming that git,
docker, and nb-wrangler are already set up and a wrangler spec we want to inject is available.

The injection command is very simple:

```bash

$ nb-wrangler --clone --repos-dir spi-references --inject-spi sample-specs/tike-2025-07-beta.yaml 
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/sample-specs/tike-2025-07-beta.yaml
INFO: 00:00:00.035 Running explicitly selected steps, if any.
INFO: 00:00:00.000 Running step _clone_repos
INFO: 00:00:00.000 Setting up repository clones.
INFO: 00:00:00.000 Cloning  repository https://github.com/jaytmiller/science-platform-images.git to spi-references/science-platform-images.
INFO: 00:00:01.435 Successfully cloned repository to spi-references/science-platform-images.
INFO: 00:00:00.000 Cloning --single-branch repository https://github.com/spacetelescope/mast_notebooks to spi-references/mast_notebooks.
INFO: 00:00:04.199 Successfully cloned repository to spi-references/mast_notebooks.
INFO: 00:00:00.000 Cloning --single-branch repository https://github.com/spacetelescope/tike_content to spi-references/tike_content.
INFO: 00:00:01.493 Successfully cloned repository to spi-references/tike_content.
INFO: 00:00:00.003 Found 8 notebooks in all notebook repositories.
INFO: 00:00:00.000 Processing 8 unique notebooks for imports.
INFO: 00:00:00.001 Extracted 7 package imports from 8 notebooks.
INFO: 00:00:00.000 Revising spec file /home/ai/nb-wrangler/sample-specs/tike-2025-07-beta.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/temps/tike-2025-07-beta.yaml.
INFO: 00:00:00.057 Running step inject
INFO: 00:00:00.000 Initiating SPI injection into spi-references/science-platform-images for tike kernel tess...
INFO: 00:00:00.000 Injecting field test_imports to spi-references/science-platform-images/deployments/tike/environments/tess/tests/imports
INFO: 00:00:00.000 Injecting field mamba_spec to spi-references/science-platform-images/deployments/tike/environments/tess/tess.yml
INFO: 00:00:00.000 Injecting field pip_compiler_output to spi-references/science-platform-images/deployments/tike/environments/tess/tess.pip
INFO: 00:00:00.000 Saving spec file to spi-references/science-platform-images/deployments/tike/environments/nbw-wrangler-spec.yaml.
INFO: 00:00:00.055 SPI injection complete.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:07

```

NOTE: because nb-wrangler is very heavy handed about deleting repo clones, we set `--repos-dir` to some
private path which in this instance will be *writable* in order to absorb the SPI injection updates; we
use a custom directory name to prevent nb-wrangler from trying to delete it.

The end goal of the injection is then avaialble in the subdirectory `references\science-platform-images`
as can be seen from git status below:

```bash
$ cd spi-references/science-platform-images
$ git status
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
        modified:   deployments/tike/environments/tess/tess.pip
        modified:   deployments/tike/environments/tess/tess.yml
        modified:   deployments/tike/environments/tess/tests/imports

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        deployments/tike/environments/nbw-wrangler-spec.yaml

no changes added to commit (use "git add" and/or "git commit -a")
```

As you can see from the `git status`, the mamba (tess.yml) and pip (tess.pip)
package requirements,  and the import tests, have been extracted from the
input spec and injected into the declarative section of the TIKE deployment
of our science-platform-images clone.

Additionally,  the spec itself has been added to the environments directory
under the generic name nbw-wrangler-spec.yaml from whence it can be utilized
to perform wrangler functions like testing or data installation later;  in
the fully built image,  the spec will be located at `/opt/environments/mb-wrangler-spec.yaml`.

Before proceeding it's a good idea to add and commit all the changes under
`spi-references/science-platform-images/deployments`:

```bash
$ git checkout -b my-spi-branch
$ git add deployments
$ git commit
```

If you have docker installed from this point you can go straight into a classic
local SPI image build:

```bash
$ scripts/image-configure tike
$ source setup-env
$ image-build
```

Like all classic builds,  while getting a fully built image and environment is
the bulk of the work, the exact details of the `post-start-hook` and or deployment
`test` function may need to be reworked to adjust for the current set of notebooks,
etc. In principle the wrangler can automate both of these as well even for classic
builds but in practice it required pulling in too many common changes from nb-wrangler
not to add additional development effort and risk.

## Key Differences from True Wrangler Builds

While both `SPI injection` and `submit-for-build` approaches
use the wrangler spec to define package requirements and related notebooks and/or data,
they differ significantly in how the corresponding images are acutally built:

### SPI Injection

`SPI Injection` based builds have these basic properties:

1. Primitive, the only real automation beyond the original build scripts is limited to
   filling in package requirements and tests defined by a wrangler spec.
2. Continues to build images using original mission Dockerfiles which perform arbitrary actions
   including custom library or package builds not available from mamba or pip.
3. Package installation and cleanup is performed using classic build scripts: `env-conda`,
   `env-compile`, `env-sync`, etc.
4. Requires manual configuration of `post-start-hook` and tests to manage things like
   git-sync'ing and notebook test setup.
5. Requires manual image-build, scanning, tagging, and push.

### Wrangler Submit For Build

The wrangler submit-for-build approach is characterized by:

1. Fully automated image builds, scanning, tagging, and hosting based on submitting a spec.
2. Environment and package installation using nb-wranger itself vs. classic install scripts
   such as `env-conda`, `env-compile`, and `env-sync`, resulting in higher fidelity reproductons
   of local spec-based development and test installs.
3. Support for a new single kernel vs. base + mission kernel approaches with minor spec
   changes.   This trades stability and isolation of mission environment for simplicity and
   smaller images.
4. Significantly smaller images overall since only spec'ed software is installed.
5. Software currently limited to mamba and pip packages,  no ad hoc UNIX libraries or Ubuntu
   packages yet.
