"""Handles management of refdata_dependencies.yaml data specs discovered
at the root of notebook repos that need supporting data.

Attempts to provide some input validation as well as the capability of
instantiating either from notebook directory repos or spec and metadata
values stored the wrangler spec during post-collection download and
compute steps.

This module is spec oriented, heavy lifting for data downloads and metadata
collection are performed in the pantry.py module and part of managing local
archives.
"""

import sys
import os
from pathlib import Path
from urllib.parse import urlparse
import re
from dataclasses import dataclass
from collections import defaultdict

from . import utils
from .logger import WranglerLoggable, WranglerLogger
from . import config
from . import constants


"""
The initial implementation of a data spec for a single notebook repo was:

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


def is_valid_url(url: str):
    """Make sure `url` has a valid scheme like https:// and a valid net location."""
    logger = WranglerLogger()
    try:
        result = urlparse(str(url).strip())
        logger.debug(f"Validating URL '{url}'.")
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
    """Represents a single data item in the ref. Attributes are all static
    values taken directly from a refdata_dependencies.yaml spec which are
    later further resolved into more concrete installed valuesw"""

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
        d["data_url"] = d["data_url"][:]  # copy of list
        d.pop("logger", None)
        return d

    def __str__(self):
        return utils.yaml_dumps(self.__dict__)

    @property
    def env_value(self):
        return os.path.join(self.install_path, self.data_path)


class RefdataSpec(WranglerLoggable):
    def __init__(self, install_files={}, other_variables={}):
        super().__init__()
        self.install_files = install_files
        self.other_variables = other_variables

    def todict(self) -> dict[str, dict]:
        return dict(
            install_files={
                name: section.todict() for (name, section) in self.install_files.items()
            },
            other_variables=dict(self.other_variables),
        )

    def __str__(self):
        return utils.yaml_dumps(self.todict())

    def validate_install_files(
        self, refdata_path: str, install_files: dict[str, dict]
    ) -> bool:
        self.logger.debug(
            f"Validating data sections for refdata file '{refdata_path}'."
        )
        errors = False
        if not isinstance(install_files, dict):
            return self.logger.error(
                "install_files is not a dict in refdata file '{refdata_path}'."
            )
        for name, section_dict in install_files.items():
            if not isinstance(name, str):
                errors = self.logger.error(
                    f"Invalid data section name '{name}' in refdata file '{refdata_path}'."
                )
            if not isinstance(section_dict, dict):
                errors = self.logger.error(
                    f"Invalid data section value '{section_dict}' in refdata file '{refdata_path}'."
                )
            else:
                self.install_files[name] = DataSection(**section_dict)
                errors = errors or self.install_files[name].validate(refdata_path, name)
        return errors

    def validate_other_variables(
        self, refdata_path: str, other_variables: dict[str, str]
    ) -> bool:
        self.logger.debug(
            f"Validating environment variable names and values for refdata file '{refdata_path}'."
        )
        error = False
        if not isinstance(other_variables, dict):
            return self.logger.error(
                "fInvalid other_variables type for refdata file '{refdata_path}'."
            )
        for name, value in other_variables.items():
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
            self.other_variables[name] = value
        return error

    @classmethod
    def from_dict(cls, refdata_path: str, spec_dict: dict) -> "RefdataSpec":
        self = cls()
        if self.validate_install_files(
            refdata_path, spec_dict["install_files"]
        ) or self.validate_other_variables(refdata_path, spec_dict["other_variables"]):
            raise ValueError("Failed to validate spec dictionary.")
        return self

    @classmethod
    def from_yaml(cls, refdata_path: str, yaml_str: str) -> "RefdataSpec":
        spec_dict = utils.get_yaml().load(yaml_str)
        return cls.from_dict(refdata_path, spec_dict)

    @classmethod
    def from_file(cls, refdata_path: str) -> "RefdataSpec":
        rp = Path(refdata_path)
        if rp.exists():
            with rp.open("r") as stream:
                return cls.from_yaml(refdata_path, stream.read())
        else:
            raise FileNotFoundError(f"Refdata file {refdata_path} not found.")

    def get_data_urls(self) -> list[tuple[str, str]]:
        urls = []
        for name, section in self.install_files.items():
            for url in section.data_url:
                urls.append((name, url))
        return urls

    def get_spec_vars(self) -> dict[str, str]:
        result: defaultdict = defaultdict(dict)
        for section_name, section in self.install_files.items():
            result[section_name][section.environment_variable] = section.env_value
        return dict(result)


