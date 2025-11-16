# Managing Notebook Reference Data with nb-wrangler

## Data Curation

`nb-wrangler` streamlines the management of data files required by notebooks. This process, known as data curation, relies on `refdata_dependencies.yaml` files. These YAML files, typically located in the root directory of notebook repositories, define the data associated with a `nb-wrangler` spec.

Similar to `requirements.txt` for Python packages, `refdata_dependencies.yaml` files are maintained by notebook repository owners. `nb-wrangler` interprets these definitions to handle the download, installation, and location of data, making it accessible via environment variables.

`nb-wrangler` also augments these data definitions with metadata like the length and hash of each data archive file. This metadata, computed after the initial download, helps verify data integrity during subsequent installations, though it's not foolproof.

### refdata_dependencies.yaml



The `refdata_dependencies.yaml` file, provided by notebook repositories, defines data requirements. Its initial format is as follows:



```yaml

# Defines data installations for Python packages.

install_files:

  pandeia:

    version: 2025.9

    data_url:

      - https://stsci.box.com/shared/static/0qjvuqwkurhx1xd13i63j760cosep9wh.gz

    environment_variable: pandeia_refdata # Environment variable to reference installed data

    install_path: ${HOME}/refdata/        # Top directory for data installation

    data_path: pandeia_data-2025.9-roman  # Directory name for unpacked tarball

    # Final path: install_path + data_path.

    # install_path can be overridden for shared data paths (e.g., Nexus setup).

  stpsf:

    version: 2.1.0

    data_url:

      - https://stsci.box.com/shared/static/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz

    environment_variable: STPSF_PATH

    install_path: ${HOME}/refdata/

    data_path: stpsf-data

  stips:

    version: 2.3.0

    data_url:

      - https://stsci.box.com/shared/static/761vz7zav7pux03fg0hhqq7z2uw8nmqw.tgz

    environment_variable: stips_data

    install_path: ${HOME}/refdata/

    data_path: stips_data

  synphot:

    version: 1.6.0

    data_url:

      - https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_everything_multi_v18_sed.tar

      - https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_star-galaxy-models_multi_v3_synphot2.tar

      - https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_castelli-kurucz-2004-atlas_multi_v2_synphot3.tar

      - https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_kurucz-1993-atlas_multi_v2_synphot4.tar

      - https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_pheonix-models_multi_v3_synphot5.tar

      - https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_calibration-spectra_multi_v13_synphot6.tar

      - https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_jwst_multi_etc-models_multi_v1_synphot7.tar

      - https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_modewave_multi_v1_synphot8.tar

      - https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar

    environment_variable: PYSYN_CDBS

    install_path: ${HOME}/refdata/

    data_path: grp/redcat/trds/

# Environment variables that do not require a data download.

other_variables:

  CRDS_SERVER_URL: https://roman-crds-tvac.stsci.edu

  CRDS_CONTEXT: roman_0027.pmap

  CRDS_PATH: ${HOME}/crds_cache

  ```



This format is defined by notebook repository maintainers and used by other systems (e.g., GitHub CI). `nb-wrangler` validates these files for its internal use and integrates them into the `nb-wrangler` spec. While `nb-wrangler`'s environment curation doesn't directly include each `requirements.txt` file, it does add each verbatim, along with any other `nb-wrangler`-computed information.

`nb-wrangler` then adds additional metadata to the spec, such as:

