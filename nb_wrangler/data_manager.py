"""Handles management of data specified in wrangler spec.

Similar to how package requirements are primarily specified by locating requirements.txt files
in the notebook directories of a notebook repo, the top level data spec is defined by a file
named `refdata_dependencies.yaml` which is stored at the top level of any notebook repository.
"""

import sys

# import os
# from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import copy
import re

# from typing import Optional


from . import utils

# from .utils import DataDownloadError
# from .constants import DATA_GET_TIMEOUT
# from .config import WranglerConfig
# from . import config
from .logger import WranglerLoggable, WranglerLogger
from . import config
from . import constants


"""
The initial implementation of a data spec for a single notebook repo was:
"""

"""
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
"""

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

'''

@dataclass
class SingleUrl:
    url: str
    archive_dir: str
    abstract_path: str  # where to unpack including
    resolved_path: str  # Where to unpack relative to overridden(?) env vars
    size: int = 0
    sha256: str = (
        "yyy"  # has to verify definitely not corrupted status,  very hard to spoof if known elsewhere, not a signature
    )

    def todict(self):
        return dict(self.__dict__)

    def validate_sha256(self) -> None:
        if not self.archive_filepath.exists():
            raise utils.DataIntegrityError(
                f"Archive file does not exist at expected location {str(self.archive_filepath)}."
            )
        new_sha256 = utils.sha256_file(self.resolved_path)
        if self.sha256 != new_sha256:
            raise utils.DataIntegrityError(
                f"Data for '{self.url}' may be corrupt: Recorded sha256 is '{self.sha256}' but computed from '{self.archive_filepath}' is '{new_sha256}'."
            )

    def validate_filesize(self) -> None:
        size = self.archive_filepath.stat().st_size
        if self.size != size:
            raise utils.DataIntegrityError(
                f"Data for '{self.url}' may be corrupt: Recorded file size is '{self.size}' but computed from '{self.archive_filepath}' is '{size}'."
            )

    def validate_resolved_exists(self) -> None:
        path = Path(self.resolved_path)
        if path.exists():
            raise utils.DataIntegrityError(
                f"Data for '{self.url}' may be corrupt: Unpacked directory '{self.resolved_path}' does not exist."
            )

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
        new_path = utils.robust_get(
            self.url, timeout=DATA_GET_TIMEOUT, cwd=str(self.archive_dir)
        )
        if self.archive_filepath != new_path:
            raise DataDownloadError(
                f"Failed to download data from '{self.url}' expected filepath '{self.archive_filepath}' got '{new_path}'."
            )
        self.size = self.archive_filepath.stat().st_size
        self.sha256 = utils.sha256_file(self.archive_filepath)
        return new_path


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
            self.url_map[url] = SingleUrl(
                url, self.archive_dir, self.abstract_path, self.resolved_path
            )

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


class DataRepoSpec(WranglerLoggable):
    """This class loads a single refdata_dependencies.yaml file including multiple
    named data sections each of which may have more than one URL which is represented
    by a DataSection instance.
    """

    def __init__(self, yaml_string: str, archive_dir: str):
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
                    archive_dir=archive_dir,
                )
            except Exception as e:
                self.logger.exception(e, f"Failed creating data section {name}.")

    @classmethod
    def from_string(cls, yaml_string: str, archive_dir: str = "."):
        return cls(yaml_string, archive_dir)

    @classmethod
    def from_file(cls, filepath, archive_dir: str = "."):
        with open(filepath) as stream:
            yaml_string = stream.read()
            return cls.from_string(yaml_string, archive_dir)

    def validate_spec(self):
        """Validate that the refdata_dependencies.yaml is well structured and with
        sound HEAD for urls.
        """
        for data_item in self.data_items.values():
            data_item.validate()

    def download_spec(self, *args):
        for data_item in self.data_items.values():
            data_item.download(*args)


class DataManager(WranglerLoggable):
    """This class manages all the data associated with a single *wrangler* spec,
    which may include *data sub-specs* in the form of refdata_dependencies.yaml
    files from each/any of the notebook repos associated with the wrangler spec.
    """

    def __init__(
        self,
        notebook_repo_paths: list[str],
        archive_dir: str = ".",
    ):
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
            self.logger.error(
                f"Cannot validate refdata spec {repo_path} that failed to load."
            )

    def validate_refdata_specs(self, *args):
        self.iterate_over("Validating refdata spec", self._validate_spec, *args)

    def _get_repo_spec_dict(self, repo_path) -> dict:
        return self.data_specs[repo_path].todict()

    def get_repo_spec_dict_map(self) -> dict[str, dict]:
        return self.iterate_over("Getting repo spec dict map", self._get_repo_spec_dict)

    def _download_repo_spec(self, repo_path, *args):
        return self.data_specs[repo_path].download_spec(*args)

    def download(self, force=False):
        return self.iterate_over(
            "Downloading repo spec", self._download_repo_spec, force
        )




def main(argv):
    config.global_config = WranglerConfig()
    config.global_config.debug = True
    config.global_config.verbose = True
    dm = DataManager(argv[1:])
    dm.load_refdata_specs()
    dm.download()
    dm.validate_refdata_specs()


if __name__ == "__main__":
    main(sys.argv)

'''


