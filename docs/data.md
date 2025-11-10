# Managing Notebook Reference Data using nb-wrangler

## Data Curation

Similar to notebook and environment curation, nb-wrangler has workflows that allow you to curate data files.  The basic inputs defining the data associated with a wrangler
spec are kept in `refdata_dependencies.yaml` files which are found in the root directory of applicable notebook repositories.  Like requirements.txt files these data definition files are written by the notebook repository maintainers, and are added to the nb-wrangler spec and then further interpreted by nb-wrangler to properly support the download, installation, location via environment variables, and usage
of the data. Note that the wrangler further augments the data definition with the length
and hash of each data archive file but that these require at least one download to compute prior to existing to help verify the integrity of downloads;  consequently
the metadata scheme is not foolproof, but should fortify the long term integrity checking of the data as well as re-installation on additional platforms.

### refdata_dependencies.yaml

The refdata_dependencies.yaml file provided by applicable notebook repositories has an initial format that looks like this:

```yaml
# For each Python package that requires a data installation, give the
# package name and:
#   version - package version number
#   data_url - the data_url is a list of URLs of tarballs to install
#   environment_variable - variable to reference the installed data
#   install_path - top directory under which to install the data
#   data_path - name of the directory the tarball is expended into
# The final path to the data is the join os install_path + data_path.
#
# For Nexus setup, the install_path value can be overridden to point
# to a shared data path (instead of $HOME).
install_files:
  pandeia:
    version: 2025.9
    data_url: 
      - https://stsci.box.com/shared/static/0qjvuqwkurhx1xd13i63j760cosep9wh.gz
    environment_variable: pandeia_refdata
    install_path: ${HOME}/refdata/
    data_path: pandeia_data-2025.9-roman
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
# Add environment variables that do not require an data download
# and install. For each variable, the name of the variable is given
# followed by a value.
other_variables:
  CRDS_SERVER_URL: https://roman-crds-tvac.stsci.edu
  CRDS_CONTEXT: roman_0027.pmap
  CRDS_PATH: ${HOME}/crds_cache    # Nexus CRDS caches are local for now
  ```

This format is defined by the notebook repository maintainers, independent of the nb-wrangler tool, and used by other systems such as the GitHub CI system for notebooks.
Nevertheless nb-wrangler necessarily includes code which validates these files for it's own internal use and/or roucontinguend-tripping through the nb-wrangler spec.  While
nb-wrangler's environment curation does not directly include each requirements.txt file, nb-wrangler does add each  verbatim in addition to any other wrangler-computed information.

nb-wrangler then adds additional metadata such as this:

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

In the additional data you (and nb-wrangler) can find:

- **local_exports**  - information on data locations as defined by refdata_dependencies.yaml for personal use.  in addition there are general purpose env vars. 

- **pantry_exports**  - information on data locations as defined by nb-wrangler to locate data in the $NBW_PANTRY persistent storage area that supports shared installations for teams. ideally notebooks operate relative to these without change.

- **metadata**  - nb-wrangler computed archive file hashes and lengths to verify consistency between the wrangler's initial data curation workflow and the data re-installation workflow.   For each downloaded archive nb-wrangler computes, records,
and later verifies the size and sha256 hash for each archive file.

## nb-wrangler's Storage Categories

To efficiently support operation on the STScI science platforms,  nb-wrangler divides
the disk storage it uses into two major areas:

In the case of a local personal installation of an nb-wrangler environment, generally
both areas will reside on SSD with equivalent perfomance, and can even be mapped to a
single top-level directory for both.

These storage areas are defined and located using environment variables, with the default values shown below:

| Env Variable        | Default Location  | Description                              |
| ------------------- | ----------------- | ---------------------------------------- |
| NBW_ROOT            | $HOME/.nbw-live   | Fast but possibly emphemeral storage.    |
| NBW_PANTRY          | $HOME/.nbw-pantry | Slower but should be persistent          |


### Persistent Storage

On a containerized system such as JupyterHub or Docker, persistent storage such as
personal $HOME directories or team directories survive individual container runs. Their disadvantage is generally inferior performance compared to other storage such as a local SSD,  particularly for large numbers of small files.

Typically this might be e.g. a network file system such as EFS which is easily shared between containers on a compute cluster. Because it is persistent, it can make an excellent place for archive files such as data archives or pre-built Python installations,  thus saving time relative to repeat downloads and installs.  Because it can be shared,  it enables both shared data and shared compute environments for teams or generic platform use.