```yaml
    local_exports:
      CRDS_SERVER_URL: https://roman-crds-tvac.stsci.edu
      CRDS_CONTEXT: roman_0027.pmap
      CRDS_PATH: ${HOME}/crds_cache
      pandeia_refdata: ${HOME}/refdata/pandeia_data-2025.9-roman
      STPSF_PATH: ${HOME}/refdata/stpsf-data
      stips_data: ${HOME}/refdata/stips_data
      PYSYN_CDBS: ${HOME}/refdata/grp/redcat/trds/
    pantry_exports:
      CRDS_SERVER_URL: https://roman-crds-tvac.stsci.edu
      CRDS_CONTEXT: roman_0027.pmap
      CRDS_PATH: ${HOME}/crds_cache
      pandeia_refdata:
        ${NBW_PANTRY}/shelves/roman-20-roman-cal/data/pandeia_data-2025.9-roman
      STPSF_PATH: ${NBW_PANTRY}/shelves/roman-20-roman-cal/data/stpsf-data
      stips_data: ${NBW_PANTRY}/shelves/roman-20-roman-cal/data/stips_data
      PYSYN_CDBS: ${NBW_PANTRY}/shelves/roman-20-roman-cal/data/grp/redcat/trds
    metadata:
      roman_notebooks/pandeia/0qjvuqwkurhx1xd13i63j760cosep9wh.gz:
        size: '578788837'
        sha256: 736766b93e12d5adff9499b3a69a676e78d12d0ddff3a5193430cbab688bb978
      roman_notebooks/stpsf/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz:
        size: '92295282'
        sha256: d30eb72b571b0e9f09a091909bf16f679f23c30d327ce6fc09ace227790be6bf
      roman_notebooks/stips/761vz7zav7pux03fg0hhqq7z2uw8nmqw.tgz:
        size: '153097868'
        sha256: 15a430e67c7526abb4bd0f56379631ef7cb10a93f72b5d5dbd7919b441422d6a
      roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_everything_multi_v18_sed.tar:
        size: '1285222400'
        sha256: 3f01b858d88960f864cad56a03d2425955ae3951a979378da612af960c5f6b59
      roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_star-galaxy-models_multi_v3_synphot2.tar:
        size: '90347520'
        sha256: 66faaaeeb04e855a09c6cb8bc9b748c8fbedf23b782208dba84e10c4f0fd450b
      roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_castelli-kurucz-2004-atlas_multi_v2_synphot3.tar:
        size: '42772480'
        sha256: 8f7a220bc9480900c372015847057b06a2c218ae8b2dbf8020e6a1dd2990b42c
      roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_kurucz-1993-atlas_multi_v2_synphot4.tar:
        size: '81684480'
        sha256: 95ca73356f38a703064c346e286f571b53f78964d5511d1b538ff086f5ce897e
      roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_pheonix-models_multi_v3_synphot5.tar:
        size: '1868328960'
        sha256: 1ffb5e136dc4f846cd95b83843eb89f7a5171f58732705b25f07a99c4d8cf50d
      roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_calibration-spectra_multi_v13_synphot6.tar:
        size: '8695121920'
        sha256: 69b3ba91db2a3290bacbe48ef7b7626905567d89e7e03d11b3cefeadf5f26fd7
      roman_notebooks/synphot/hlsp_reference-atlases_jwst_multi_etc-models_multi_v1_synphot7.tar:
        size: '8909717'
        sha256: 01b2eae81852d56971796a62c82ff7f76256e1fdaabccf2f7f09151b1283640a
      roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_modewave_multi_v1_synphot8.tar:
        size: '34160640'
        sha256: 3338b1fb400d752c02c06132e0ce804ef8a9751f6ff535b41d022f60b0364d81
      roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar:
        size: '121835520'
        sha256: b8901e54c03a185d19cd08e9590a7b959d82901d02abc7a9a3f468c8691db70b
```

This additional data includes:

-   **`local_exports`**: Defines data locations for personal use, based on `refdata_dependencies.yaml`, along with general-purpose environment variables.
-   **`pantry_exports`**: Specifies data locations within the `$NBW_PANTRY` persistent storage area, supporting shared installations for teams. Notebooks should ideally operate relative to these paths without modification.
-   **`metadata`**: `nb-wrangler`-computed archive file hashes (SHA256) and sizes. These are used to verify data consistency between the initial curation and subsequent re-installation workflows. Failures indicate potential data integrity issues.

## Storage Categories


To operate efficiently on STScI science platforms, `nb-wrangler` utilizes two main disk storage areas. 

For local personal installations, both areas can reside on SSDs, offering equivalent performance, and can even be mapped to a single top-level directory.



These storage areas are defined and located using environment variables, with default values shown below:



| Env Variable | Default Location  | Description                                        |
| :----------- | :---------------- | :------------------------------------------------- |
| `NBW_ROOT`   | `$HOME/.nbw-live` | Fast, ephemeral storage for frequently accessed files. |
| `NBW_PANTRY` | `$HOME/.nbw-pantry`| Slower, persistent storage for shared archives and installations. |



### Persistent Storage (Pantry)



