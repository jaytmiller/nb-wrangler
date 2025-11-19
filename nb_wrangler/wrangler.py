# nb_wrangler/wrangler.py
"""Main NotebookWrangler class orchestrating the curation process."""

import os
from pathlib import Path
from typing import Any

from .constants import NBW_URI
from .config import WranglerConfigurable
from .logger import WranglerLoggable
from .spec_manager import SpecManager
from .repository import RepositoryManager
from .nb_processor import NotebookImportProcessor
from .environment import WranglerEnvable
from .compiler import RequirementsCompiler
from .notebook_tester import NotebookTester
from .injector import get_injector
from .data_manager import RefdataValidator
from .pantry import NbwPantry
from . import utils


class NotebookWrangler(WranglerConfigurable, WranglerLoggable, WranglerEnvable):
    """Main wrangler class for processing notebooks."""

    def __init__(self):
        super().__init__()
        self.logger.info("Loading and validating spec", self.config.spec_file)
        self.spec_manager = SpecManager.load_and_validate(self.config.spec_file)
        if self.spec_manager is None:
            raise RuntimeError("SpecManager is not initialized.  Cannot continue.")
        self.pantry = NbwPantry()
        self.pantry_shelf = self.pantry.get_shelf(self.spec_manager.shelf_name)
        if self.config.repos_dir == NBW_URI:
            self.config.repos_dir = self.pantry_shelf.notebook_repos_path
        else:
            self.config.repos_dir = Path(self.config.repos_dir)
        self.repo_manager = RepositoryManager(self.config.repos_dir)
        self.notebook_import_processor = NotebookImportProcessor()
        self.tester = NotebookTester()
        self.compiler = RequirementsCompiler(
            python_version=self.spec_manager.python_version
        )
        self.injector = get_injector(self.repo_manager, self.spec_manager)
        # Create output directories
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.config.repos_dir.mkdir(parents=True, exist_ok=True)

    @property
    def deployment_name(self):
        """Nominally the branch of science-platform-images this build will target."""
        return self.spec_manager.deployment_name if self.spec_manager else None

    @property
    def env_name(self):
        """Strictly speaking,  kernel name,  but nominally also environment name.
        The worst/only exception I know of is "base" environment == "python3" kernel.
        """
        return self.spec_manager.kernel_name if self.spec_manager else None

    @property
    def kernel_display_name(self) -> str:
        """More readable version of kernel name visible in JupyterLab menu."""
        return self.spec_manager.display_name if self.spec_manager else self.env_name

    @property
    def mamba_spec_file(self):
        return self.config.output_dir / f"{self.spec_manager.moniker}-mamba.yml"

    @property
    def pip_output_file(self):
        return self.config.output_dir / f"{self.spec_manager.moniker}-pip.txt"

    @property
    def extra_pip_output_file(self):
        return self.config.output_dir / f"{self.spec_manager.moniker}-extra-pip.txt"

    @property
    def shelf_name(self) -> str:
        return self.spec_manager.shelf_name

    @property
    def archive_format(self):
        """Combines default + optional spec value + optional cli override into final format."""
        if self.config.env_archive_format:
            self.logger.warning(
                "Overriding spec'ed and/or default archive file format to",
                self.config.env_archive_format,
                "nominally to experiment, may not automatically unpack correctly.",
            )
            return self.config.env_archive_format
        else:
            return self.spec_manager.archive_format

    def main(self) -> bool:
        """Main processing method."""
        self.logger.debug(f"Starting wrangler configuration: {self.config}")
        try:
            return self._main_uncaught_core()
        except Exception as e:
            return self.logger.exception(e, f"Error during curation: {e}")

    def _main_uncaught_core(self) -> bool:
        """Execute the complete curation workflow based on configured workflow type."""
        if not self._setup_environment():
            return self.logger.error(
                "Failed to set up internal Python environment from spec."
            )
        no_errors = True
        if self.config.workflows:
            self.logger.info(f"Running workflows {self.config.workflows}.")
        for workflow in self.config.workflows:
            match workflow:
                case "curation":
                    status = self._run_development_workflow()
                case "submit_for-build":
                    status = self._run_submit_build_workflow()
                case "reinstall":
                    status = self._run_reinstall_spec_workflow()
                case "data_curation":
                    status = self._run_data_curation_workflow()
                case "data_reinstall":
                    status = self._run_data_reinstall_workflow()
                case _:
                    self.logger.error(f"Undefined workflow {workflow}.")
            no_errors = status and no_errors
        return self._run_explicit_steps() and no_errors

    def run_workflow(self, name: str, steps: list) -> bool:
        self.logger.info("Running", name, "workflow")
        for step in steps:
            self.logger.debug(f"Running step {step.__name__}.")
            if not step():
                return self.logger.error(f"FAILED running step {step.__name__}.")
        return self.logger.info("Workflow", name, "completed.")

    def _run_development_workflow(self) -> bool:
        """Execute steps for spec/notebook development workflow."""
        return self.run_workflow(
            "spec development / curation",
            [
                self._clone_repos,
                self._compile_requirements,
                self._initialize_environment,
                self._install_packages,
                self._save_final_spec,
            ],
        )

    def _run_data_curation_workflow(self) -> bool:
        """Execute steps for data curation workflow, defining spec for data."""
        return self.run_workflow(
            "data collection / downloads / metadata capture / unpacking",
            [
                self._clone_repos,
                self._spec_add,
                self._data_collect,
                self._data_download,
                self._data_update,
                self._data_validate,
                self._data_unpack,
                self._save_final_spec,
            ],
        )

    def _run_submit_build_workflow(self) -> bool:
        """Execute steps for the build submission workflow."""
        return self.run_workflow(
            "submit-for-build",
            [
                self._validate_spec,
                self._delete_spi_repo,
                self._clone_repos,
                self._submit_for_build,
            ],
        )

    def _run_reinstall_spec_workflow(self) -> bool:
        """Execute steps for environment recreation from spec workflow."""
        required_outputs = (
            "mamba_spec",
            "pip_compiler_output",
        )
        assert self.spec_manager is not None  # guaranteed by __init__
        if not self.spec_manager.outputs_exist(*required_outputs):
            return self.logger.error(
                "This workflow requires a precompiled spec with outputs",
                required_outputs,
            )
        return self.run_workflow(
            "install-compiled-spec",
            [
                # self._clone_repos,
                self._validate_spec,
                self._spec_add,
                self._initialize_environment,
                self._install_packages,
            ],
        )

    def _run_data_reinstall_workflow(self) -> bool:
        """Execute steps for data curation workflow, defining spec for data."""
        return self.run_workflow(
            "data download / validation / unpacking",
            [
                self._validate_spec,
                self._spec_add,
                self._data_download,
                self._data_validate,
                self._data_unpack,
            ],
        )

    def _run_explicit_steps(self) -> bool:
        """Execute steps for spec/notebook development workflow."""
        self.logger.info("Running any explicitly selected steps.")
        flags_and_steps = [
            (self.config.clone_repos, self._clone_repos),
            (self.config.packages_compile, self._compile_requirements),
            (self.config.env_init, self._initialize_environment),
            (self.config.packages_install, self._install_packages),
            (self.config.test_imports, self._test_imports),
            (self.config.test_notebooks, self._test_notebooks),
            (self.config.inject_spi, self.injector.inject),
            (self.config.spec_update_hash, self._update_spec_sha256),
            (self.config.spec_validate, self._validate_spec),
            (self.config.env_pack, self._pack_environment),
            (self.config.env_unpack, self._unpack_environment),
            (self.config.env_register, self._register_environment),
            (self.config.env_unregister, self._unregister_environment),
            (self.config.spec_add, self._spec_add),
            (self.config.spec_list, self._spec_list),
            (self.config.data_collect, self._data_collect),
            (self.config.data_list, self._data_list),
            (self.config.data_download, self._data_download),
            (self.config.data_delete, self._data_delete),
            (self.config.data_update, self._data_update),
            (self.config.data_validate, self._data_validate),
            (self.config.data_unpack, self._data_unpack),
            (self.config.data_pack, self._data_pack),
            (self.config.delete_repos, self._delete_repos),
            (self.config.packages_uninstall, self._uninstall_packages),
            (self.config.env_delete, self._delete_environment),
            (self.config.env_compact, self._env_compact),
            (self.config.spec_reset, self._reset_spec),
            (self.config.data_reset_spec, self._data_reset_spec),
        ]
        for flag, step in flags_and_steps:
            if flag:
                self.logger.info("Running step", step.__name__)
                if not step():
                    self.logger.error("FAILED step", step.__name__, "... stopping...")
                    return False
        return True

    def _clone_repos(self) -> bool:
        """Based on the spec unconditionally clone repos, collect specified notebook paths,
        and scrape notebooks for package imports.
        """
        self.logger.info("Setting up repository clones.")
        notebook_repo_urls = self.spec_manager.get_repository_urls()
        notebook_repo_branches = self.spec_manager.get_repository_branches()
        if (
            self.config.packages_omit_spi
            and not self.config.inject_spi
            and not self.config.submit_for_build
        ):
            injector_url = None
        else:
            injector_url = self.injector.url
            if not self.repo_manager.setup_repos([injector_url], single_branch=False):
                return False
        if not self.repo_manager.setup_repos(
            notebook_repo_urls, repo_branches=notebook_repo_branches
        ):
            return False
        notebook_paths = self.spec_manager.collect_notebook_paths(
            self.config.repos_dir, notebook_repo_urls
        )
        if not notebook_paths:
            self.logger.warning(
                "No notebooks found in specified repositories using spec'd patterns."
            )
        test_imports, nb_to_imports = self.notebook_import_processor.extract_imports(
            notebook_paths
        )
        if not test_imports:
            self.logger.warning(
                "No imports found in notebooks. Import tests will be skipped."
            )
        return self.spec_manager.revise_and_save(
            self.config.output_dir,
            add_sha256=not self.config.spec_ignore_hash,
            notebook_repo_urls=notebook_repo_urls,
            notebook_repo_branches=notebook_repo_branches,
            injector_url=injector_url,
            test_notebooks=notebook_paths,
            test_imports=test_imports,
            nb_to_imports=nb_to_imports,
        )

    def _spec_add(self) -> bool:
        """Add a new spec to the pantry."""
        self.pantry_shelf.set_wrangler_spec(self.config.spec_file)
        return True

    def _spec_list(self) -> bool:
        """List the available shelves/specs in the pantry."""
        self.logger.info("Listing available shelves/specs in pantry.")
        return self.pantry.list_shelves()

    def _data_collect(self) -> bool:
        """Collect data from notebook repos."""
        self.logger.info("Collecing data information from notebook repo data specs.")
        repo_urls = self.spec_manager.get_output_data("notebook_repo_urls")
        data_validator = RefdataValidator.from_repo_urls(
            self.config.repos_dir, repo_urls
        )

        spec_exports = data_validator.get_spec_exports()
        self.pantry_shelf.save_exports_file("nbw-spec-exports.sh", spec_exports)
        pantry_exports = data_validator.get_pantry_exports(
            self.pantry_shelf.abstract_data_path
        )
        self.pantry_shelf.save_exports_file("nbw-pantry-exports.sh", pantry_exports)

        self._register_environment()

        return self.spec_manager.revise_and_save(
            Path(self.config.spec_file).parent,
            data=dict(
                spec_inputs=data_validator.todict(),
                spec_exports=spec_exports,
                pantry_exports=pantry_exports,
            ),
        )

    def _get_data_url_tuples(
        self,
    ) -> tuple[dict[str, Any], list[tuple[str, str, str, str, str]]]:
        data = self.spec_manager.get_output_data("data")
        spec_inputs = data["spec_inputs"]
        data_validator = RefdataValidator.from_dict(spec_inputs)
        urls = data_validator.get_data_urls(self.config.data_select)
        return data, urls

    def _data_list(self) -> bool:
        self.logger.info("Listing selected data archives.")
        _data, urls = self._get_data_url_tuples()
        for url in urls[:-1]:
            print(url)
        return True

    def _data_download(self) -> bool:
        self.logger.info("Downloading selected data archives.")
        _data, urls = self._get_data_url_tuples()
        if not self.pantry_shelf.download_all_data(urls):
            return self.logger.error("One or more data archive downloads failed.")
        return self.logger.info("Selected data downloaded successfully.")

    def _data_delete(self) -> bool:
        self.logger.info(
            f"Deleting selected data files of types {self.config.data_delete}."
        )
        _data, urls = self._get_data_url_tuples()
        if not self.pantry_shelf.delete_archives(self.config.data_delete, urls):
            return self.logger.error("One or more data archive deletes failed.")
        return self.logger.info(
            f"All selected data files of types {self.config.data_delete} removed successfully."
        )

    def _data_update(self) -> bool:
        if self.config.data_no_validation:
            return self.logger.info(
                "Skipping data validation due to --data-no-validation."
            )
        self.logger.info("Collecting metadata for downloaded data archives.")
        data, urls = self._get_data_url_tuples()
        data["metadata"] = self.pantry_shelf.collect_all_metadata(urls)
        return self.spec_manager.revise_and_save(
            Path(self.config.spec_file).parent,
            data=data,
        )

    def _data_validate(self) -> bool:
        if self.config.data_no_validation:
            return self.logger.info(
                "Skipping data validation due to --data-no-validation."
            )
        self.logger.info("Validating all downloaded data archives.")
        data, urls = self._get_data_url_tuples()
        metadata = data.get("metadata")
        if metadata:
            if not self.pantry_shelf.validate_all_data(urls, metadata):
                return self.logger.error("Some data archives did not validate.")
            else:
                return self.logger.info("All data archives validated.")
        else:
            return self.logger.error(
                "Before it can be validated, data metadata must be updated."
            )

    def _data_unpack(self) -> bool:
        self.logger.info("Unpacking downloaded data archives to live locations.")
        data, archive_tuples = self._get_data_url_tuples()
        for archive_tuple in archive_tuples:
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
            if not self.env_manager.unarchive(src_archive, dest_path, ""):
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
            return self.logger.error("Failed registering environment.")
        return True

    def _data_pack(self) -> bool:
        self.logger.info("Packing downloaded data archives from live locations.")
        no_errors = True
        for archive_tuple in self._get_data_url_tuples()[1]:
            dest_archive = self.pantry_shelf.archive_filepath(archive_tuple)
            src_path = self.pantry_shelf.data_path
            no_errors = (
                self.env_manager.archive(dest_archive, src_path, "") and no_errors
            )
        return no_errors

    def _delete_repos(self) -> bool:
        """Delete notebook and SPI repo clones."""
        urls = self.spec_manager.get_outputs("notebook_repo_urls")
        if spi_url := self.spec_manager.get_outputs("injector_url"):
            urls.append(spi_url)
        return self.repo_manager.delete_repos(urls)

    def _delete_spi_repo(self) -> bool:
        """Remove the 'SPI injector repo' used to make PR's for image builds
        ensuring the next copy will be clean.
        """
        url = self.spec_manager.get_outputs("injector_url")
        if not url:
            self.logger.info("No injector repo to delete.")
            return True
        return self.repo_manager.delete_repos([str(url)])

    def _generate_target_mamba_spec(self) -> str | bool:
        """Unconditionally generate mamba environment .yml spec."""
        self.logger.info(
            f"Generating mamba spec for target environment {self.mamba_spec_file}."
        )
        mamba_packages = list(self.spec_manager.extra_mamba_packages)
        spec_out: dict[str, Any] = dict(injector_url=self.injector.url)
        if not self.config.packages_omit_spi:
            spi_file_paths = self.injector.find_spi_mamba_files()
            spec_out["spi_files"] = [str(p) for p in spi_file_paths]
            spec_out["spi_packages"] = spi_packages = (
                self.compiler.read_package_versions(spi_file_paths)
            )
            mamba_packages += spi_packages
        mamba_spec = self.compiler.generate_target_mamba_spec(
            self.spec_manager.kernel_name, mamba_packages
        )
        if not mamba_spec:
            return self.logger.error(
                "Failed to generate mamba spec for target environment."
            )
        else:
            spec_out["mamba_spec"] = utils.yaml_block(mamba_spec)
            return self.spec_manager.revise_and_save(
                self.config.output_dir,
                add_sha256=not self.config.spec_ignore_hash,
                **spec_out,
            )

    def _compile_requirements(self) -> bool:
        """Unconditionally identify notebooks, compile requirements, and update spec outputs
        for both mamba and pip.
        """
        if not self._generate_target_mamba_spec():
            return self.logger.error("Failed generating mamba spec.")
        notebook_paths = self.spec_manager.get_outputs("test_notebooks")
        requirements_files = self.compiler.find_requirements_files(notebook_paths)
        if not self.compiler.write_pip_requirements_file(
            self.extra_pip_output_file, self.spec_manager.extra_pip_packages
        ):
            return False
        requirements_files.append(self.extra_pip_output_file)
        if not self.config.packages_omit_spi:
            spi_requirements_files = self.injector.find_spi_pip_files()
            requirements_files.extend(spi_requirements_files)
        self.compiler.compile_requirements(
            requirements_files, self.pip_output_file, self.config.spec_add_pip_hashes
        )
        with self.pip_output_file.open("r") as f:
            yaml_str = utils.yaml_block(f.read())
        d = dict(
            add_sha256=not self.config.spec_ignore_hash,
            pip_compiler_output=yaml_str,
        )
        if self.config.packages_diagnostics:
            requirements_files_str = list(str(f) for f in requirements_files)
            pip_map = utils.files_to_map(requirements_files_str)
            d["pip_requirements_files"] = requirements_files_str
            d["pip_map"] = pip_map
        return self.spec_manager.revise_and_save(
            self.config.output_dir,
            **d,
        )

    def _initialize_environment(self) -> bool:
        """Unconditionally initialize the target environment."""
        if self.env_manager.environment_exists(self.env_name):
            return self.logger.info(
                f"Environment {self.env_name} already exists, skipping re-install.  Use --env-delete to remove."
            )
        mamba_spec = str(self.spec_manager.get_outputs("mamba_spec"))
        with open(self.mamba_spec_file, "w+") as spec_file:
            spec_file.write(mamba_spec)
        if not self.env_manager.create_environment(self.env_name, self.mamba_spec_file):
            return False
        if not self._register_environment():
            return False
        return self._copy_spec_to_env()

    def _install_packages(self) -> bool:
        """Unconditionally install packages and test imports."""
        pip_compiler_output = self.spec_manager.get_outputs("pip_compiler_output")
        if pip_compiler_output:
            with open(self.pip_output_file, "w+") as pkgs:
                pkgs.write(str(pip_compiler_output))
            if not self.env_manager.install_packages(
                self.env_name, [self.pip_output_file]
            ):
                return False
        else:
            self.logger.warning("Found no pip requirements to install.")
        return self._copy_spec_to_env()

    def _uninstall_packages(self) -> bool:
        """Unconditionally uninstall pip packages from target environment."""
        return self.env_manager.uninstall_packages(
            self.env_name, [self.pip_output_file]
        )

    def _copy_spec_to_env(self) -> bool:
        self.logger.debug("Copying spec to target environment.")
        return self.spec_manager.save_spec(
            self.env_manager.env_live_path(self.env_name),
            add_sha256=not self.config.spec_ignore_hash,
        )

    def _save_final_spec(self) -> bool:
        """Overwrite the original spec with the updated spec."""
        self.logger.debug("Updating spec with final results.")
        no_errors = self.spec_manager.save_spec(
            Path(self.config.spec_file).parent,
            add_sha256=not self.config.spec_ignore_hash,
        )
        if self.pantry_shelf.spec_path.exists():
            no_errors = (
                self.spec_manager.save_spec_as(
                    self.pantry_shelf.spec_path,
                    add_sha256=not self.config.spec_ignore_hash,
                )
                and no_errors
            )
        return no_errors

    def _update_spec_sha256(self) -> bool:
        return self.spec_manager.save_spec(
            Path(self.config.spec_file).parent, add_sha256=True
        )

    def _validate_spec_sha256(self) -> bool:
        if self.config.spec_ignore_hash:
            return self.logger.warning(
                "Ignoring spec_sha256 checksum validation. Spec integrity unknown."
            )
        else:
            return self.spec_manager.validate_sha256()

    def _validate_spec(self) -> bool:
        if not self.spec_manager.validate():
            return False
        return self._validate_spec_sha256()

    def _test_imports(self) -> bool:
        """Unconditionally run import checks if test_imports are defined."""
        if nb_to_imports := self.spec_manager.get_outputs("nb_to_imports"):
            return self.env_manager.test_nb_imports(self.env_name, nb_to_imports)
        else:
            return self.logger.warning("Found no imports to check in spec'd notebooks.")

    def _test_notebooks(self) -> bool:
        """Unconditionally test notebooks matching the configured pattern."""
        notebook_paths = self.spec_manager.get_outputs("test_notebooks")
        if filtered_notebooks := self.tester.filter_notebooks(
            notebook_paths,
            self.config.test_notebooks or "",
            self.config.test_notebooks_exclude,
        ):
            return self.tester.test_notebooks(self.env_name, filtered_notebooks)
        else:
            return self.logger.warning(
                "Found no notebooks to test matching inclusion patterns but not exclusion patterns."
            )

    def _reset_spec(self) -> bool:
        return self.spec_manager.reset_spec()

    def _data_reset_spec(self) -> bool:
        return self.spec_manager.data_reset_spec()

    def _unpack_environment(self) -> bool:
        if self.env_manager.unpack_environment(
            self.env_name, self.spec_manager.moniker, self.archive_format
        ):
            return self._register_environment()
        return False

    def _pack_environment(self) -> bool:
        return self.env_manager.pack_environment(
            self.env_name, self.spec_manager.moniker, self.archive_format
        )

    def _delete_environment(self) -> bool:
        """Unregister its kernel and delete the test environment."""
        self.env_manager.unregister_environment(self.env_name)
        return self.env_manager.delete_environment(self.env_name)

    def _env_compact(self) -> bool:
        return self.env_manager.compact()

    def _get_environment(self) -> dict:
        data = self.spec_manager.get_output_data("data")
        if data is not None and not self.config.data_env_vars_no_auto_add:
            env_vars = data.get(self.config.data_env_vars_mode + "_exports", {})
            return env_vars
            # resolved_vars = utils.resolve_env(env_vars)
            # return resolved_vars
        else:
            return {}

    def _setup_environment(self) -> bool:
        env_vars = self._get_environment()
        env_vars = utils.resolve_env(env_vars)
        for key, value in env_vars.items():
            os.environ[key] = value
            self.logger.debug(
                f"Setting environment '{key}' = '{value}' for wrangler and and notebooks."
            )
        return True

    def _register_environment(self) -> bool:  # post-start-hook / user support
        """Register the target environment with Jupyter as a kernel."""
        env_vars = self._get_environment()
        self.logger.debug(
            f"The resolved env vars for environment '{self.env_name}' are '{env_vars}'."
        )
        if not self.env_manager.register_environment(
            self.env_name, self.kernel_display_name, env_vars
        ):
            return False
        return True

    def _unregister_environment(self) -> bool:
        """Unregister the target environment from Jupyter."""
        return self.env_manager.unregister_environment(self.env_name)

    def _submit_for_build(self) -> bool:
        return self.injector.submit_for_build()