def is_valid_url(url: str):
    """Make sure `url` has a valid scheme like https:// and a valid net location."""
    logger = WranglerLogger()
    try:
        result = urlparse(str(url).strip())
        logger.info(f"Validating URL '{url}'.")
        return all([result.scheme, result.netloc])
    except Exception as e:
        logger.exception(e, f"Invalid URL '{url}'.")
        return False


def is_valid_env_name(name: str) -> bool:
    return isinstance(name, str) and re.match("^[A-Za-z0-9_]{1,64}$", name) is not None


def is_valid_env_value(value: str) -> bool:
    return isinstance(value, str) and re.match("^.{0,131072}$", value) is not None


def is_valid_abstract_path(path: str):
    if not isinstance(path, str):
        return False
    parts = Path(path).parts
    if parts[0].startswith("/"):  # no absolute paths
        return False
    dir_exp = r"[A-Za-z0_.][A-Za-z0-9_.]*"
    if not re.match(
        r"^[$]?" + dir_exp + r"$", parts[0]
    ) and not re.match(  # cover ${X} form
        r"^\$\{" + dir_exp + r"\}$", parts[0]
    ):  # only first part can start with $
        return False
    for part in parts[1:]:
        if not re.match(r"^" + dir_exp + "$", part):
            return False
        if part == "..":  # no 'escape' paths
            return False
    return True


class DataSection(WranglerLoggable):
    """Represents a single data item in the ref."""

    def __init__(
        self,
        version: str,
        environment_variable: str,
        install_path: str,
        data_path: str,
        data_url: list[str],
    ):
        super().__init__()
        self.version: str = version
        self.environment_variable: str = environment_variable
        self.install_path: str = install_path
        self.data_path: str = data_path
        self.data_url: list[str] = data_url

    def validate(self, refdata_path: str, section_name: str) -> bool:
        errors = False
        if not isinstance(self.version, (str, float)):
            errors = self.logger.error(
                f"Invalid type '{type(self.version)}' for version in refdata file '{refdata_path}' section '{section_name}'.  Should be 'str'."
            )
        else:
            self.version = str(self.version)  # unify floats as str
        if not is_valid_env_name(self.environment_variable):
            errors = self.logger.error(
                f"Invalid env var name '{self.environment_variable}' in refdata file '{refdata_path}' section '{section_name}'."
            )
        if not is_valid_abstract_path(self.install_path):
            errors = self.logger.error(
                f"Invalid data install path '{self.install_path}' for refdata file '{refdata_path}' section '{section_name}'."
            )
        for url in self.data_url:
            if not is_valid_url(url):
                errors = self.logger.error(
                    f"Found invalid data URL '{url}' in refdata file '{refdata_path}' section '{section_name}'."
                )
        return errors

    def todict(self):
        d = dict(self.__dict__)
        d.pop("logger", None)
        return d

    def __str__(self):
        return utils.yaml_dumps(self.__dict__)