On containerized systems (e.g., JupyterHub, Docker), persistent storage like user `$HOME` directories or team directories survives individual container runs. While crucial for data longevity, their performance can be inferior to other storage types (e.g., local SSDs), especially for numerous small files.



Typically, this might be a network file system (e.g., EFS) easily shared across containers in a compute cluster. Its persistence makes it ideal for storing archive files such as data archives or pre-built Python installations, reducing repeated downloads and installations. Its shareability enables shared data and compute environments for teams or general platform use.



`nb-wrangler` refers to its persistent storage area as the `Pantry`, typically pointed to by the `NBW_PANTRY` environment variable. The Pantry is structured to store persistent data for multiple `nb-wrangler` specs, with each spec having its own subdirectory for both archive files and unpacked versions of files intended for sharing. Currently, it stores data archives and Mamba environment archives.



### Live Storage (Live)



On containerized systems, the container storage itself is typically ephemeral (erased between user sessions) but often backed by high-performance hardware like SSDs. `nb-wrangler` terms its ephemeral storage area `Live`, usually pointed to by the `NBW_ROOT` environment variable. Live storage is limited in size (e.g., <50GB, variable) and designed for frequently accessed but not necessarily shared files. It offers performance comparable to pre-installed files in the container image. Conceptually, `nb-wrangler` Mamba environments unpacked from pre-installed archives to live storage should perform similarly to pre-installed environments. For data, it can offer superior performance, as data is often too large for direct inclusion in a science platform image but suitable for unpacking into private container storage.

## Wrangling / Curating Data



The initial phase of data wrangling involves notebook repository curators and/or platform administrators ensuring that required data is available in public archive files and referenced in the repository's `refdata_dependencies.yaml` spec file. This phase includes:



*   Adjusting notebooks.

*   Creating and modifying the `refdata_dependencies.yaml` file.

*   Creating, updating, and delivering new archive files to public repositories for `nb-wrangler` users to download.



During curation, `nb-wrangler` downloads and unpacks data archives into the appropriate Pantry locations if they don't already exist. It also configures the environment to correctly reference the unpacked data, enabling platform-independent notebook access. Once notebooks correctly reference their data, the entire end-to-end process (downloading notebooks and data, setting up Mamba environments) can be tested.



As part of curation, `nb-wrangler` captures the length and SHA256 hash of each archive file. These are later verified against the `refdata_dependencies.yaml` spec during future installations. Validation failures indicate data integrity issues relative to when the `nb-wrangler` spec was created.

### Example --data-curate

