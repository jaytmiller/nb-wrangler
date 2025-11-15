The following example of a notebook repo *refdata_dependencies.yaml* file was developed to specify data dependencies
for a Python environment in a notebook-repo-defined format.

The example below is the initial prototype definition for
Roman 20 development and may be updated as Roman 20 development is completed:

```
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

The spec contains two high level sections:

- install_files - defines a series of named data archive `section`s each of which defines one aspect of roman-20's refdata and specifies the download of one or more archive files and related infromation.
- other_variables - defines environment variables that do not require an data download and install. For each variable, the name of the variable is given followed by a value.

Within each named `section` of install_files there are the following fields:

- version - specifies the version of this data section taken in aggregate for all its URL's
- data_url - the data_url is a list of URLs of tarballs to install.  each url must include a viable tar file archive and compression identifying file extension, e.g. .tgz
- environment_variable - variable to reference the installed data of *this section* from notebooks, scripts, and other programs.
- install_path - location at which `tar` will run to unpack the archive.
- data_path - path extension to be added to `install_path` to define full path for the data. for typical archives, this should be a single top level directory rather than deep path taken relative to the root of the data source system.

For Nexus setup, the install_path value can be overridden to point to a shared data path.  To that end the wrangler has several data archive unpacking modes:

- local - data should be unpacked at the location of `install_path` specified by refdata_depenencies.yaml interpreted within the local environment.
- pantry - data should be unpacked at a standard directory of the pantry shelf for this wrangler spec, persistent on science platforms.
- live - data should be unpacked at a standard directory of the wrangler's live storage area defined by NBW_LIVE, possibly ephemeral on science platforms.