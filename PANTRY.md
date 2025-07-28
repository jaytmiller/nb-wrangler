# NB-Curator's Pantry, Shelves, and Cans

## Overview

NB-Curator has two primary stores for information:

- The **nbc-live** directory where the isolated curator and target environments are first
  installed, archived to pantry shelves, and later unarchived from the pantry
  back to a restored live environment.

- The **nbc-pantry** directory where a collection of **shelves** are stored. Each shelf
  holds shared readonly static assets (notebooks, data, etc...)
  and one or more micromamba-environment archives reverred to as **cans**.

While all users have personal nbc-live directories, only hub admins and team admins have
write acces to shared pantries. The task of e.g. preparing for a webbinar or conference,
or setting up a shared team environment, is performed by creating a new shelf in the pantry.

## NBC-Live Directory Structure

The **NB-Curator Live Directory** is fairly simple and has only a few key parts:

- The single-file binary **micromamba** program
- An **envs** directory where micromamba-environment archives are stored as singe subdirectories.
- A **cache** directory where micromamba caches files for faster access during installs.
- A **envs/pkgs** directory where uv packages are also cached for faster access during installs.
- A **temps** directory where nb-curator generated files are stored to support install tools.

## NBC-Pantry Structure

The **NB-Curator Pantry** is a collection of staged notebook-centric analysis environments
each of which is referred to as a "shelf". Each shelf contains several things which taken as
a whole can provide a complete environment for running a particular set of notebooks.

### Shelf Structure

#### Live Assets

Each shelf has a number of live but readonly assets which are intended to be shared by all users of the
shelf. These include:

- **Notebooks**: Jupyter notebooks that the shelves Python environments were specifically constructed to support.
- **Notebook Input Data**: Data directories and files used as readonly inputs to the notebooks.
- **Environment Variables**: Configuration settings that are specific to the shelf.

#### Frozen Assets

Each shelf has a number of frozen assets which are intended to be unpacked onto faster storage media for quick access. These include:

- **Cans**: Each can is a compressed archive of a single curated environment.  Because it is a single compressed
            file, it is very fast to unpack and use,  even when transferred from EFS. In fact poor performance
            working with small files on EFS is the main reason cans exist.  It is MUCH faster to do installations
            on local storage than EFS, so by using cans we can speed up installation times both during curation
            and later during operations.