```bash
../../nb-wrangler data-test-spec.yaml --data-reset-spec && \
../../nb-wrangler data-test-spec.yaml --data-curate --data-select 'pandeia|stpsf|other-spectra_multi_v2_sed'
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml
INFO: 00:00:00.000 Running explicitly selected steps, if any.
INFO: 00:00:00.000 Running step _data_reset_spec
INFO: 00:00:00.000 Saving spec file to /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml.
INFO: 00:00:00.028 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:00
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml
INFO: 00:00:00.000 Running workflows {self.config.workflows}.
INFO: 00:00:00.000 Running data collection / downloads / metadata capture / unpacking workflow
INFO: 00:00:00.000 Setting up repository clones.
INFO: 00:00:00.000 Using existing local clone at references/science-platform-images
INFO: 00:00:00.000 Using existing local clone at references/roman_notebooks
INFO: 00:00:00.001 Found 13 notebooks in all notebook repositories.
INFO: 00:00:00.000 Processing 13 unique notebooks for imports.
INFO: 00:00:00.002 Extracted 27 package imports from 13 notebooks.
INFO: 00:00:00.000 Revising spec file /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/temps/data-test-spec.yaml.
INFO: 00:00:00.057 Collecing data information from notebook repo data specs.
INFO: 00:00:00.000 New data exports file available at /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/nbw-local-exports.sh
INFO: 00:00:00.000 New data exports file available at /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/nbw-pantry-exports.sh
INFO: 00:00:00.000 Revising spec file /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml.
INFO: 00:00:00.032 Downloading selected data archives.
INFO: 00:00:00.000 Downloading data from 'https://stsci.box.com/shared/static/0qjvuqwkurhx1xd13i63j760cosep9wh.gz' to archive file 'roman_notebooks/pandeia/0qjvuqwkurhx1xd13i63j760cosep9wh.gz'.
--2025-11-09 14:28:23--  https://stsci.box.com/shared/static/0qjvuqwkurhx1xd13i63j760cosep9wh.gz
Resolving stsci.box.com (stsci.box.com)... 74.112.186.157, 2620:117:bff0:12d::
Connecting to stsci.box.com (stsci.box.com)|74.112.186.157|:443... connected.
HTTP request sent, awaiting response... 301 Moved Permanently
Location: /public/static/0qjvuqwkurhx1xd13i63j760cosep9wh.gz [following]
--2025-11-09 14:28:23--  https://stsci.box.com/public/static/0qjvuqwkurhx1xd13i63j760cosep9wh.gz
Reusing existing connection to stsci.box.com:443.
HTTP request sent, awaiting response... 301 Moved Permanently
Location: https://stsci.app.box.com/public/static/0qjvuqwkurhx1xd13i63j760cosep9wh.gz [following]
--2025-11-09 14:28:23--  https://stsci.app.box.com/public/static/0qjvuqwkurhx1xd13i63j760cosep9wh.gz
Resolving stsci.app.box.com (stsci.app.box.com)... 74.112.186.157, 2620:117:bff0:12d::
Connecting to stsci.app.box.com (stsci.app.box.com)|74.112.186.157|:443... connected.
HTTP request sent, awaiting response... 302 Found
... some output elided ...
Connecting to public.boxcloud.com (public.boxcloud.com)|74.112.186.164|:443... connected.
HTTP request sent, awaiting response... 200 OK
Length: 578788837 (552M) [application/octet-stream]
Saving to: ‘0qjvuqwkurhx1xd13i63j760cosep9wh.gz’

0qjvuqwkurhx1xd13i63j760cosep9wh.gz                                100%[=============================================================================================================================================================>] 551.98M  43.5MB/s    in 13s     

2025-11-09 14:28:38 (41.5 MB/s) - ‘0qjvuqwkurhx1xd13i63j760cosep9wh.gz’ saved [578788837/578788837]

INFO: 00:00:15.210 Downloading data from 'https://stsci.box.com/shared/static/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz' to archive file 'roman_notebooks/stpsf/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz'.
--2025-11-09 14:28:38--  https://stsci.box.com/shared/static/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz
Resolving stsci.box.com (stsci.box.com)... 74.112.186.157, 2620:117:bff0:12d::
Connecting to stsci.box.com (stsci.box.com)|74.112.186.157|:443... connected.
HTTP request sent, awaiting response... 301 Moved Permanently
Location: /public/static/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz [following]
--2025-11-09 14:28:38--  https://stsci.box.com/public/static/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz
Reusing existing connection to stsci.box.com:443.
HTTP request sent, awaiting response... 301 Moved Permanently
Location: https://stsci.app.box.com/public/static/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz [following]
--2025-11-09 14:28:38--  https://stsci.app.box.com/public/static/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz
Resolving stsci.app.box.com (stsci.app.box.com)... 74.112.186.157, 2620:117:bff0:12d::
Connecting to stsci.app.box.com (stsci.app.box.com)|74.112.186.157|:443... connected.
... some output elided ...
Connecting to public.boxcloud.com (public.boxcloud.com)|74.112.186.164|:443... connected.
HTTP request sent, awaiting response... 200 OK
Length: 92295282 (88M) [application/octet-stream]
Saving to: ‘kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz’

kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz                                100%[=============================================================================================================================================================>]  88.02M  29.6MB/s    in 3.0s    

2025-11-09 14:28:43 (29.6 MB/s) - ‘kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz’ saved [92295282/92295282]

INFO: 00:00:04.780 Downloading data from 'https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar' to archive file 'roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar'.
--2025-11-09 14:28:43--  https://archive.stsci.edu/hlsps/reference-atlases/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar
Resolving archive.stsci.edu (archive.stsci.edu)... 130.167.201.60
Connecting to archive.stsci.edu (archive.stsci.edu)|130.167.201.60|:443... connected.
HTTP request sent, awaiting response... 200 OK
Length: 121835520 (116M) [application/x-tar]
Saving to: ‘hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar’

hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar    100%[=============================================================================================================================================================>] 116.19M  8.60MB/s    in 12s     

2025-11-09 14:28:55 (10.1 MB/s) - ‘hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar’ saved [121835520/121835520]

INFO: 00:00:11.800 Selected data downloaded successfully.
INFO: 00:00:00.000 Collecting metadata for downloaded data archives.
INFO: 00:00:00.000 Computing sha256 for archive file 'roman_notebooks/pandeia/0qjvuqwkurhx1xd13i63j760cosep9wh.gz'.
INFO: 00:00:01.184 Computing sha256 for archive file 'roman_notebooks/stpsf/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz'.
INFO: 00:00:00.193 Computing sha256 for archive file 'roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar'.
INFO: 00:00:00.253 Revising spec file /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml.
INFO: 00:00:00.033 Validating all downloaded data archives.
INFO: 00:00:00.000 Validating data archive 'roman_notebooks/pandeia/0qjvuqwkurhx1xd13i63j760cosep9wh.gz'.
INFO: 00:00:00.000 Computing sha256 for archive file 'roman_notebooks/pandeia/0qjvuqwkurhx1xd13i63j760cosep9wh.gz'.
INFO: 00:00:01.196 Validating data archive 'roman_notebooks/stpsf/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz'.
INFO: 00:00:00.000 Computing sha256 for archive file 'roman_notebooks/stpsf/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz'.
INFO: 00:00:00.197 Validating data archive 'roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar'.
INFO: 00:00:00.000 Computing sha256 for archive file 'roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar'.
INFO: 00:00:00.267 All data archives validated.
INFO: 00:00:00.000 Unpacking downloaded data archives to live locations.
INFO: 00:00:03.716 Unpacked /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/archives/roman_notebooks/pandeia/0qjvuqwkurhx1xd13i63j760cosep9wh.gz into /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/data
INFO: 00:00:00.663 Unpacked /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/archives/roman_notebooks/stpsf/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz into /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/data
INFO: 00:00:00.078 Unpacked /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/archives/roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar into /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/data
INFO: 00:00:00.000 New data exports file available at /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/nbw-local-exports.sh
INFO: 00:00:00.000 New data exports file available at /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/nbw-pantry-exports.sh
INFO: 00:00:00.000 Saving spec file to /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml.
INFO: 00:00:00.062 Workflow data collection / downloads / metadata capture / unpacking completed.
INFO: 00:00:00.000 Running explicitly selected steps, if any.
INFO: 00:00:00.000 Running explicitly selected steps, if any.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:39
```

