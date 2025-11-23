# Managing Notebook Selection and Environments with nb-wrangler

The "wrangler half" of notebook curation revolves around the creation of a fully populated and tested
wrangler spec that catches the repos, notebooks, Python environment, and data associated with a single
Science Platform environment.
 
 The current process is to *define the spec*:

- Bootstrap and/or install nb-wrangler
- Copy an existing wrangler spec from the same project. See sample-specs.
- Update the header section of the spec.
- Add repo and notebook selection information to the selected_notebooks section.
- Add any extra mamba packages or mamba version constraints;  minimize these to those not available by pip
- Add any extra pip packages or pip version constraints not defined in requirements.txt files

Once the curator's inputs are specified,  *run nb-wrangler* like this:

```bash
./nb-wrangler my-spec.yaml --curate
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/sample-specs/roman-20.0.0.yaml
INFO: 00:00:00.017 Running workflows ['curation'].
INFO: 00:00:00.000 Running spec development / curation workflow
INFO: 00:00:00.000 Running step _clone_repos.
INFO: 00:00:00.000 Setting up repository clones.
INFO: 00:00:00.000 Using existing local clone at references/science-platform-images
INFO: 00:00:00.000 Using existing local clone at references/roman_notebooks
INFO: 00:00:00.001 Selected 7 notebooks under references/roman_notebooks/notebooks repository:
INFO: 00:00:00.000 Found stpsf.ipynb under references/roman_notebooks/notebooks.
INFO: 00:00:00.000 Found romanisim.ipynb under references/roman_notebooks/notebooks.
INFO: 00:00:00.000 Found roman_cutouts.ipynb under references/roman_notebooks/notebooks.
INFO: 00:00:00.000 Found pandeia.ipynb under references/roman_notebooks/notebooks.
INFO: 00:00:00.000 Found rist.ipynb under references/roman_notebooks/notebooks.
INFO: 00:00:00.000 Found synphot.ipynb under references/roman_notebooks/notebooks.
INFO: 00:00:00.000 Found time_domain_simulations.ipynb under references/roman_notebooks/notebooks.
INFO: 00:00:00.000 Found 7 notebooks in all notebook repositories.
INFO: 00:00:00.000 Processing 7 unique notebooks for imports.
INFO: 00:00:00.002 Extracted 27 package imports from 7 notebooks.
INFO: 00:00:00.000 Revising spec file /home/ai/nb-wrangler/sample-specs/roman-20.0.0.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/temps/roman-20.0.0.yaml.
INFO: 00:00:00.025 Running step _compile_requirements.
INFO: 00:00:00.000 Generating mamba spec for target environment /home/ai/.nbw-live/temps/roman-20.0.0-roman-cal-mamba.yml.
INFO: 00:00:00.000 Found SPI extra 1 mamba requirements files.
INFO: 00:00:00.001 Revising spec file /home/ai/nb-wrangler/sample-specs/roman-20.0.0.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/temps/roman-20.0.0.yaml.
INFO: 00:00:00.028 Found 7 notebook requirements.txt files.
INFO: 00:00:00.000 Found SPI extra 6 pip requirements files.
INFO: 00:00:00.000 w/o hashes.
INFO: 00:00:02.325 Compiled combined pip requirements to 366 package versions.
INFO: 00:00:00.000 Revising spec file /home/ai/nb-wrangler/sample-specs/roman-20.0.0.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/temps/roman-20.0.0.yaml.
INFO: 00:00:00.063 Running step _initialize_environment.
INFO: 00:00:00.009 Creating environment: roman-cal
INFO: 00:00:19.356 Environment roman-cal created. It needs to be registered before JupyterLab will display it as an option.
INFO: 00:00:00.379 Registered environment roman-cal as a jupyter kernel making it visible to JupyterLab as 'Roman Research Nexus'.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/mm/envs/roman-cal/roman-20.0.0.yaml.
INFO: 00:00:00.066 Running step _install_packages.
INFO: 00:00:00.000 Installing packages from: ['/home/ai/.nbw-live/temps/roman-20.0.0-roman-cal-pip.txt']
INFO: 00:00:21.266 Package installation for roman-cal completed successfully.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/mm/envs/roman-cal/roman-20.0.0.yaml.
INFO: 00:00:00.057 Running step _save_final_spec.
INFO: 00:00:00.000 Saving spec file to /home/ai/nb-wrangler/sample-specs/roman-20.0.0.yaml.
INFO: 00:00:00.058 Saving spec file to /home/ai/.nbw-pantry/shelves/roman-20.0.0-roman-cal/nbw-wranger-spec.yaml.
INFO: 00:00:00.063 Workflow spec development / curation completed.
INFO: 00:00:00.000 Running any explicitly selected steps.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:43
```

