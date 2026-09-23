# Persistent Platform Environments

## Scope

This document explains the concepts behind user installed environments
and proposes the set of requirements defining the system to be implementd.

## Overview

Persistent Platform Environments (PPE's) are science platform mamba
environments that are installed directly on the platform instead of being
built into images. Wrangler makes it easy to manage the performance
differences between container storage (fast) and EFS (horrible small/many file 
performance) by systematically controlling how live environments are installed
on container storage or archived on EFS for reinstallation later.

This document enumerates requirements for a system to support user, team, or
system installed science platform mamba environments that persist between
notebook sessions and can be used by individuals or teams.

This system,  previously referred to as Wrangler Plan-B, largely arose from the
realization of the simplicity of the development loop as well as the multi-year
difficulty of getting a public Docker registry needed to support curator driven
development.

## Naming

Rather than calling this Wrangler Plan-B, I've gotten as far as describing
the system concept as `User Installed Persistent Environments` and the CLI
dedicated to it as `pet` for Persistent Environment Tool.

## Benefits

The benefits of User Installed Environments using `net`:

- Provides a fast replacement for the current *kernel-xxx* scripts that interoperate
  with the `nbw` tool used for notebook-driven image building.

- Enables the creation of completely generic base-environment-only images that are
  ~half the size of the current two kernel (base + mission) images and spawn more rapidly.
  This image would also be simpler and with fewer "concerns" if we can partition correctly,
  potentially reducing the frequency at which we rebuild this funtionality.
  Measured kernel "unpack" times of 20-30 seconds are probably < ECR transfer times for
  2-3G of environment binaries.

- Eliminates the need for but does not preclude an image registry and build pipelines.
  This was particularly attractive during years of struggle to get public registry support
  (DockerHub or GHCR) for GitHub image building.

- Ducks but does not preclude the automatic technical requirement and/or process for
  scanning these "350+ pacakge mission environments" because there is no image involved
  and it is equivalent to what users can and do already.  Meanwhile any smaller generic 
  base image should be much easier to keep clean on any required scans due to reduced
  package count.

- Enables parallel use of N kernels (including supporting data and environment variables)
  within a single notebook session without respawning.  This can be used to more
  flexibly debug old vs. new environment issues or work with multiple missions
  concurrently,  all without gigantic multi-environment images.

- Empowers users with wrangler's capabilities for determining multi-notebook package
  lists and package versions when used with supported notebook repos and selected notebooks.

- Can automatically install existing wrangler image specs as persistent environments.

- Provides a short path for promoting a user or teams personal environment to a notebook
  image supporting exactly that environment.  (Under the hood of `net`,  wrangler is still
  using a wrangler spec to define the environment.)

## What it isn't

While the ability to separate mission environments from a smaller base image and
resulting features and simplifications are attractive, one thing which is nominally
lost is Docker's ability to build once and install the same binary everywhere.  However,
that capability may be overrated compared to uv and lock files.

1. Put binary `net` archives in degenerate images and store them in ECR. However,
   this is an admin level function requiring access to Docker and ECR perms in addition
   to `net`.

2. Get a multi-SDLC S3 bucket and store archives and potentially whole pantries there
   as simple files vs. bastardized Docker images requiring Docker to push/pull from ECR.

## Required Features

### Simple as possible CLI

   Key to making this user-friendly will be providing a CLI tool that works in terms
   people are familiar with such as mamba .yaml specs and pip requirements.txt specs
   in addition to wrangler specs. A third candidate is uv specs but current wrangler
   support/usage of `uv` is limited to pip package management.  For operating
   on archived environments, referring to the environment MUST support lookups by
   kernel name but may include other beneficial mechanisms.

   **NOTE:** command examples given below are based on the current relatively
   complex nbw CLI used for curation and image building.  As such they are primarily
   technical notes on how the user CLI maps onto `nbw` features.  The user CLI will
   be a thin wrapper heavily dependent on existing functionality.

### Command to install and archive live environment to pantry

  nbw specs/roman/nbw-wrangler-spec.yaml --reinstall --env-pack
  nbw specs/roman/nbw-wrangler-spec.yaml --data-install  (optional for data if needed?)

### Command to re-install inactive environment from pantry

  nbw specs/roman/nbw-wrangler-spec.yaml --env-unpack

### Command to uninstall live environment

  While this is automatic on session shutdown, supporting it facilitates
  switching between multiple kernels without exceeding available container
  disk space.

  nbw specs/roman/nbw-wrangler-spec.yaml --env-delete

### Command to delete environment archive

  This process is not automatic. It deletes the archive and/or installed
  kernel from the pantry.

  nbw specs/roman/nbw-wrangler-spec.yaml --env-archive-delete

### Ability to install and/or unpack live environments on EFS

  This feature cannot be implemented quickly at install-time even with `uv`,
  but can completely bypass the 20 second activation time for each subsequent
  reactivation, basically leaving the environment live across sessions
  vs. unpacked on the container and lost at shutdown due to its temporary
  container unpack location.

### Commands to bootstrap environments

#### Basic spec stub

  nbw --spec-init [filename]

  This creates a basic stub wrangler spec that a user can edit as needed and
  then install and operate on either for persistent hub environments or curation
  of more complex scenarios.

#### Environment setup from mamba, pip, or wrangler specs

  This creates a basic spec or imports the given wrangler spec and immediately
  and transparently installs, registers, and archives a wrangler environment.
  The environment is then live and available in notebooks. Activation in terminals
  needs to be performed similar to `mamba activate blah`.

```/bin/sh
  nbw --spec-from-mamba [mamba-yml-spec] --spec-kernel-name [k] --spec-menu-name [m] --spec-python [p]
  nbw --spec-from-pip [pip-requirements.txt]  --spec-kernel-name [k] --spec-menu-name --spec-python [p]
  nbw --spec-from-wrangler [nbw-wrangler-spec.yaml]
  nbw --spec-from-notebooks https://<repo>/<root-path>/<notebook-glob>...
```

  Predicated on existing wrangler base environment supplied by image.  Wrangler adds environment persistence and coordination, data-handling, notebook awareness, extensible path for any 
  metadata we want/need.

### Investigate official env archive formats

   The POC environment archiving is based on the observation that mamba and micromamba environments
   are highly self-contained;  as such,  the archive format is simply .tar for speed with the option
   of compression to save space at a noticeable cost in speed.

  Investigate mamba/micromamba environment bundling commands as alternative to less formal
  archives created with tar.   If Plan B is robust on the platform and using mamba unpacking
  commands results in performance loss,  keep informal tar archives for the platform at a minimum.

- Notation for referring to specs

   Whether local, web, or archived on ghcr, including globbing.

```/bin/sh
   For pantry searches use nbw://(pattern)
   For https use https://...
   For file use <local path>
   For registry use ghcr://nbs_<glob>,  requires Docker won't work on platform
```

### Automatic association of correct data with active kernel

   Integration with wrangler data management so activated data tracks activated environment.
   Note that the current window (terminal or notebook) typically has associated with it an
   independent kernel each of which can potentially use different data.  This capability
   basically exists already but has not been "wrung out" in plural form,  just single env.

### Ability to support user, team, and mission/image level kernel archives / pantries

   Propose NBW_PATH which points to pantry-1:pantry-2:pantry-3... enabling users to disambiguate
   same-name conflicts similar to UNIX PATH and programs.  e.g. if a RomanNexus-2026.2 happens to
   be in both pantry-1 and pantry-2,  the user gets the one in pantry-1.

   ```/bin/bash
   export NBW_PANTRY=<pantry-1-path>:<pantry-2-path>:<pantry-3-path>...
   ```

   Manage this as automatically as possible.

- Barebones generic JupyterLab image

   Continue refining the wrangler base image.  The intent is to limit "deployments" to just wrangler
   and simplify the Dockerfile(s) and scripts (both repo level and installed) to the max possible.

   It should support 0 or 1 mission kernels and be as light as possible to reduce spawn times at one
   root: image size.  (What exactly has to be in the minimal base environment is part of the job.)

   Regardless of the mission kernel count (0 or 1),  it should interoperate with wrangler to
   support multiple plan-b environments.  That should have a clean decoupling burdensome to neither
   image building nor wrangler so we should be a little careful not to accidentally create more work.

   Using jupyter/docker-stacks for the image is optional and eliminating it should be explored
   to reduce image size and complexity. Areas where docker-stacks has already added "assumed policy"
   should however be carefully emulated,  e.g. image files are installed as jovyan:users so every
   platform user can operate on them depending on the perms associated with the (users) group.
   How the platform works assumes everyone is in "users" and the image is created leveraging that;
   this can affect things like "wrangler can write to image storage or not".

   It should be a goal to host the *existing* wrangler specs as plan-B environments.

   This can be a new GitHub repo or just take over science-platform-images (prefered).

   Controversial?  While complex, automatic Docker build caching should be preserved in some
   form,  for a bad image not re-downloading packages on every Docker run saves hours.

### In-session environment activation/deactivation/status

  Add GUI elements that interact with the base kernel to unpack/activate other kernels. The 
  GUI can display available kernels found in the user's defined pantries and make them usable
  in terminals and notebooks by unarchiving and registerining the kernel with jupyter.

### Automatic environment activation?

  Since having and archive environment requires unpacking to use it, provide some mechanism
  to reduce user burden with unpacking kernels.

  One simple possibility is add to .bashrc:

  ```/bin/sh
  NBW_PANTRY=$HOME/.nbw-pantry:/teams/my-team/nbw-pantry:$NBW_PANTRY
  nei --unpack  <important-kernel>
  ```

  Note that current images define `NBW_PANTRY` as `/home/admin/nbw-pantry` which above
  effectively makes the "image mission kernel" lowest priority.

### Automatic environment curation?

  Rather than unpacking a pre-installed archive at spawn or later, fully recurate
  a spec so that it recomputes the package versions as a curator does offline or
  using the GitHub pipeline.
  
  Designed carefully, this could make the curation pipeline more of a button press
  *on the hub* itself eliminating GHCR, GitHub, ECR,
  For the TEST server,  this pushes the "image/environment
  build" forward from GitHub to locally on the hub.  Like the GitHub pipeline, a
  decent interface here could make mission environment creation a low skill activity
  with no in-depth knowledge of wrangler or curation.

  