## Re-installing Data



The second phase of data wrangling involves downloading, verifying, and installing data on the target system. In this phase, the `nb-wrangler` spec (assembled during `--curate` and `--data-curate` operations) is treated as read-only. `nb-wrangler` uses its environment variables, primarily `NBW_ROOT` and `NBW_PANTRY`, to manage the overall installation.



Re-installing data includes:

1.  Downloading data locally.

2.  Verifying its metadata (size and SHA256 hash).

3.  Unpacking the data as specified.

4.  Configuring the environment to point to the installation locations.



Environment configuration is achieved through a combination of bash scripts (which can be sourced) and environment settings within JupyterLab kernel specs, installed in user persistent storage. The `--data-select` parameter allows users to specify a regular expression to match key fields of data archive paths, enabling selective re-installation.

### Example --data-reinstall

```bash
../../nb-wrangler data-test-spec.yaml --data-reinstall --data-select 'pandeia|stpsf|other-spectra_multi_v2_sed'
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/tests/data-functional/data-test-spec.yaml
INFO: 00:00:00.000 Running workflows {self.config.workflows}.
INFO: 00:00:00.000 Running data download / validation / unpacking workflow
INFO: 00:00:00.032 Downloading selected data archives.
INFO: 00:00:00.000 Archive file for '0qjvuqwkurhx1xd13i63j760cosep9wh.gz' already exists a '/home/ai/.nbw-pantry/shelves/roman-20-roman-cal/archives/roman_notebooks/pandeia'. Skipping downloads.
INFO: 00:00:00.000 Archive file for 'kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz' already exists a '/home/ai/.nbw-pantry/shelves/roman-20-roman-cal/archives/roman_notebooks/stpsf'. Skipping downloads.
INFO: 00:00:00.000 Archive file for 'hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar' already exists a '/home/ai/.nbw-pantry/shelves/roman-20-roman-cal/archives/roman_notebooks/synphot'. Skipping downloads.
INFO: 00:00:00.000 Selected data downloaded successfully.
INFO: 00:00:00.000 Validating all downloaded data archives.
INFO: 00:00:00.000 Validating data archive 'roman_notebooks/pandeia/0qjvuqwkurhx1xd13i63j760cosep9wh.gz'.
INFO: 00:00:00.000 Computing sha256 for archive file 'roman_notebooks/pandeia/0qjvuqwkurhx1xd13i63j760cosep9wh.gz'.
INFO: 00:00:01.187 Validating data archive 'roman_notebooks/stpsf/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz'.
INFO: 00:00:00.000 Computing sha256 for archive file 'roman_notebooks/stpsf/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz'.
INFO: 00:00:00.200 Validating data archive 'roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar'.
INFO: 00:00:00.000 Computing sha256 for archive file 'roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar'.
INFO: 00:00:00.259 All data archives validated.
INFO: 00:00:00.000 Unpacking downloaded data archives to live locations.
INFO: 00:00:03.675 Unpacked /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/archives/roman_notebooks/pandeia/0qjvuqwkurhx1xd13i63j760cosep9wh.gz into /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/data
INFO: 00:00:00.694 Unpacked /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/archives/roman_notebooks/stpsf/kqfolg2bfzqc4mjkgmujo06d3iaymahv.gz into /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/data
INFO: 00:00:00.096 Unpacked /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/archives/roman_notebooks/synphot/hlsp_reference-atlases_hst_multi_other-spectra_multi_v2_sed.tar into /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/data
INFO: 00:00:00.000 New data exports file available at /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/nbw-local-exports.sh
INFO: 00:00:00.000 New data exports file available at /home/ai/.nbw-pantry/shelves/roman-20-roman-cal/nbw-pantry-exports.sh
INFO: 00:00:00.000 Workflow data download / validation / unpacking completed.
INFO: 00:00:00.000 Running explicitly selected steps, if any.
INFO: 00:00:00.000 Running explicitly selected steps, if any.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:06
```

