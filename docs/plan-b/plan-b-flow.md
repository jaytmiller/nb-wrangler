# Persistent Platform Environment Workflows

## Environment Specification Curation

These steps are needed to define and install an environment on the
science platform:

- Define wrangler specification basic environment properties like kernel name and Python version.
- Define notebook repos and notebook selections, extra or special packages, mission specific file assets.
- Curate notebook and packages using the `nbw` tool adding notebook and package locks to the spec.
- If curation fails, loop back to spec definition to resolve issues, redo all subsequent steps.
- If curation succeeds, archive the environment for future re-installation.

## Environment Un-Archiving and Usage

To use a persistent environment:

- Unpack EFS archive to container (~20 sec and one command)
- Activate environment in terminal or choose notebook kernel

Note that it is also possible to set up a live environment inside
a pantry on EFS to avoid the future need to unpack at the cost
of both installation time and potentially application runtime.

## A Single Pantry Environment

The directory structure of a single pantry environment corresponding
to a single wrangler spec:

/ spec.yaml
  / Code
     / Binary Code Archives
         Mamba Env Tarballs...
     / Optional Live Environment
         Mamba Live Env Files...
  / Data
     / Binary Data Archives
         Downloaded Data Tarballs...
     / Unpacked Data
         Live Data Dirs...

## Three Tiered Pantry Structure

Nominally users may want up to 3 independent pantries,  and perhaps more
if they are working on multiple teams:  personal, team pantries, system.

- The personal pantry is nominally stored at $HOME/.nbw-pantry
- The team pantries are norminally stored at /teams/team/nbw-pantry
- The system pantry is nominally stored at /teams/admin/nbw-pantry

Each pantry in turn can store multiple environments in packed, hybrid,
or unpackaed states: shared data is already stored both archived and
unpacked in the admin pantry.  as we add code, it can likewise be stored
in both archived and unpacked/live forms on EFS.  however,  nominally
code will be archived on EFS and unpacked to container storage to run.