nb-wrangler dubs its persistent storage area the `Pantry` which is a directory tree nominally pointed to by the `NBW_PANTRY` environment variable. The Pantry is designed to store persistent data for multiple nb-wrangler specs where each spec has its own subdirectory which contains both archive files and unpacked
versions of files which are nominally intended to be shared. Currently two kinds of archives exist: data archives, and mamba environment archives.

### Live Storage

On a containerized system such as JupyterHub or Docker, the container storage itself is nominally ephemeral, i.e. completely erased between user sessions, and typically backed by high performance hardware such as SSD's. nb-wrangler dubs its ephemeral storage area `Live`, a directory tree nominally pointed to by the `NBW_ROOT` environment variable. The Live storage area is both limited in size (e.g. <50G,  variable) and intended for files which are frequently accessed but not necessarily shared. In this regard live storage is equivalent in performance to pre-installed files in the container image. Thus conceptually, wrangler mamba environments unpacked from pre-installed archives to live storage should have equivalent performance to environments which were pre-installed,  and in the case of data,  potentially superior performance since data is generally too large to be directly included in a science platform image but not too large to be unpacked into private container storage.

## Wrangling / Curating Data

The first phase of wrangling data is performed by notebook repo curators and/or plaform admins, and involves working with particular repos and notebooks to ensure that their required data is available in public archive files and referenced by the repo's `refdata_dependencies.yaml` spec file. As with environment creation, this phase can include adjusting notebooks, creating and adjusting the `refdata_dependencies.yaml` file, as well as creating, updating, and delivering new archive files to public repositories from which they can be downloaded by arbitrary nb-wrangler users. During curation, nb-wrangler downloads and unpacks the data archives if they are not already in the appropriate locations in the Pantry. Additionally, nb-wrangler sets up the environment to properly refer to the unpacked data so that notebooks can reference it in a platform independent way.  Once notebooks are correctly referencing their required data, they can be tested demonstrating that the entire end-to-end process of downloading notebooks and data,  and setting up supporting mamba environments, works.

As part of curation, nb-wrangler additionally captures the length and sha256 of each archive file so that they can later be verified against the `refdata_dependencies.yaml` spec during future installations. Failures to validate indicate issues with data integrity relative to the time the wrangler spec was created.

### Example --data-curate Run

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

The second phase of data wrangling is downloading, verifying, and installing the data in the target system.
In this phase, the wrangler spec assembled `--curate` and `--data-curate` is viewed as readonly and the
wrangler will target the overall install using its environment variables,  most critically `NBW_ROOT` and
`NBW_PANTRY`. Re-installing the data involves downloading it locally, verifying the metadata, unpacking the
data as directed, and configuring the environment to point to the installation locations.  Configuring the
environment is achieved by a combination of bash scripts which can be sourced and/or env settings in the 
JupyterLab kernel specs installed in user persistent storage.  It's worth noting that there is a `--data-select`
paramter which can be give a regex used to match key fields of the data archive paths.

### Example --data-reinstall Run

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

## Environment Variable Setup

As can be seen in the `refdata_dependencies.yaml` example above and brief excerpt here:

```yaml
install_files:
    pandeia:
    version: 2025.9
    data_url: 
        - https://stsci.box.com/shared/static/0qjvuqwkurhx1xd13i63j760cosep9wh.gz
    environment_variable: pandeia_refdata
    install_path: ${HOME}/refdata/
    data_path: pandeia_data-2025.9-roman
```

each archive section such as `pandeia` above is associated with N different URLs all of
which are expected to unpack to a `data_path` prefix directory using tar.  For each archive
nb-wrangler unpacks, it runs `tar` or the equivalent relative to `install_path` to unpack
individual files from the archive into usable locations. 

Consequently, one `local` definition of nb-wrangler environment vars is something like:

```sh
export pandeia_refdata="${install_path}${data_path}"
```

Meanwhile a `pantry` definition of environment variables is more like:

```sh
export pandeia_refdata="${NBW_PANTRY}/shelves/<shelf>/data/${section}/${environment_variable}"
```

### Pantry Paths

As previously discussed, nb-wrangler has a built-in persistent storage directory where it
can store artifacts related to multiple wrangler specs,  where each wrangler spec is associated
with one `Shelf`.  Within the shelf directory,  nb-wrangler further stores data archive files
so that future sessions can proceed without re-downloading data.

### Local Paths


### Working on Data Selectively