## Installed Environment Variable Setup



As seen in the `refdata_dependencies.yaml` example, each archive section (e.g., `pandeia`) is associated with an `environment_variable`. This variable should point to the root location of its unpacked data, allowing notebooks to reference it independently of the installation path.



### Data Install Locations



`nb-wrangler` supports two primary modes for defining data installation locations:



#### *Pantry Mode (Default)*

In Pantry Mode, `nb-wrangler` replaces the `install_path` with a standard location within the Pantry for that specific spec. 

This ensures that unpacked data is always stored in a location unique to a particular spec, facilitating seamless switching between different versions of code and their associated data.

Conceptual example of a `pantry` mode definition for an environment variable:



```sh
install_path_override="${NBW_PANTRY}/shelves/<shelf>/data/${section}"

export pandeia_refdata="<install_path_override>/<data_path>"
```

where *install_path_override* is only defined to clarify how Pantry mode differs from Spec mode and `<>` notation
is used to show substitution of spec values vs. literal shell syntax.

#### *Spec Mode*

Spec Mode allows the `refdata_dependencies.yaml` to fully define the data installation location *outside* the Pantry. 

This mode can be activated using the `--data-env-vars-mode spec` option during data packing or unpacking.

Conceptual example of a `spec` mode definition for an `nb-wrangler` environment variable:


```sh
export pandeia_refdata="<install_path>/<data_path>"
```

where again `<>` notation is used to show substitution of values vs. literal shell syntax and operations.



### Automatic Environment Variable Kernel Registration



Regardless of where archive sections are unpacked, `nb-wrangler` automatically adds their corresponding environment variable definitions to the JupyterLab kernel spec. This makes these variables available for use within notebooks without manual configuration.



### Shell Environment Variable Exports



In addition to kernel registration, `nb-wrangler` generates "exports" files named `nbw-pantry-exports.sh` and `nbw-local-exports.sh`. These files can be sourced to define data locations for shell environments and JupyterLab terminals.