@dataclass
class DataSectionUrl:
    """This is a single URL from a 'flattened' version of all specs."""

    refdata_path: str
    section_name: str
    section: DataSection
    url: str

    @property
    def repo_name(self) -> str:
        return Path(self.repo_path).name

    @property
    def repo_path(self) -> str:
        return str(Path(self.refdata_path).parent)


class RefdataValidator(WranglerLoggable):

    def __init__(self, refdata_paths: list[str]):
        super().__init__()
        self.refdata_paths = refdata_paths
        self.all_data: dict[str, "RefdataSpec"] = {}

    # ..........................................................................

    @classmethod
    def from_files(cls, refdata_paths: list[str]) -> "RefdataValidator":
        self = cls(refdata_paths)
        for refdata_path in refdata_paths:
            self.all_data[str(refdata_path)] = RefdataSpec.from_file(refdata_path)
        self.validate_env_conflicts()
        return self

    @classmethod
    def from_dict(cls, refdata_map: dict[str, dict]) -> "RefdataValidator":
        self = cls(list(refdata_map.keys()))
        for refdata_path, spec_dict in refdata_map.items():
            self.all_data[str(refdata_path)] = RefdataSpec.from_dict(
                refdata_path, spec_dict
            )
        self.validate_env_conflicts()
        return self

    @classmethod
    def from_repo_urls(cls, repo_dir: str, repo_urls: list[str]) -> "RefdataValidator":
        """Based on specs discovered at repo URLs, construct a RefdataValidator."""
        return cls.from_files(
            [
                str(Path(repo_dir) / Path(url).stem / constants.DATA_SPEC_NAME)
                for url in repo_urls
            ]
        )

    def todict(self):
        return {name: refdata.todict() for name, refdata in self.all_data.items()}

    def __str__(self):
        return utils.yaml_dumps(self.todict())

    def check_conflicts(self, refdata_path_i: str, refdata_path_j: str) -> bool:
        """Between two specs, ensure they do not have conflicting environment variables."""
        self.logger.debug(
            f"Validating environment variable conflicts between refdata files '{refdata_path_i}' and '{refdata_path_j}'."
        )
        env_vars_i = self.all_data[refdata_path_i].other_variables
        env_vars_j = self.all_data[refdata_path_j].other_variables
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

    def get_data_section_urls(self) -> list[DataSectionUrl]:
        return [
            DataSectionUrl(refdata_path, section_name, section, url)
            for refdata_path, refdata_spec in self.all_data.items()
            for section_name, section in refdata_spec.install_files.items()
            for url in section.data_url
        ]

    def get_data_urls(self) -> list[tuple[str, str, str]]:
        return [
            (dsu.repo_name, dsu.section_name, dsu.url)
            for dsu in self.get_data_section_urls()
        ]

    def get_data_section_env_vars(self) -> dict[str, str]:
        return {
            dsu.section.environment_variable : dsu.section.env_value
            for dsu in self.get_data_section_urls()
        }
    
    def get_data_pantry_env_vars(self, pantry_path: Path) -> dict[str, str]:
        return {
            dsu.section.environment_variable : str(pantry_path / dsu.section.data_path)
            for dsu in self.get_data_section_urls()
        }

    def get_data_other_env_vars(self) -> dict[str, str]:
        result = dict()
        for refdata_path, refdata in self.all_data.items():
            result.update(refdata.other_variables)
        return dict(result)


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
