"""Handles management of data specified in wrangler spec.

Similar to how package requirements are primarily specified by locating requirements.txt files
in the notebook directories of a notebook repo, the top level data spec is defined by a file
named `refdata_dependencies.yaml` which is stored at the top level of any notebook repository.
"""
import sys
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from . import utils
from .constants import DATA_SPEC_NAME, DATA_GET_TIMEOUT
from .config import WranglerConfig
from . import config
from .logger import WranglerLogger

"""
The initial implementation of a data spec for a single notebook repo was:
"""

'''
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
'''

"""
Similar to requirements.txt, the role of the data manager is to load refdata_dependencies.yaml files
from each repo included in the wrangler spec, resolve any conflicts between repos by requesting 
curator changes,  validate the spec for required keywords and live URLs, and then inline the combined
result in the `out:` section of the spec.  Within the out section of the wrangler spec, the wrangler 
will also add the length and sha256 for each archive file for integrity checking during later installs.

To support platform independence,  the wrangler will provide a switch which forces the definition of
bash script to define the exports required for each data item such that notebooks can use the environment
variables to locate as-installed data.
"""


@dataclass
class SingleUrl:
    url: str
    archive_dir: str
    abstract_path: str   # where to unpack including
    resolved_path: str   # Where to unpack relative to overridden(?) env vars
    size: int = 0
    sha256: str = "yyy"  # has to verify definitely not corrupted status,  very hard to spoof if known elsewhere, not a signature
 
    def todict(self):
        return dict(self.__dict__)

    def validate_sha256(self) -> None:
        if not self.archive_filepath.exists():
            raise utils.DataIntegrityError(f"Archive file does not exist at expected location {str(self.archive_filepath)}.")
        new_sha256 = utils.sha256_file(self.resolved_path)
        if self.sha256 != new_sha256:
            raise utils.DataIntegrityError(f"Data for '{self.url}' may be corrupt: Recorded sha256 is '{self.sha256}' but computed from '{self.archive_path}' is '{new_sha256}'.")

    def validate_filesize(self) -> None:
        size = self.archive_filepath.stat().st_size
        if self.size != size:
            raise utils.DataIntegrityError(f"Data for '{self.url}' may be corrupt: Recorded file size is '{self.size}' but computed from '{self.archive_path}' is '{size}'.")

    def validate_resolved_exists(self) -> None:
        path = Path(self.resolved_path)
        if path.exists():
            raise utils.DataIntegrityError(f"Data for '{self.url}' may be corrupt: Unpacked directory '{self.resolved_path}' does not exist.")

    def validate(self, kind: str = "") -> None:
        self.validate_filesize()
        if "sha256" in kind:
            self.validate_sha256()
        if "resolved-exists" in kind:
            self.validate_resolved_exists()

    @property
    def archive_filepath(self) -> Path:
        return Path(self.archive_dir) / os.path.basename(self.url)

    def download(self, force: bool = False) -> Path:
        if self.archive_filepath.exists() or force:
            return self.archive_filepath
        new_path = utils.robust_get(self.url, timeout=DATA_GET_TIMEOUT, cwd=str(self.archive_dir))
        if self.archive_filepath != new_path:
            raise DataDownloadError(f"Failed to download data from '{self.url}' expected filepath '{self.archive_filepath}' got '{new_path}'.")
        self.size = self.archive_filepath.stat().st_size
        self.sha256 = utils.sha256_file(self.archive_filepath)


@dataclass
class DataSection:
    """Represents a single data item in the ref."""
    name: str
    version: str
    env_var: str
    install_path: str
    data_path: str
    urls: list[str]
    url_map: list[str]
    archive_dir: str

    def __post_init__(self):
        for url in self.urls:
            self.url_map[url] = SingleUrl(url, self.archive_dir, self.abstract_path, self.resolved_path)

    @property
    def abstract_path(self):
        return os.path.join(self.install_path, self.data_path)

    @property
    def resolved_path(self):
        return config.global_config.resolve_overrides(self.abstract_path)

    def todict(self):
        d = dict(self.__dict__)
        d["urls"] = [url.todict() for url in self.urls]
        return d

    def download(self, *args):
        for url, single_url in self.url_map.items():
            single_url.download(*args)

    def validate(self, *args):
        for url, single_url in self.url_map.items():
            single_url.validate(*args)