class RefdataValidator(WranglerLoggable):

    def __init__(self):
        super().__init__()
        self.all_data = {}

    def load_data_sections(self, install_files: dict) -> dict[str, dict]:
        result = dict()
        for name, data_section in install_files.items():
            section = DataSection(**data_section)
            result[name] = section.todict()
        return result

    def load_refdata_spec(self, refdata_path: str) -> dict[str, dict]:
        result: dict[str, dict] = dict(install_files={}, other_variables={})
        rp = Path(refdata_path)
        if rp.exists():
            spec_dict = utils.get_yaml().load(rp.open())
            result["install_files"] = self.load_data_sections(
                spec_dict["install_files"]
            )
            result["other_variables"] = spec_dict.get("other_variables", {})
        else:
            raise FileNotFoundError(f"Refdata file {refdata_path} not found.")
        return result

    def load_refdata_specs(self, refdata_paths: list[str]) -> dict[str, dict]:
        self.all_data = {}
        for refdata_path in refdata_paths:
            self.all_data[str(refdata_path)] = self.load_refdata_spec(refdata_path)
        return copy.deepcopy(self.all_data)

    @classmethod
    def from_files(cls, refdata_paths: list[str]) -> "RefdataValidator":
        result = cls()
        result.load_refdata_specs(refdata_paths)
        return result

    @classmethod
    def from_notebook_repo_urls(
        cls, repo_dir: str, repo_urls: list[str]
    ) -> "RefdataValidator":
        files = []
        for url in repo_urls:
            url_name = Path(url).stem
            files.append(str(Path(repo_dir) / url_name / constants.DATA_SPEC_NAME))
        return cls.from_files(files)

    def __str__(self):
        return utils.yaml_dumps(self.all_data)

    def todict(self):
        result = copy.deepcopy(self.all_data)
        result.pop("logger", None)
        return result

    def validate_data_sections(self, refdata_path: str):
        self.logger.debug(
            f"Validating data sections for refdata file '{refdata_path}'."
        )
        errors = False
        for name, section_dict in self.all_data[refdata_path]["install_files"].items():
            if not isinstance(name, str):
                errors = self.logger.error(
                    f"Invalid data section name '{name}' in refdata file '{refdata_path}'."
                )
            if not isinstance(section_dict, dict):
                errors = self.logger.error(
                    f"Invalid data section value '{section_dict}' in refdata file '{refdata_path}'."
                )
            else:
                section = DataSection(**section_dict)
                errors = errors or section.validate(refdata_path, name)
        return errors

    def validate_install_files(self) -> bool:
        errors = False
        for refdata_path in self.all_data:
            if self.validate_data_sections(refdata_path):
                errors = self.logger.error(
                    f"Validation failed for data sections of refdata file '{refdata_path}'."
                )
        return errors

    def validate_env_dict(self, refdata_path: str, env_dict: dict[str, str]) -> bool:
        self.logger.debug(
            f"Validating environment variable names and values for refdata file '{refdata_path}'."
        )
        error = False
        for name, value in env_dict.items():
            if not is_valid_env_name(name):
                error = True
                self.logger.error(
                    f"Invalid environment name: '{name}' in refdata file '{refdata_path}'."
                )
            if not is_valid_env_value(value):
                error = True
                self.logger.error(
                    f"Invalid environment value: '{value}' in refdata file '{refdata_path}'."
                )
        return error

    def validate_env_dicts(self):
        self.logger.debug("Validating all environment variable names and values...")
        errors = False
        for refdata_path, env_dict in self.all_data.items():
            errors = errors or self.validate_env_dict(refdata_path, env_dict)
        return errors

    def check_conflicts(self, refdata_path_i: str, refdata_path_j: str) -> bool:
        """Between two specs, ensure they do not have conflicting environment variables."""
        self.logger.debug(
            f"Validating environment variable conflicts between refdata files '{refdata_path_i}' and '{refdata_path_j}'."
        )
        env_vars_i = self.all_data[refdata_path_i]["other_variables"]
        env_vars_j = self.all_data[refdata_path_j]["other_variables"]
        already_seen = set()
        errors = False
        for name_i, value_i in env_vars_i.items():
            for name_j, value_j in env_vars_j.items():
                if name_i != name_j or (name_j, name_i) in already_seen:
                    continue
                already_seen.add((name_i, name_j))
                if value_i != value_j:
                    errors = self.logger.error(
                        "Conflicting environment variable values for env var '{name_i}' in refdata specs '{refdata_path_i}' and '{refdata_path_j}'."
                    )
        return errors

    def validate_env_conflicts(self) -> bool:
        """Across all specs,  ensure no two specs define the same env var with different values."""
        self.logger.debug("Validating no conflicts between any two refdata specs..." "")
        already_seen = set()
        errors = False
        for refdata_path_i in self.all_data.keys():
            for refdata_path_j in self.all_data.keys():
                if (refdata_path_j, refdata_path_i) not in already_seen:
                    already_seen.add((refdata_path_i, refdata_path_j))
                    errors = errors or self.check_conflicts(
                        refdata_path_i, refdata_path_j
                    )
        return errors

    def validate_env_vars(self) -> bool:
        self.logger.info("Validating environment variables for all refdata specs...")
        return self.validate_env_conflicts() or self.validate_env_dicts()

    def validate(self) -> bool:
        return self.validate_install_files() and self.validate_env_vars()


def main(argv):
    config.set_args_config(config.WranglerConfig())
    config.args_config.debug = True
    config.args_config.verbose = True

    rdv = RefdataValidator()
    rdv.load_refdata_specs(argv[1:])
    print(rdv)
    rdv.validate()


if __name__ == "__main__":
    main(sys.argv)