to download repos, scrape requirements, and build the corresponding environment.

As a quick check on the built environment you can try out the notebook imports with `--test-imports`:

```sh
./nb-wrangler my-spec.yaml --test-imports

INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/sample-specs/roman-20.0.0.yaml
INFO: 00:00:00.037 Running any explicitly selected steps.
INFO: 00:00:00.000 Running step _test_imports
INFO: 00:00:00.000 Testing imports by notebook for 7 notebooks...
INFO: 00:00:00.000 Testing imports for references/roman_notebooks/notebooks/pandeia/pandeia.ipynb.
INFO: 00:00:00.000 Testing 3 imports
INFO: 00:00:00.245 Import of numpy succeeded.
INFO: 00:00:00.061 Import of pandeia succeeded.
INFO: 00:00:00.147 Import of scipy succeeded.
INFO: 00:00:00.000 All imports succeeded.
INFO: 00:00:00.000 Testing imports for references/roman_notebooks/notebooks/rist/rist.ipynb.
INFO: 00:00:00.000 Testing 1 imports
INFO: 00:00:01.883 Import of plot_rist succeeded.
INFO: 00:00:00.000 All imports succeeded.
INFO: 00:00:00.000 Testing imports for references/roman_notebooks/notebooks/roman_cutouts/roman_cutouts.ipynb.
INFO: 00:00:00.000 Testing 8 imports
INFO: 00:00:00.317 Import of asdf succeeded.
INFO: 00:00:02.777 Import of astrocut succeeded.
INFO: 00:00:00.185 Import of astropy succeeded.
INFO: 00:00:00.211 Import of matplotlib succeeded.
INFO: 00:00:00.121 Import of numpy succeeded.
INFO: 00:00:01.304 Import of roman_datamodels succeeded.
INFO: 00:00:00.355 Import of s3fs succeeded.
INFO: 00:00:00.049 Import of warnings succeeded.
INFO: 00:00:00.000 All imports succeeded.
INFO: 00:00:00.000 Testing imports for references/roman_notebooks/notebooks/romanisim/romanisim.ipynb.
INFO: 00:00:00.000 Testing 15 imports
INFO: 00:00:00.057 Import of argparse succeeded.
INFO: 00:00:00.252 Import of asdf succeeded.
INFO: 00:00:00.196 Import of astropy succeeded.
INFO: 00:00:00.189 Import of astroquery succeeded.
ERROR: 00:00:00.048 Failed to import dask:Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'dask' ::: 
INFO: 00:00:00.058 Import of dataclasses succeeded.
INFO: 00:00:00.780 Import of galsim succeeded.
INFO: 00:00:00.051 Import of importlib succeeded.
INFO: 00:00:00.213 Import of matplotlib succeeded.
INFO: 00:00:00.123 Import of numpy succeeded.
INFO: 00:00:01.857 Import of pysiaf succeeded.
INFO: 00:00:01.134 Import of roman_datamodels succeeded.
INFO: 00:00:00.103 Import of romanisim succeeded.
INFO: 00:00:00.355 Import of s3fs succeeded.
INFO: 00:00:00.057 Import of typing succeeded.
ERROR: 00:00:00.000 Failed to import 1: ['dask']
INFO: 00:00:00.000 Testing imports for references/roman_notebooks/notebooks/stpsf/stpsf.ipynb.
INFO: 00:00:00.000 Testing 4 imports
INFO: 00:00:00.184 Import of astropy succeeded.
INFO: 00:00:00.214 Import of matplotlib succeeded.
INFO: 00:00:00.122 Import of numpy succeeded.
INFO: 00:00:02.650 Import of stpsf succeeded.
INFO: 00:00:00.000 All imports succeeded.
INFO: 00:00:00.000 Testing imports for references/roman_notebooks/notebooks/synphot/synphot.ipynb.
INFO: 00:00:00.000 Testing 6 imports
INFO: 00:00:00.184 Import of astropy succeeded.
INFO: 00:00:00.217 Import of matplotlib succeeded.
INFO: 00:00:00.120 Import of numpy succeeded.
INFO: 00:00:01.765 Import of stpsf succeeded.
INFO: 00:00:00.844 Import of stsynphot succeeded.
INFO: 00:00:00.830 Import of synphot succeeded.
INFO: 00:00:00.000 All imports succeeded.
INFO: 00:00:00.000 Testing imports for references/roman_notebooks/notebooks/time_domain_simulations/time_domain_simulations.ipynb.
INFO: 00:00:00.000 Testing 18 imports
INFO: 00:00:00.059 Import of argparse succeeded.
INFO: 00:00:00.253 Import of asdf succeeded.
INFO: 00:00:01.202 Import of astrocut succeeded.
INFO: 00:00:00.189 Import of astropy succeeded.
INFO: 00:00:00.063 Import of dataclasses succeeded.
INFO: 00:00:00.576 Import of galsim succeeded.
INFO: 00:00:00.055 Import of glob succeeded.
INFO: 00:00:00.048 Import of importlib succeeded.
INFO: 00:00:00.215 Import of matplotlib succeeded.
INFO: 00:00:00.123 Import of numpy succeeded.
INFO: 00:00:01.181 Import of pysiaf succeeded.
INFO: 00:00:01.096 Import of roman_datamodels succeeded.
INFO: 00:00:00.096 Import of romancal succeeded.
INFO: 00:00:00.090 Import of romanisim succeeded.
INFO: 00:00:00.052 Import of shutil succeeded.
INFO: 00:00:01.063 Import of sncosmo succeeded.
INFO: 00:00:00.060 Import of typing succeeded.
INFO: 00:00:00.047 Import of warnings succeeded.
INFO: 00:00:00.000 All imports succeeded.
ERROR: 00:00:00.000 FAILED step _test_imports ... stopping...
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 3
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:26
```

