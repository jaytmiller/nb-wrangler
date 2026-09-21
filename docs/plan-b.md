# Plab B Overview

Plan B is a science platform system powered by wrangler designed to leverage
the difference in performance between container storage and EFS in order to
support software environments that are relatively fast to install or re-install
on the science platform.  To achieve this Plan B uses ephemeral container
storage (for performance) and EFS (to persistently store installed binaries).
Plan B beats the EFS small file performance issue by only streaming to/from a
single large archive file on EFS.  Plan B is designed to enable switching
between multiple kernels on-the-fly, one per notebook or terminal window, once
they are activated.  (Fully realizing this switching will require supporting
only specs that have eliminated the refdata symlink in $HOME which is
relatively new, prob only roman >= 2026.2 + commissioning.)

- Command to install wrangler spec as live environment *and* archive to pantry for plan-b unpack later

  nbw specs/roman/nbw-wrangler-spec.yaml --reinstall --env-pack
  nbw specs/roman/nbw-wrangler-spec.yaml --data-install  (optional if shared data available? tricky)

- Command to uninstall live environment to release container space.

  nbw specs/roman/nbw-wrangler-spec.yaml --env-delete

- Command to restore archived environment to live status.

  nbw specs/roman/nbw-wrangler-spec.yaml --env-unpack

- Command to delete environment archive to release archive space.

  nbw specs/roman/nbw-wrangler-spec.yaml --env-archive-delete

- Simple commands (a) to create basic wrangler specs for personal/team use

  nbw --spec-init <filename>
  nbw --spec-from-conda
  nbw --spec-from-requirements

  Nothing fancy for these other than basically importing a conda env yml
  spec into wrangler format or a generic pip requirements.txt file into
  wrangler format.   Operating on specs remains primary.

- Simple commands (b) to immediately install from conda or requirements.txt
  specs based on an implied/generated/hidden wrangler spec.  This might require
  a few extra parameters like kernel name and Python version.

- Investigate official env archive formats

  Investigate mamba/micromamba environment bundling commands as alternative to less formal
  archives created with tar.   If Plan B is robust on the platform and using mamba unpacking
  commands results in performance loss,  keep informal tar archives for the platform at a minimum.

- Notation for referring to specs

   Whether local, web, or archived on ghcr, including globbing.

   For pantry searches use nbw://(pattern)
   For https use https://...
   For file use <local path>
   For registry use ghcr://<glob>

- Automatic association of correct data with active kernel

   Integration with wrangler data management so activated data tracks activated environment.
   Note that the current window (terminal or notebook) typically has associated with it an independent
   kernel which can be activated

- Ability to support user, team, and mission/image level kernel archives / pantries

   Propose NBW_PATH which points to pantry-1:pantry-2:pantry-3... enabling users to disambiguate
   same-name conflicts similar to UNIX PATH and programs.  e.g. if a RomanNexus-2026.2 happens to
   be in both pantry-1 and pantry-2,  the user gets the one in pantry-1.

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

- Set NBW_SPEC from spawner profile and "activate" the selected shared env during post-start-hook.

- Fancy in-session environment activation/deactivation/status

  Basic plan B will enable activating or deactivating environments using shell commands.

  A more advanced version would populate a menu in the lab interface with a list of pre-installed
  kernels which can be "activated" and then used normally to select the notebook or terminal
  kernel in use.

- Automatic environment activation?

  Having a plan-B environment archived at the team level is not implicitly the same thing as
  having it and *activating/unpacking* it for the current session.  Devise a mechanism for
  team or user define environments that are automatically unpacked and ready to use so that
  they can be selected in notebooks or activated in terminal windows without first manually
  activating them.

- Automatic environment curation

  Rather than just re-installing an environment at login or later,  fully recurate a spec
  during login (user could do this in .bashrc?) so that it recomputes the package versions
  as a curator does when building images.
