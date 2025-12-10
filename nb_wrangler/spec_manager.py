import os.path
import re
from typing import Any, Optional
from pathlib import Path
import copy

from . import utils
from .logger import WranglerLoggable
from .constants import DEFAULT_ARCHIVE_FORMAT, VALID_ARCHIVE_FORMATS


class SpecManager(WranglerLoggable):
    """Manages specification loading, validation, access, and persistence."""

    def __init__(self):
        super().__init__()
        self._spec = {}
        self._is_validated = False
        self._source_file = Path("")
        self._initial_spec_sha256 = None

    # ---------------------------- Property-based read/write access to spec data -------------------
    @property
    def header(self):
        return self._spec["image_spec_header"]

    @property
    def deployment_name(self) -> str:
        return self.header["deployment_name"]

    @property
    def kernel_name(self) -> str:  # also environment_name / env_name
        return self.header["kernel_name"]

    @property
    def display_name(self) -> str:  # readable name in lab menu
        return self.header.get("display_name", self.kernel_name)

    @property
    def image_name(self) -> str:
        return self.header["image_name"]

    @property
    def spec_id(self) -> str | None:
        return self.sha256[:6] if self.sha256 is not None else None

    @property
    def description(self) -> str:
        return self.header["description"]

    @property
    def python_version(self) -> str:
        return self.header["python_version"]

    @property
    def repositories(self) -> dict[str, Any]:
        return self._spec.get("repositories", {})

    @property
    def notebook_selections(self) -> dict[str, Any]:
        return self._spec.get("selected_notebooks", {})

    @property
    def system(self) -> dict[str, str]:
        return self._spec["system"]

    @property
    def extra_mamba_packages(self) -> list[str]:
        return self._spec.get("extra_mamba_packages", [])

    @property
    def extra_pip_packages(self) -> list[str]:
        return self._spec.get("extra_pip_packages", [])

    @property
    def spi_url(self):
        return self.system.get("spi_url", None)

    @property
    def spi_fork_remote(self):
        return self.system.get("spi_fork_remote", None)

    @property
    def moniker(self) -> str:
        """Get a filesystem-safe version of the image name."""
        return self.image_name.replace(" ", "-").lower() + "-" + self.kernel_name

    @property
    def spec_file(self) -> Path:
        return self._source_file

    @property
    def shelf_name(self) -> str:
        return self.moniker  # + "-" + self.spec_id

    @property
    def archive_format(self) -> str:
        """Get the default archival format for the environment's binaries."""
        # Return default if not specified
        arch_format = self.system.get("archive_format")
        if arch_format:
            self.logger.debug("Using spec'ed archive format", arch_format)
        else:
            arch_format = DEFAULT_ARCHIVE_FORMAT
            self.logger.debug(
                "No archive format in spec, assuming default format", arch_format
            )
        return arch_format

    # ----------------- functional access to output section ----------------

    def get_output_data(self, key: str, default: Any = None) -> Any:
        """Get data from the output section of the spec."""
        return self._spec.get("out", {}).get(key, default)

    def get_outputs(self, *output_names) -> list[Any] | Any:
        """Get the named fields from the spec output section and
        return a tuple in order of `output_names`.
        """
        self.logger.debug("Retrieving prior outputs from spec:", output_names)
        if "out" not in self._spec:
            raise RuntimeError(
                f"No output section found.   Output values for {output_names} must already be in the spec."
            )
        output_values = []
        for output_name in output_names:
            output_value = self.get_output_data(output_name)
            if output_value is not None:
                output_values.append(output_value)
            else:
                raise RuntimeError(
                    f"Missing output field '{output_name}' needs to be computed earlier or already in the spec."
                )
        if len(output_values) > 1:
            return output_values
        elif len(output_values) == 1:
            return output_values[0]
        else:
            raise RuntimeError(f"No output values were found for '{output_names}'.")

    def outputs_exist(self, *output_names: str) -> bool:
        """Check if all specified outputs exist in the spec already."""
        return "out" in self._spec and all(
            name in self._spec["out"] for name in output_names
        )

    def files_exist(self, *filepaths: str | Path) -> bool:
        """Check if all specified files exist in the filesystem."""
        return all(Path(filepath).exists() for filepath in filepaths)

    # Raw read/write access for backward compatibility or special cases
    def to_dict(self) -> dict[str, Any]:
        """Return the raw spec dictionary."""
        return copy.deepcopy(self._spec)

    def to_string(self):
        return utils.yaml_dumps(self._spec)

    # ----------------------------- load, save, outputs  ---------------------------

    @classmethod
    def load_and_validate(
        cls,
        spec_file: str,
    ) -> Optional["SpecManager"]:
        """Factory method to load and validate a spec file."""
        manager = cls()
        if manager.load_spec(spec_file) and manager.validate():
            # stash the unchecked initial checksum to check later
            # to ensure readonly workflows do not change it.
            # if the unchecked value starts out bad, that should
            # be detected or ignored before it is used.
            manager._initial_spec_sha256 = manager.sha256
            return manager
        else:
            manager.logger.error("Failed to load and validate", spec_file)
            return None

    def load_spec(self, spec_file: str | Path) -> bool:
        """Load YAML specification file."""
        try:
            self._source_file = Path(spec_file)
            with self._source_file.open("r") as f:
                self._spec = utils.get_yaml().load(f)
            self.logger.debug(f"Loaded spec from {str(spec_file)}.")
            return True
        except Exception as e:
            return self.logger.exception(e, f"Failed to load YAML spec: {e}")

    def set_output_data(self, key: str, value: Any) -> None:
        """set data in the output section."""
        if "out" not in self._spec:
            self._spec["out"] = dict()
        self._spec["out"][key] = value
        self.logger.debug(f"setting output data: {key} -> {value}")

    # -------------------------------- saving & resetting spec -------------------------------

    def output_spec(self, output_dir: Path | str) -> Path:
        """The output path for the spec file."""
        if self._source_file is None:
            raise RuntimeError("No source file loaded")
        return Path(output_dir) / self._source_file.name

    def save_spec(self, output_dir: Path | str, add_sha256: bool = False) -> bool:
        """Keeping the original name,  save the spec at a new location, optionally
        updating the sha256 sum.
        """
        output_filepath = self.output_spec(output_dir)
        return self.save_spec_as(output_filepath, add_sha256=add_sha256)

    def save_spec_as(
        self, output_filepath: Path | str, add_sha256: bool = False
    ) -> bool:
        """Save the current YAML spec to a file."""
        self.logger.info(f"Saving spec file to {output_filepath}.")
        try:
            output_path = Path(output_filepath)
            if add_sha256:
                hash = self.add_sha256()
                self.logger.debug(f"Setting spec_sha256 to {hash}.")
            else:
                self.system.pop("spec_sha256", None)
                self.logger.debug(
                    "Not updating spec_sha256 sum; Removing potentially outdated sum."
                )
            if output_path.exists():
                output_path.unlink()  # Remove existing file if it
            with output_path.open("w+") as f:
                f.write(self.to_string())
            self.logger.debug(f"Spec file saved to {output_filepath}.")
            return True
        except Exception as e:
            return self.logger.exception(
                e, f"Error saving YAML spec file to {output_filepath}: {e}"
            )

    def revise_and_save(
        self,
        output_dir: Path | str,
        add_sha256: bool = False,
        **additional_outputs,
    ) -> bool:
        """Update spec with computed outputs and save to file."""
        try:
            self.logger.info(f"Revising spec file {self._source_file}.")
            for key, value in additional_outputs.items():
                self.set_output_data(key, value)
            return self.save_spec(output_dir, add_sha256=add_sha256)
        except Exception as e:
            return self.logger.exception(e, f"Error revising spec file: {e}")

    def reset_spec(self) -> bool:
        """Delete the output field of the spec and make sure the source file reflects it."""
        self.logger.debug("Resetting spec file.")
        out = self._spec.pop("out", None)
        data = out.pop("data", None)
        if data:
            self._spec["out"] = dict(data=data)
        self.system.pop("spec_sha256", None)
        if not self.validate():
            return self.logger.error("Spec did not validate follwing reset.")
        if not self.save_spec_as(self._source_file):
            return self.logger.error("Spec save to", self._source_file, "failed...")
        return True

    def data_reset_spec(self) -> bool:
        """Delete only the 'data' output field of the spec and make sure the source file reflects it."""
        self.logger.debug("Resetting data section spec file.")
        self._spec["out"].pop("data", None)
        self.system.pop("spec_sha256", None)
        if not self.validate():
            return self.logger.error("Spec did not validate follwing data reset.")
        if not self.save_spec_as(self._source_file):
            return self.logger.error("Spec save to", self._source_file, "failed...")
        return True

    # ---------------------------- hashes, crypto ----------------------------------

    @property
    def sha256(self) -> str | None:
        hash = self.system.get("spec_sha256", None)
        if hash is None:
            self.logger.debug("Spec has no spec_sha256 hash for verifying integrity.")
            return None
        if len(hash) != 64 or not re.match("[a-z0-9]{64}", hash):
            self.logger.warning(f"System spec_sha256 hash '{hash}' is malformed.")
        return hash

    def add_sha256(self) -> str:
        self.system["spec_sha256"] = ""
        self.system["spec_sha256"] = utils.sha256_str(self.to_string())
        return self.system["spec_sha256"]

    def validate_sha256(self) -> bool:
        """Validate the sha256 hash of the spec which proves integrity unless we've been hacked."""
        expected_hash = self.system.get("spec_sha256")
        if not expected_hash:
            return self.logger.error("Spec has no spec_sha256 hash to validate.")
        else:
            self.logger.debug(f"Validating spec_sha256 checksum {expected_hash}.")
            actual_hash = self.add_sha256()
            if expected_hash == actual_hash:
                self.logger.debug(f"Spec-sha256 {expected_hash} validated.")
                return True
            else:
                return self.logger.error(
                    f"Spec-sha256 {expected_hash} did not match actual hash {actual_hash}."
                )

    # ---------------------------- validation ----------------------------------

    ALLOWED_KEYWORDS = {
        "image_spec_header": [
            "image_name",
            "description",
            "valid_on",
            "expires_on",
            "python_version",
            "deployment_name",
            "kernel_name",
            "display_name",
        ],
        "repositories": ["url", "branch", "hash"],
        "extra_mamba_packages": [],
        "extra_pip_packages": [],
        "selected_notebooks": [
            "repo",
            "root_directory",
            "include_subdirs",
            "exclude_subdirs",
            "tests",
        ],
        "out": [
            "repositories",
            "test_notebooks",
            "spi_packages",
            "mamba_spec",
            "pip_requirement_files",
            "pip_map",
            "package_versions",
            "data",
        ],
        "system": [
            "spec_version",
            "spec_sha256",
            "archive_format",
            "spi_url",
            "spi_fork_remote",
        ],
    }

    REQUIRED_KEYWORDS = {
        "image_spec_header": [
            "image_name",
            "deployment_name",
            "kernel_name",
            "python_version",
            "valid_on",
            "expires_on",
        ],
        "repositories": [],
        "system": [
            "spec_version",
        ],
    }

    def validate(self) -> bool:
        """Perform comprehensive validation on the loaded specification."""
        self._is_validated = False
        if not self._spec:
            return self.logger.error("Spec did not loaded / defined, cannot validate.")
        validated = (
            self._validate_top_level_structure()
            and self._validate_header_section()
            and self._validate_repositories_section()
            and self._validate_notebook_selections_section()
            and self._validate_system()
        )
        if not validated:
            return self.logger.error("Spec validation failed.")
        self._is_validated = True
        self.logger.debug("Spec validated.")
        return True

    def _ensure_validated(self) -> None:
        """Ensure the spec has been validated before access."""
        if not self._is_validated:
            raise RuntimeError("Spec must be validated before accessing data")

    # Validation methods
    def _validate_top_level_structure(self) -> bool:
        """Validate top-level structure."""
        no_errors = True
        for field in self.REQUIRED_KEYWORDS:
            if field not in self._spec:
                no_errors = self.logger.error(f"Missing required field: {field}")

        for key in self._spec:
            if key not in self.ALLOWED_KEYWORDS:
                no_errors = self.logger.error(f"Unknown top-level keyword: {key}")

        return no_errors

    def _validate_header_section(self) -> bool:
        """Validate image_spec_header section."""
        no_errors = True
        for key in self.header:
            if key not in self.ALLOWED_KEYWORDS["image_spec_header"]:
                no_errors = self.logger.error(
                    f"Unknown keyword in image_spec_header: {key}"
                )
        for field in self.REQUIRED_KEYWORDS["image_spec_header"]:
            if field not in self.header:
                no_errors = self.logger.error(
                    f"Missing required field in image_spec_header: {field}"
                )
        return no_errors

    def _validate_repositories_section(self) -> bool:
        """Validate repositories section."""
        no_errors = True
        for name, repo in self.repositories.items():
            for key in repo:
                if key not in self.ALLOWED_KEYWORDS["repositories"]:
                    no_errors = self.logger.error(
                        f"Unknown keyword '{key}' in repository '{name}'."
                    )
            if "url" not in repo:
                no_errors = self.logger.error(
                    f"Missing required 'url' field in repository '{name}'."
                )
        return no_errors

    def _validate_notebook_selections_section(self) -> bool:
        """Validate selected_notebooks section."""
        no_errors = True
        for name, selection in self.notebook_selections.items():
            for key in selection:
                if key not in self.ALLOWED_KEYWORDS["selected_notebooks"]:
                    no_errors = self.logger.error(
                        f"Unknown keyword '{key}' in notebook selection '{name}'."
                    )
            if "repo" not in selection:
                no_errors = self.logger.error(
                    f"Missing required 'repo' field in notebook selection '{name}'."
                )
            elif selection["repo"] not in self.repositories:
                no_errors = self.logger.error(
                    f"Unknown repo '{selection['repo']}' in notebook selection '{name}'."
                )
            if "include_subdirs" not in selection:
                no_errors = self.logger.error(
                    f"Missing required 'include_subdirs' field in notebook selection '{name}'."
                )
        return no_errors

    def _validate_system(self) -> bool:
        no_errors = True
        if "spec_version" not in self.system:
            no_errors = self.logger.error(
                "Required field 'spec_version' of section 'system' is missing."
            )
        else:
            try:
                version = float(self.system["spec_version"])
                if version < 2.0:
                    self.logger.warning(
                        f"Spec version {version} is deprecated. Consider updating to 2.0."
                    )
            except (ValueError, TypeError):
                no_errors = self.logger.error("spec_version must be a float or number.")

        if self.archive_format not in VALID_ARCHIVE_FORMATS:
            self.logger.warning(
                f"Invalid .system.archive_format '{self.archive_format}'. Possibly unsupported if not one of: {VALID_ARCHIVE_FORMATS}"
            )
        for key in self.system:
            if key not in self.ALLOWED_KEYWORDS["system"]:
                no_errors = self.logger.error(
                    f"Undefined keyword '{key}' in section 'system'."
                )
        return no_errors

    # -------------------------------- notebook and repository collection --------------------------------------

    def get_repository_urls(self) -> list[str]:
        """Get all unique repository URLs from the spec."""
        self._ensure_validated()
        return [repo["url"] for repo in self.repositories.values()]

    def get_repository_branches(self) -> dict[str, str | None]:
        """Get repository URLs mapped to their branches from the spec."""
        self._ensure_validated()
        return {
            repo["url"]: repo.get("branch", "main")
            for repo in self.repositories.values()
        }

    def get_repository_hashes(self) -> dict[str, str | None]:
        """Get repository URLs mapped to their hashes from the spec."""
        self._ensure_validated()
        output_repos = self.get_output_data("repositories", {})
        return {
            repo_info.get("url"): repo_info.get("hash")
            for repo_info in output_repos.values()
            if repo_info
        }

    def collect_notebook_paths(self, repos_dir: Path) -> dict[str, str]:
        """Collect paths to all notebooks specified by the spec."""
        self._ensure_validated()
        notebook_paths: dict[str, str] = {}
        for name, selection in self.notebook_selections.items():
            repo_name = selection["repo"]
            if repo_name not in self.repositories:
                raise RuntimeError(
                    f"Unknown repository '{repo_name}' in selection block '{name}'"
                )
            repo_url = self.repositories[repo_name]["url"]
            clone_dir = self._get_repo_dir(repos_dir, repo_url)
            if not clone_dir.exists():
                self.logger.error(
                    f"Repository '{repo_name}' not set up at: {clone_dir}"
                )
                continue
            root_dir = selection.get("root_directory", "")
            found_notebooks = self._process_directory_entry(
                selection, clone_dir, root_dir
            )

            for notebook_path in found_notebooks:
                if notebook_path in notebook_paths:
                    self.logger.warning(
                        f"Notebook {notebook_path} included in multiple selections. Using first one found: '{notebook_paths[notebook_path]}'."
                    )
                else:
                    notebook_paths[notebook_path] = name

        self.logger.info(
            f"Found {len(notebook_paths)} notebooks in all notebook repositories."
        )
        return dict(sorted(notebook_paths.items()))

    def _get_repo_dir(self, repos_dir: Path, repo_url: str) -> Path:
        """Get the path to the repository directory."""
        basename = os.path.basename(repo_url).replace(".git", "")
        return repos_dir / basename

    def _process_directory_entry(
        self, entry: dict, repo_dir: Path, root_directory: str
    ) -> set[str]:
        """Process a directory entry from the spec file."""
        base_path = repo_dir
        if root_directory:
            base_path = base_path / root_directory

        possible_notebooks = [str(path) for path in base_path.glob("**/*.ipynb")]

        include_subdirs = list(entry.get("include_subdirs", [r"."]))
        included_notebooks = self._matching_files(
            "Including", possible_notebooks, include_subdirs
        )

        exclude_subdirs = list(entry.get("exclude_subdirs", []))
        exclude_subdirs.append(r"(^|/)\.ipynb_checkpoints(/|/.*-checkpoint\.ipynb$)")
        excluded_notebooks = self._matching_files(
            "Excluding", possible_notebooks, exclude_subdirs
        )

        remaining_notebooks = included_notebooks - excluded_notebooks
        self.logger.info(
            f"Selected {len(remaining_notebooks)} notebooks under {base_path} for selection block."
        )

        return remaining_notebooks

    def _matching_files(
        self, verb: str, possible_notebooks: list[str], regexes: list[str]
    ) -> set[str]:
        self.logger.debug(
            f"{verb} notebooks {list(possible_notebooks)} against regexes {regexes}"
        )
        notebooks = set()
        for nb_path in possible_notebooks:
            if not Path(nb_path).is_file():
                self.logger.debug(f"Skipping {verb} non-file: {nb_path}")
                continue
            for regex in regexes:
                if re.search(regex, str(nb_path)):
                    self.logger.debug(
                        f"{verb} notebook {nb_path} based on regex: '{regex}'"
                    )
                    notebooks.add(str(nb_path))
                    break
        return notebooks