class DataRepoSpec:
    """This class loads a single refdata_dependencies.yaml file including multiple
    named data sections each of which may have more than one URL which is represented
    by a DataSection instance.
    """
    def __init__(self, logger: WranglerLogger, yaml_string: str, archive_dir: str):
        self.logger = logger
        self._yaml_dict = utils.get_yaml().load(yaml_string)
        self.archive_dir = archive_dir
        self.data_dicts = self._yaml_dict["install_files"]
        self.extra_env = self._yaml_dict["other_variables"]
        self.data_items = {}
        
        for name, dd in self.data_dicts.items():
            try:
                self.data_items[name] = DataSection(
                    name=name,
                    version=dd["version"],
                    env_var=dd["environment_variable"],
                    install_path=dd["install_path"],
                    data_path=dd["data_path"],
                    urls=dd["data_url"],
                    url_map={},
                    archive_dir=archive_dir
                )
            except Exception as e:
                self.logger.exception(e, f"Failed creating data section {name}.")

    @classmethod
    def from_string(cls, yaml_string, archive_dir: str = "."):
        return cls(logger, yaml_string, archive_dir)

    @classmethod
    def from_file(cls, logger, filepath, archive_dir: str = "."):
        with open(filepath) as stream:
            yaml_string = stream.read()
            return cls.from_string(logger, yaml_string, archive_dir)

    def validate_spec(self):
        """Validate that the refdata_dependencies.yaml is well structured and with
        sound HEAD for urls.
        """
        for data_item in self.data_items.values():
            data_item.validate()

    def download_spec(self, *args):
        for data_item in self.data_items.values():
            data_item.download(*args)


class DataManager:
    """This class manages all the data associated with a single *wrangler* spec,
    which may include *data sub-specs* in the form of refdata_dependencies.yaml
    files from each/any of the notebook repos associated with the wrangler spec.
    """
    def __init__(self, logger: WranglerLogger, notebook_repo_paths: list[str], archive_dir: str = "."):
        self.logger = logger
        self.notebook_repo_paths = notebook_repo_paths
        self.archive_dir = "."
        self.data_specs = {}

    def iterate_over(self, description, func, *args):
        result_map = {}
        for repo_path in self.notebook_repo_paths:
            try:
                self.logger.debug(f"{description} {repo_path}...")
                result_map[repo_path] = func(repo_path, *args)
            except Exception as e:
                self.logger.exception(e, f"Failed {description.lower()} {repo_path}:")
                result_map[repo_path] = None
        return result_map

    def _load_spec(self, repo_path):
        return DataRepoSpec(self.logger, Path(repo_path), self.archive_dir)

    def load_refdata_specs(self) -> None:
        self.data_specs = self.iterate_over("Loading refdata spec", self._load_spec)

    def _validate_spec(self, repo_path: str, *args) -> None:
        if self.data_specs[repo_path] is not None:
            self.data_specs[repo_path].validate_spec(*args)
        else:
            self.logger.error(f"Cannot validate refdata spec {repo_path} that failed to load.")
    
    def validate_refdata_specs(self, *args):
        self.iterate_over("Validating refdata spec", self._validate_spec, *args)

    def _get_repo_spec_dict(self, repo_path) -> dict:
        return self.data_specs[repo_path].todict()

    def get_repo_spec_dict_map(self) -> dict[str, dict]:
        return self.iterate_over("Getting repo spec dict map", self._get_repo_spec_dict)

    def _download_repo_spec(self, repo_path, *args):
        return self.data_specs[repo_path].download_spec(*args)

    def download(self, force=False):
        return self.iterate_over(f"Downloading repo spec", self._download_repo_spec, force)


def main(argv):
    config.global_config = WranglerConfig()
    config.global_config.debug = True
    config.global_config.verbose = True
    log = WranglerLogger.from_config(config.global_config)
    dm = DataManager(log, argv[1:])
    dm.load_refdata_specs()
    dm.download()
    dm.validate_refdata_specs()

if __name__ == "__main__":
    main(sys.argv)
