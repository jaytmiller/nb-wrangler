"""Spec validation logic extracted from SpecManager."""

from .logger import WranglerLoggable
from .constants import WRANGLER_SPEC_VERSION, VALID_ARCHIVE_FORMATS


class SpecValidator(WranglerLoggable):
    """Handles comprehensive validation of the wrangler specification."""

    def __init__(self, spec_manager):
        super().__init__()
        self.sm = spec_manager

    def validate(self) -> bool:
        """Perform comprehensive validation on the loaded specification."""
        if not self.sm._spec:
            return self.logger.error("Spec did not loaded / defined, cannot validate.")

        validated = (
            self._validate_top_level_structure()
            and self._validate_environment_spec()
            and self._validate_repositories_section()
            and self._validate_refdata_dependencies_section()
            and self._validate_notebook_selections_section()
            and self._validate_system()
            and self._validate_spi_section()
            and self._validate_nb_wrangler_section()
        )
        return validated

    def _validate_top_level_structure(self) -> bool:
        """Validate top-level structure."""
        no_errors = True
        for field in self.sm.REQUIRED_KEYWORDS:
            if field not in self.sm._spec:
                no_errors = self.logger.error(f"Missing required field: {field}")

        for key in self.sm._spec:
            if key not in self.sm.ALLOWED_KEYWORDS:
                # The concatenated mamba spec can add top-level keys like 'name', 'channels', etc.
                # We allow these only if an inline spec is detected.
                if self.sm.inline_mamba_spec is None:
                    no_errors = self.logger.error(f"Unknown top-level keyword: {key}")

        return no_errors

    def _validate_environment_spec(self) -> bool:
        """
        Validates the environment definition, enforcing one of four mutually exclusive methods.
        """
        no_errors = True

        # Check which environment definition method is used
        has_python_version = "python_version" in self.sm.header
        has_inline_mamba_spec = self.sm.inline_mamba_spec is not None
        has_environment_spec = self.sm.environment_spec is not None

        # Count defined methods
        methods_defined = sum(
            [has_python_version, has_inline_mamba_spec, has_environment_spec]
        )

        # Validate exactly one method is used
        if methods_defined == 0:
            return self.logger.error(
                "No environment definition found. Specify `python_version`, an inline mamba spec, or an external `environment_spec`."
            )
        if methods_defined > 1:
            return self.logger.error(
                "Multiple environment definitions found. `python_version`, inline mamba spec, and `environment_spec` are mutually exclusive."
            )

        # Validate the specific method used
        if has_python_version:
            no_errors = self._validate_simple_definition() and no_errors
        elif has_inline_mamba_spec:
            no_errors = self._validate_inline_spec() and no_errors
        elif has_environment_spec:
            no_errors = self._validate_external_spec() and no_errors

        # Validate header fields
        no_errors = (
            self._validate_header_fields(
                has_python_version, has_inline_mamba_spec, has_environment_spec
            )
            and no_errors
        )

        return no_errors

    def _validate_simple_definition(self) -> bool:
        """Validate simple definition (python_version in header)."""
        no_errors = True
        if "kernel_name" not in self.sm.header:
            no_errors = (
                self.logger.error(
                    "Missing `kernel_name` in `image_spec_header` for simple definition mode."
                )
                and no_errors
            )
        if "display_name" not in self.sm.header:
            self.logger.warning(
                "Missing `display_name` in `image_spec_header`. It will default to `kernel_name`."
            )
        return no_errors

    def _validate_inline_spec(self) -> bool:
        """Validate inline mamba spec."""
        no_errors = True
        if "python_version" in self.sm.header:
            no_errors = (
                self.logger.error(
                    "`python_version` must not be in the header when using an inline spec."
                )
                and no_errors
            )
        if "kernel_name" in self.sm.header:
            no_errors = (
                self.logger.error(
                    "`kernel_name` must not be in the header when using an inline spec."
                )
                and no_errors
            )
        if (
            not isinstance(self.sm.inline_mamba_spec, dict)
            or "name" not in self.sm.inline_mamba_spec
        ):
            no_errors = (
                self.logger.error(
                    "The inline mamba spec (second YAML document) must be a dictionary and have a `name` field."
                )
                and no_errors
            )
        return no_errors

    def _validate_external_spec(self) -> bool:
        """Validate external environment spec."""
        no_errors = True
        if "python_version" in self.sm.header:
            no_errors = (
                self.logger.error(
                    "`python_version` must not be in the header when using an external spec."
                )
                and no_errors
            )
        if "kernel_name" in self.sm.header:
            no_errors = (
                self.logger.error(
                    "`kernel_name` must not be in the header when using an external spec."
                )
                and no_errors
            )
        if not isinstance(self.sm.environment_spec, dict):
            no_errors = (
                self.logger.error("`environment_spec` must be a dictionary.")
                and no_errors
            )
        else:
            has_uri = "uri" in self.sm.environment_spec
            has_repo = "repo" in self.sm.environment_spec
            has_path = "path" in self.sm.environment_spec

            if not (has_uri or (has_repo and has_path)):
                no_errors = (
                    self.logger.error(
                        "`environment_spec` must contain either a `uri` key or both `repo` and `path` keys."
                    )
                    and no_errors
                )
            if has_uri and (has_repo or has_path):
                no_errors = (
                    self.logger.error(
                        "In `environment_spec`, `uri` cannot be mixed with `repo` or `path`."
                    )
                    and no_errors
                )
            if (
                has_repo
                and self.sm.environment_spec["repo"] not in self.sm.repositories
            ):
                no_errors = (
                    self.logger.error(
                        f"Unknown repository '{self.sm.environment_spec['repo']}' referenced in `environment_spec`."
                    )
                    and no_errors
                )
        return no_errors

    def _validate_header_fields(
        self, has_python_version, has_inline_mamba_spec, has_environment_spec
    ) -> bool:
        """Validate header fields based on which environment method is used."""
        no_errors = True
        for field in self.sm.REQUIRED_KEYWORDS["image_spec_header"]:
            # Skip validation for fields that are optional when using other methods
            if field == "kernel_name" and (
                has_inline_mamba_spec or has_environment_spec
            ):
                continue
            if field == "python_version" and (
                has_inline_mamba_spec or has_environment_spec
            ):
                continue

            if field not in self.sm.header:
                no_errors = (
                    self.logger.error(
                        f"Missing required field in image_spec_header: {field}"
                    )
                    and no_errors
                )

        for key in self.sm.header:
            if key not in self.sm.ALLOWED_KEYWORDS["image_spec_header"]:
                no_errors = (
                    self.logger.error(f"Unknown keyword in image_spec_header: {key}")
                    and no_errors
                )
        return no_errors

    def _validate_repositories_section(self) -> bool:
        """Validate repositories section."""
        no_errors = True
        if not self.sm.repositories:
            self.logger.debug("No repositories specified.")
        for name, repo in self.sm.repositories.items():
            for key in repo:
                if key not in self.sm.ALLOWED_KEYWORDS["repositories"]:
                    no_errors = self.logger.error(
                        f"Unknown keyword '{key}' in repository '{name}'."
                    )
            if "url" not in repo:
                no_errors = self.logger.error(
                    f"Missing required 'url' field in repository '{name}'."
                )
        return no_errors

    def _validate_refdata_dependencies_section(self) -> bool:
        """Validate refdata_dependencies section."""
        if "refdata_dependencies" not in self.sm._spec:
            return True

        from .data_manager import RefdataSpec

        try:
            RefdataSpec.from_dict(
                "wrangler_spec", self.sm._spec["refdata_dependencies"]
            )
            return True
        except ValueError as e:
            return self.logger.error(f"Invalid 'refdata_dependencies' in spec: {e}")

    def _validate_notebook_selections_section(self) -> bool:
        """Validate selected_notebooks section."""
        no_errors = True
        if not self.sm.notebook_selections:
            self.logger.debug("selected_notebooks is not specified.")
        for name, selection in self.sm.notebook_selections.items():
            for key in selection:
                if key not in self.sm.ALLOWED_KEYWORDS["selected_notebooks"]:
                    no_errors = self.logger.error(
                        f"Unknown keyword '{key}' in notebook selection '{name}'."
                    )
            if "repo" not in selection:
                no_errors = self.logger.error(
                    f"Missing required 'repo' field in notebook selection '{name}'."
                )
            elif selection["repo"] not in self.sm.repositories:
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
        if "spec_version" not in self.sm.system:
            no_errors = self.logger.error(
                "Required field 'spec_version' of section 'system' is missing."
            )
        else:
            try:
                version = float(self.sm.system["spec_version"])
                if version < int(WRANGLER_SPEC_VERSION):
                    self.logger.warning(
                        f"Spec version {version} is deprecated. Consider updating to {WRANGLER_SPEC_VERSION}."
                    )
            except (ValueError, TypeError):
                no_errors = self.logger.error("spec_version must be a float or number.")

        if "date_updated" not in self.sm.system:
            self.logger.debug(
                "Field 'date_updated' is missing from section 'system'. It will be added automatically on the next spec update."
            )

        if self.sm.archive_format not in VALID_ARCHIVE_FORMATS:
            self.logger.warning(
                f"Invalid .system.archive_format '{self.sm.archive_format}'. Possibly unsupported if not one of: {VALID_ARCHIVE_FORMATS}"
            )
        for key in self.sm.system:
            if key not in self.sm.ALLOWED_KEYWORDS["system"]:
                no_errors = self.logger.error(
                    f"Undefined keyword '{key}' in section 'system'."
                )
        return no_errors

    def _validate_spi_section(self) -> bool:
        """Validate spi section."""
        no_errors = True
        if "spi" not in self.sm._spec["system"]:
            return self.logger.error("Missing required section: spi")

        spi = self.sm._spec["system"]["spi"]
        for key in spi:
            if key not in self.sm.ALLOWED_KEYWORDS["system"]["spi"]:
                no_errors = self.logger.error(
                    f"Unknown keyword '{key}' in spi section."
                )
        for field in self.sm.REQUIRED_KEYWORDS["system"]["spi"]:
            if field not in spi:
                no_errors = self.logger.error(
                    f"Missing required field in spi section: {field}"
                )
        return no_errors

    def _validate_nb_wrangler_section(self) -> bool:
        """Validate nb-wrangler section."""
        no_errors = True
        if "nb-wrangler" not in self.sm._spec["system"]:
            return True

        nbw = self.sm._spec["system"]["nb-wrangler"]
        for key in nbw:
            if key not in self.sm.ALLOWED_KEYWORDS["system"]["nb-wrangler"]:
                no_errors = self.logger.error(
                    f"Unknown keyword '{key}' in nb-wrangler section."
                )
        for field in self.sm.REQUIRED_KEYWORDS["system"]["nb-wrangler"]:
            if field not in nbw:
                no_errors = self.logger.error(
                    f"Missing required field in nb-wrangler section: {field}"
                )
        return no_errors