**NOTE:** the above import test shows a failure where checking imports discovers
in 26 seconds that the environment does not support `dask` so there is still more 
work to do with  notebook and/or spec curation.

As a short-cut to avoid constantly retyping the spec path you can also:

```bash
export NBW_SPEC=/full/path/to/the/spec.yaml
./nb-wrangler --curate --test-imports
... output omitted,  see above ...
```

Once the environment is built successfully, you can automatically run all of the notebooks headlessly with:

```sh
./nb-wrangler my-spec.yaml --test-notebooks
```

## Introduction

This section discusses working with the aspects of `nb-wrangler` that let you choose repos
and notebooks which will be covered by a spec, as well as the basic properties of the
environment being defined such as environment name, display name, image name Python version,
etc.

For more information on defining the wrangler spec to get started see [Wrangler Spec Format](spec-format.md)

Curation involves iteratively updating notebooks repos, packages, and available reference
data until the desired combination of repos and notebooks actually work together in some fashion;
these fundamentals are independent of nb-wrangler. In the context of nb-wrangler,  curation
also involves defining specs which specify the notebooks, Packages, and data needed by one 
tested, working, self-consistent environment. So nb-wrangler does not, of itself, make the 
fundamentals work. nb-wrangler makes it easier to specify, build, test, distribute, and 
re-install solutions supporting multiple notebook repos and/or notebooks with a single Python
and reference data environment. 

In terms of information, nb-wrangler spec (and repo refdata_dependencies.yaml specs) define:

1. Notebooks which fulfill the purpose of this build.  Maybe it is a "generic" Roman environment.
2. Mutually consistent mamba and Python packages which can support these notebooks.
3. A set of reference data needed by these notebooks.
4. Environment variables defining data locations.
5. Environment variables defining other constant values such as CRDS_CONTEXT.
6. A set of "import tests" implicitly defined by the notebooks.

## Curation Fastpath

### Setting key nb-wrangler environment variables

During development,  your best chances of using nb-wrangler successfully are to create a fully
independent wrangler environment whereever you want to work,  it could be your laptop:

#### Laptop Env settings

```
# no changes needed,  nb-wrangler installs under $HOME in hidden .nbw-live and .nbw-pantry
# directories
```

#### Science Platform Env Settings

Another (potentially better) option could be on a science platform in an OPS or TEST environment
working solo from your personal $HOME directory:

```
export NBW_ROOT="/tmp/nbw-live"
export NBW_PANTRY="$HOME/.nbw-pantry"
```

**TIP:** Add those to .bashrc and .bash_profile to make sure they are always added to any new shells.

Note that the entire distinction between ROOT and PANTRY has to do with the underlying
performance and persistence of the associated storage.  The above setup is intended so
that NBW_ROOT is fast but not persistent, while NBW_PANTRY is persistent and unfortunately
slow as a consequence.  (Persistence refers to "not forgotten between notebook sessions
on the science platform.  Nevertheless, maye require unpacking to restore )

### Bootstrapping

After setting env vars as above, See [README.md](../README.md) for instructions on bootstrapping
the nb-wrangler software. This will install


### Failures and Process Iteration

If you encounter errors in the test phase and need to circle back to
earlier steps,  depending on what work needs to be repeated,  you may
need to `--reset-curation` to remove artifacts of earlier runs which
would otherwise short circuit the required repeat work as "already performed".

Environment curation can be reset like this:

```sh
nb-wrangler spec.yaml --reset-curation [--delete-repos]
```

This results in resetting the spec, deleting the environment, clearing package
caches, and any other required cleanup needed before resuming curation of
modified inputs.  Removing the repos is optional but the simplest way to
get a robust update of upstream changes.

