## Notebook Curation

The task of notebook curation revolves around the creation of a fully populated wrangler spec. The current
process is to:

- Bootstrap and/or install nb-wrangler
- Copy an existing wrangler spec from the same project. See sample-specs.
- Update the header section of the spec.
- Add notebook selection information to the selected_notebooks section.
- Add any extra mamba packages
- Add any extra pip packages
- Add any extra data files

Once the curator's inputs are specified,  run the nb-curator command to scrape the specified notebooks repos
and notebook directories for notebooks and package requirements, and then create a dedicated micromamba / mamba
environment as described by the spec and repos:

```bash
nb-wrangler --curate my-spec.yaml  --test
```

From here out it will likely be an iterative process of updating the spec, massaging package requirements and notebooks, re-compiling, re-installing, testing.


## Wrangler Spec Format

Creating a fully populated wrangler spec has a simple workflow that involves adjusting an existing YAML specification to specify new/different notebook and packages and other system properties the new spec will define:

### **image_spec_header**
This section provides metadata about the image.
   - **image_name**: A name for your image (e.g., `TIKE 2025.07-beta`).
   - **deployment_name**: The deployment name, which can be `tike`, `roman`, or `jwebbinar`.
   - **kernel_name**: The kernel name, currently `tess`, `roman-cal`, or `masterclass`.
   - **display_name**: The name as it will appear in the JupyterLab kernel selection list (e.g., `TESS`).
   - **description**: A brief description of the image and its purpose.
   - **valid_on** and **expires_on**: Dates specifying when the image becomes valid and when it expires, respectively.
   - **python_version**: The version of Python supported by the image (e.g., `3.11.13`).

### **selected_notebooks**
Defines a list of notebook selections each of which has the following fields:

  - **nb_repo**: 
  This field specifies the GitHub repository URL where the notebooks are located. 
  For example, `https://github.com/spacetelescope/mast_notebooks` or `https://github.com/spacetelescope/tike_content`. When filling this out, ensure you provide a valid GitHub repository URL that contains the notebooks you wish to include.
  - **nb_root_directory**: 
  This defines the root directory within the repository where the notebooks are stored. Examples include `notebooks/TESS` or `content/notebooks/`. Fill this field with the path to the directory containing your notebooks, relative to the repository's root.
  - **include_subdirs**: 
  This is a list of subdirectories under `nb_root_directory` that you want to include. For instance, `- beginner_how_to_use_lc` or `- data-access/`. When specifying subdirectories, make sure to prefix them with a hyphen and keep them indented under the `include_subdirs` line. Note that these can be regexes or complete path continuations under `nb_root_directory` if desired. Defaults to regex .*
  - **exclude_subdirs**: 
  This is a list of subdirectories under `nb_root_directory` that should be excluded. For instance, `- beginner_how_to_use_lc` or `- data-access/`. When specifying subdirectories, make sure to prefix them with a hyphen and keep them indented under the `exclude_subdirs` line. Note that these can be regexes or complete path continuations under `nb_root_directory` if desired. Defaults to regexes for notebook checkpoint directories.

### **extra_mamba_packages**
list of additional mamba packages which are required by your environment but not (yet?) specified by the notebook repo itself. For example, `- pip` or `- boto3`. When filling these out, list each package on a new line, prefixed with a hyphen. Note that mamba packages should be limited to build tools and compiled libraries not available on PyPi to the extent possible.

### **extra_pip_packages**
list additional pip packages required by your environment that aren't included by default. For example, `boto3` is very useful on AWS but may have been left as optional until actually used by some packages. List each package on a new line, prefixed with a hyphen. These packages should all be available on PyPi unless there is a compelling reason to get them from somewhere else.

### **system**
This section contains specifications for the system environment and unlike the preceeding sections is added by nb-wrangler automatically.

   - **spec_version**: The version of the specification being used (e.g., `1.0`).
   - **archive_format**: The format used for archiving environments (e.g., `.tar`).
   - **spi_url**: The URL of the GitHub repository for Science Platform Images (e.g., `https://github.com/jaytmiller/science-platform-images.git`).   This repo defines both extra platform package requirements and acts as a build hub where wrangler specs can be submitted for an automatic build.
   - **spec_sha256**: An sha256 hash of the spec when it was last saved, for integrity checking, easily updated if system compromised but hard to spoof and keep the same if compromised. Not a signature, does not identify authenticity with respect to a particular author, rather primarily accidental spec corruption.


