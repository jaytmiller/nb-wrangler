"""Data curation logic extracted from NotebookWrangler."""

import os
from pathlib import Path
from typing import Any, Optional

from .config import WranglerConfigurable
from .logger import WranglerLoggable
from .spec_manager import SpecManager
from .repository import RepositoryManager
from .data_manager import RefdataValidator
from .pantry import NbwPantry
from .environment import EnvironmentManager
from . import utils


class DataWrangler(WranglerConfigurable, WranglerLoggable):
    """Handles data curation operations."""

    def __init__(
        self,
        spec_manager: SpecManager,
        pantry: NbwPantry,
        repo_manager: RepositoryManager,
        env_manager: EnvironmentManager,
    ):
        super().__init__()
        self.spec_manager = spec_manager
        self.pantry = pantry
        self.pantry_shelf = pantry.get_shelf(spec_manager.shelf_name)
        self.repo_manager = repo_manager
        self.env_manager = env_manager

    @property
    def resolved_kname(self) -> str | None:
        """Helper to get kernel name, matching NotebookWrangler logic."""
        # Note: This is a bit of duplication, but necessary if we want DataWrangler
        # to be independent for environment registration.
        # In a fuller refactor, this state might live in a shared context.
        return (
            self.spec_manager.get_output_data("kernel_name")
            or self.spec_manager.kernel_name
        )

    def _get_environment(self) -> dict:
        data = self.spec_manager.get_output_data("data")
        if data is not None and not self.config.data_env_vars_no_auto_add:
            mode = self.config.data_env_vars_mode
            env_vars = data.get(mode + "_exports", {})
            return env_vars
        else:
            return {}

    def _register_environment(self) -> bool:
        """Register the target environment with Jupyter as a kernel."""
        kname = self.resolved_kname
        if not kname:
            return self.logger.error("No kernel name found to register.")
        env_vars = self._get_environment()
        display_name = self.spec_manager.display_name or kname
        self.logger.debug(
            f"The resolved env vars for environment '{kname}' are '{env_vars}'."
        )
        if not self.env_manager.register_environment(kname, display_name, env_vars):
            return False
        return True

    def run_workflow(
        self, name: str, steps: list, continue_on_failure: bool = False
    ) -> bool:
        self.logger.info("Running", name, "workflow")
        overall_success = True
        for step in steps:
            self.logger.info(f"Step {step.__name__} of Workflow {name}.")
            if not step():
                if continue_on_failure:
                    self.logger.warning(f"FAILED Workflow {name} Step {step.__name__}.")
                    overall_success = False
                else:
                    return self.logger.error(
                        f"FAILED Workflow {name} Step {step.__name__}."
                    )
        if not overall_success:
            return self.logger.warning(f"Workflow {name} completed with errors.")
        return self.logger.info("Workflow", name, "completed.")

    def collect(self) -> bool:
        """Collect data from notebook repos."""
        self.logger.info("Collecing data information from notebook repo data specs.")
        output_repos = self.spec_manager.get_output_data("repositories")
        if not output_repos:
            self.logger.warning(
                "No repositories found in spec output. Data collection may be incomplete."
            )
            output_repos = {}

        repo_urls = [repo["url"] for repo in output_repos.values()]
        data_validator = RefdataValidator.from_repo_urls(
            self.config.repos_dir, repo_urls
        )

        if spec_refdata := self.spec_manager.refdata_dependencies:
            data_validator.add_spec(
                str(self.repo_manager.repos_dir / "nbw-spec/refdata_dependencies.yaml"),
                spec_refdata,
            )

        spec_exports = data_validator.get_spec_exports()
        self.pantry_shelf.save_exports_file("nbw-spec-exports.sh", spec_exports)
        pantry_exports = data_validator.get_pantry_exports(
            self.pantry_shelf.abstract_data_path
        )
        self.pantry_shelf.save_exports_file("nbw-pantry-exports.sh", pantry_exports)

        if not self._register_environment():
            self.logger.warning(
                "Failed registering environment.  Env vars in JupyterLab may note be set."
            )

        return self.spec_manager.revise_and_save(
            Path(self.config.spec_file).parent,
            data=dict(
                spec_inputs=data_validator.todict(),
                spec_exports=spec_exports,
                pantry_exports=pantry_exports,
            ),
        )

    def get_exports(self) -> Optional[str]:
        """Print out the data environment variables on stdout according to the selected data
        storage mode.
        """
        data = self.spec_manager.get_output_data("data")
        if data is None:
            self.logger.warning(
                "No 'data' section in spec for defining environment variables."
            )
            return ""
        mode = self.config.data_env_vars_mode
        exports = data.get(mode + "_exports")
        exports_str = ""
        if exports is None:
            self.logger.debug(
                f"Data environment for mode '{mode}' is not defined yet.  No environment variables to list."
            )
        else:
            for var, value in exports.items():
                exports_str += f'export {var}="{value}"\n'
        return exports_str

    def print_exports(self) -> bool:
        print(self.get_exports())
        return True

    def _get_url_tuples(
        self,
    ) -> tuple[dict[str, Any], list[tuple[str, str, str, str, str]]]:
        data = self.spec_manager.get_output_data("data")
        if not data or "spec_inputs" not in data:
            raise RuntimeError("Data spec inputs not found. Run --data-collect first.")
        spec_inputs = data["spec_inputs"]
        data_validator = RefdataValidator.from_dict(spec_inputs)
        urls = data_validator.get_data_urls(self.config.data_select)
        return data, urls

    def list_data(self) -> bool:
        self.logger.info("Listing selected data archives.")
        try:
            _data, urls = self._get_url_tuples()
            for url in urls:
                print(url)
            return True
        except Exception as e:
            return self.logger.error(f"Failed to list data: {e}")

    def download(self) -> bool:
        self.logger.info("Downloading selected data archives.")
        try:
            _data, urls = self._get_url_tuples()
            if not self.pantry_shelf.download_all_data(urls):
                return self.logger.error("One or more data archive downloads failed.")
            return self.logger.info("Selected data downloaded successfully.")
        except Exception as e:
            return self.logger.error(f"Failed to download data: {e}")

    def delete(self) -> bool:
        self.logger.info(
            f"Deleting selected data files of types {self.config.data_delete}."
        )
        try:
            _data, urls = self._get_url_tuples()
            if not self.pantry_shelf.delete_archives(self.config.data_delete, urls):
                return self.logger.error("One or more data archive deletes failed.")
            return self.logger.info(
                f"All selected data files of types {self.config.data_delete} removed successfully."
            )
        except Exception as e:
            return self.logger.error(f"Failed to delete data: {e}")

    def update(self) -> bool:
        if self.config.data_no_validation:
            return self.logger.info(
                "Skipping data validation due to --data-no-validation."
            )
        self.logger.info("Collecting metadata for downloaded data archives.")
        try:
            data, urls = self._get_url_tuples()
            self.logger.debug(f"Collecting metadata for {urls}.")
            data["metadata"] = self.pantry_shelf.collect_all_metadata(urls)
            return self.spec_manager.revise_and_save(
                Path(self.config.spec_file).parent,
                data=data,
            )
        except Exception as e:
            return self.logger.error(f"Failed to update data metadata: {e}")

    def validate(self) -> bool:
        if self.config.data_no_validation:
            return self.logger.info(
                "Skipping data validation due to --data-no-validation."
            )
        self.logger.info("Validating all downloaded data archives.")
        try:
            data, urls = self._get_url_tuples()
            metadata = data.get("metadata")
            if metadata is not None:
                if not self.pantry_shelf.validate_all_data(urls, metadata):
                    return self.logger.error("Some data archives did not validate.")
                else:
                    return self.logger.info("All data archives validated.")
            else:
                return self.logger.error(
                    "Before it can be validated, data metadata must be updated."
                )
        except Exception as e:
            return self.logger.error(f"Failed to validate data: {e}")

    def unpack(self) -> bool:
        self.logger.info("Unpacking downloaded data archives to live locations.")
        if not self.config.data_no_symlinks:
            self.symlink_install_data()
        try:
            data, archive_tuples = self._get_url_tuples()
            for archive_tuple in archive_tuples:
                self.logger.debug(f"Unpacking data: {archive_tuple}")
                src_archive = self.pantry_shelf.archive_filepath(archive_tuple)
                if self.config.data_env_vars_mode == "pantry":
                    dest_path = self.pantry_shelf.data_path
                else:
                    resolved = utils.resolve_vars(archive_tuple[4], dict(os.environ))
                    dest_path = Path(resolved)
                final_path = dest_path / archive_tuple[3]
                if final_path.exists() and self.config.data_no_unpack_existing:
                    self.logger.info(
                        f"Skipping unpack for existing directory {final_path}."
                    )
                    continue
                if not self.pantry_shelf.unarchive(src_archive, dest_path, ""):
                    return self.logger.error(
                        f"Failed unpacking '{src_archive}' to '{dest_path}'."
                    )
            if not self.pantry_shelf.save_exports_file(
                "nbw-spec-exports.sh", data["spec_exports"]
            ):
                return self.logger.error("Failed exporting nbw-spec-exports.sh")
            if not self.pantry_shelf.save_exports_file(
                "nbw-pantry-exports.sh", data["pantry_exports"]
            ):
                return self.logger.error("Failed exporting nbw-spec-exports.sh")
            if not self._register_environment():
                self.logger.warning(
                    "Failed registering environment.  Env vars in JupyterLab may note be set."
                )
            return True
        except Exception as e:
            return self.logger.error(f"Failed to unpack data: {e}")

    def symlink_install_data(self) -> bool:
        """Create symlinks from install_data locations to the pantry data directory."""
        try:
            _data, archive_tuples = self._get_url_tuples()
            self.pantry_shelf.symlink_install_data(archive_tuples)
            return True
        except Exception as e:
            return self.logger.error(f"Failed to symlink data: {e}")

    def pack(self) -> bool:
        self.logger.info("Packing downloaded data archives from live locations.")
        try:
            _data, urls = self._get_url_tuples()
            no_errors = True
            for archive_tuple in urls:
                dest_archive = self.pantry_shelf.archive_filepath(archive_tuple)
                src_path = self.pantry_shelf.data_path
                no_errors = (
                    self.pantry_shelf.archive(dest_archive, src_path, "") and no_errors
                )
            return no_errors
        except Exception as e:
            return self.logger.error(f"Failed to pack data: {e}")

    def reset_spec(self) -> bool:
        return self.spec_manager.data_reset_spec()
