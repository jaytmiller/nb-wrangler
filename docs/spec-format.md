# Wrangler Spec Format

## Example Spec

Below is a prototype wrangler spec for TIKE:

```yaml
image_spec_header:
  image_name: TIKE 2025.07-beta
  deployment_name: tike  # currenty tike, roman, or jwebbinar
  kernel_name: tess      # currently tess, roman-cal, or masterclass (and conda env name)
  display_name: TESS     # menu item in JupyterLab kernel selection list
  description: |
    This is a beta test of the latest TIKE packages. Use at your own risk!
  valid_on: 2025-07-02
  expires_on: 2025-10-02
  python_version: 3.11.13
selected_notebooks:
  - nb_repo: https://github.com/spacetelescope/tike_content
    nb_root_directory: content/notebooks/
    include_subdirs:
      - data-access/
      - lcviz-tutorial/
      - tglc/
      - zooniverse_view_lightcurve/
  - nb_repo: https://github.com/spacetelescope/mast_notebooks
    nb_root_directory: notebooks/TESS
    include_subdirs:
      - beginner_how_to_use_lc
      - beginner_tour_lc_tp
  - nb_repo: https://github.com/spacetelescope/mast_notebooks
    nb_root_directory: notebooks/Kepler
    include_subdirs:
      - identifying_transiting_planet_signals
      - instrumental_noise_4_electronic_noise
extra_mamba_packages:
  - pip
extra_pip_packages:
  - boto3
system:
  spec_version: 1.0
  archive_format: .tar
  spi_url: https://github.com/jaytmiller/science-platform-images.git
  spec_sha256: f5dffe6b0e2cfcf4a1b246e8bfa34d81c9db169ad117873d55e48d98928e40ba
```

## Sections of the Wrangler Spec

### **image_spec_header**
This section provides metadata about the image and Python environment
   - **image_name**: A name for your image (e.g., `TIKE 2025.07-beta`).
   - **deployment_name**: The deployment name, which can be `tike`, `roman`, `jwebbinar`, or `wrangler`.
   - **kernel_name**: The kernel name, currently `tess`, `roman-cal`, or `masterclass` for SPI injection,  anything for wrangler.
   - **display_name**: The name as it will appear in the JupyterLab kernel selection list (e.g., `TESS`).
   - **description**: A brief description of the image and its purpose.
   - **valid_on** and **expires_on**: Dates specifying when the image becomes valid and when it expires, respectively.
   - **python_version**: The version of Python supported by the image (e.g., `3.11.13`).

### **selected_notebooks**

Defines a list of repo and notebook selections  and is the heart of the wrangler spec since it also implies 
Python package (per-notebook `requirements.txt`) and data requirements (global per-repo `refdata_dependencies.yaml`).

As part of the curation process the wrangler will automatically clone 
each notebook respository so that it can be searched for requirements files of different kinds and
also support tests by running them directly from a notebook's source directory.

While scraping notebook repo inputs,  the wrangler assumes that:

1. Each notebook directory will include at least one .ipynb notebook file.
2. Each notebook directory may include at least on requirements.txt file.
3. Each notebook directory may include one or more .py files to support the notebook.
4. The repo may contain on refdata_dependencies.yaml file specifying data requirements for its notebooks.

Each `selected_notebooks` entry has the following fields:

  - **nb_repo**: 
  This field specifies the GitHub repository URL where the notebooks are located. 
  For example, `https://github.com/spacetelescope/mast_notebooks` or `https://github.com/spacetelescope/tike_content`. When filling this out, ensure you provide a valid GitHub repository URL that contains the notebooks you wish to include.
  - **nb_root_directory**: 
  This defines the root directory within the repository where the notebooks are stored. Examples include `notebooks/TESS` or `content/notebooks/`. Fill this field with the path to the parent of the directory containing your notebooks, relative to the repository's root.
  - **include_subdirs**: 
  This is a list of subdirectories under `nb_root_directory` that you want to include. For instance, `- beginner_how_to_use_lc` or `- data-access/`. When specifying subdirectories, make sure to prefix them with a hyphen and keep them indented under the `include_subdirs` line. Note that these can be regexes or complete path continuations under `nb_root_directory` if desired. Defaults to regex .*
  - **exclude_subdirs**: 
  This is a list of subdirectories under `nb_root_directory` that should be excluded. For instance, `- beginner_how_to_use_lc` or `- data-access/`. When specifying subdirectories, make sure to prefix them with a hyphen and keep them indented under the `exclude_subdirs` line. Note that these can be regexes or complete path continuations under `nb_root_directory` if desired. Defaults to regexes for notebook checkpoint directories.

The combination of `nb_root_directory` and `include_subdirs` and `exclude_subdirs` is flexible and allows different selection styles:

1. Pick notebook directories directly under `nb_root_directory` as individual `include_subdirs` lines.  This avoids the clutter of repeating `nb_root_directory` with each notebook in an otherwise simple explicit list. Spell everything out, but factor out any redundant prefix.
2. To keep things really simple, leave `nb_root_directory` as an emptry string and just include the full path from the root of the repo to the notebook directory.  Verbose but simple.
3. By finding all subpaths under `nb_root_directory` containing at least one `.ipynb` file, then filtering those with `include_subdirs` or `exclude_subdirs` regexes. This makes "include everything" easy. Very succint and potentially maintenance free. Generally this would entail something like `include_subdirs: ".*"` backed up by `exclude_subdirs: "the-one-notebook-to-omit|the-other-notebook-to-omit"`.

### **extra_mamba_packages**
list additional mamba packages which are required by your environment but not specified by the notebook repo itself. For example, `- pip` or `- boto3`. When filling these out, list each package on a new line, prefixed with a hyphen. Note that mamba packages should be limited to build tools and compiled libraries not available on PyPi to the extent possible.

### **extra_pip_packages**
list additional pip packages required by your environment that aren't included by default. For example, `boto3` is very useful on AWS but may have been left as optional until actually used by some packages. List each package on a new line, prefixed with a hyphen. These packages should all be available on PyPi.

### **system**
This section contains specifications for the system environment.  Unlike the preceeding sections is updated by nb-wrangler automatically and should rarely need curator updates barring changes to the wrangler system itself.

   - **spec_version**: The version of the specification being used (e.g., `1.0`).
   - **archive_format**: The format used for archiving environments (e.g., `.tar`).
   - **spi_url**: The URL of the GitHub repository for Science Platform Images (e.g., `https://github.com/jaytmiller/science-platform-images.git`).   This repo defines both extra platform package requirements and acts as a build hub where wrangler specs can be submitted for an automatic build.
   - **spec_sha256**: An sha256 hash of the spec when it was last saved, for integrity checking. It primarily guards against accidental spec corruption during transit or storage, not hacking.

   