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

This format is defined by the notebook repository maintainers, independent of the nb-wrangler tool,  and used by other systems such as the GitHub CI system for notebooks.
Nevertheless nb-wrangler necessarily includes code which validates these files for
it's own internal use and/or round-tripping through the nb-wrangler spec.  While nb-wrangler's environment curation does not directly include each requirements.txt file,
nb-wrangler does add each refdata_dependencies.yaml file to the wrangler spec verbatim in addition to any other wrangler-computed information.

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

- **Live Storage**  - which may be ephemeral but is assumed to be high performance, e.g. a local SSD.  This makes a good place to store frequently used and readonly files for the current session, such as package caches or mamba installations.

- **Persistent Storage** - which is preserved between login sessions but which is sometimes much slower than a local SSD,  particularly for large numbers of small files, such as those found in Python installations. Typically this might be e.g. a network file system such as EFS which is easily shared between containers on a compute cluster. Because it is persistent, it can make an excellent place for archive files such as data archives or pre-built Python installations,  thus saving time relative to repeat downloads and installs.  Because it can be shared,  it enables both shared data and shared compute environments for teams or generic platform use.

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
personal $HOME directories or team directories survive individual container runs while
other parts of the container file system are ephemeral and forgotten after every notebook session.

### Live Storage

## Wrangling / Curating Data

### Example --data-curate Run

## Re-installing Data

### Example --data-reinstall Run

## Environment Setup

## Working on Data Selectively

