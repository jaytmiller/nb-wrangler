# nb_wrangler/wrangler.py
"""Main NotebookWrangler class orchestrating the curation process."""

from pathlib import Path
from typing import Any

from .constants import NBW_URI
from .config import WranglerConfig
from .logger import WranglerLoggable
from .spec_manager import SpecManager
from .repository import RepositoryManager
from .nb_processor import NotebookImportProcessor
from .environment import EnvironmentManager
from .compiler import RequirementsCompiler
from .notebook_tester import NotebookTester
from .injector import get_injector
from .data_manager import RefdataValidator
from .pantry import NbwPantry
from . import utils


class NotebookWrangler(WranglerLoggable):
    """Main wrangler class for processing notebooks."""

    def __init__(self, config: WranglerConfig):
        self.config = config
        super().__init__()
        self.logger.info("Loading and validating spec", self.config.spec_file)
        spec_manager = SpecManager.load_and_validate(self.config.spec_file)
        if spec_manager is None:
            raise RuntimeError("SpecManager is not initialized.  Cannot continue.")
        self.spec_manager = spec_manager
        self.env_manager = EnvironmentManager(
            self.logger,
            self.config.mamba_command,
            self.config.pip_command,
        )
        self.pantry = NbwPantry()
        self.pantry_shelf = self.pantry.get_shelf(self.spec_manager.shelf_name)
        if self.config.repos_dir == NBW_URI:
            self.config.repos_dir = self.pantry_shelf.notebook_repos_path
        else:
            self.config.repos_dir = Path(self.config.repos_dir)
        self.repo_manager = RepositoryManager(config.repos_dir, self.env_manager)
        self.notebook_import_processor = NotebookImportProcessor(self.logger)
        self.tester = NotebookTester(self.logger, self.config, self.env_manager)
        self.compiler = RequirementsCompiler(self.logger, self.env_manager)
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
        if self.config.archive_format:
            self.logger.warning(
                "Overriding spec'ed and/or default archive file format to",
                self.config.archive_format,
                "nominally to experiment, may not automatically unpack correctly.",
            )
            return self.config.archive_format
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
        match self.config.workflow:
            case "curation":
                return self._run_development_workflow()
            case "submit-for-build":
                return self._run_submit_build_workflow()
            case "reinstall":
                return self._run_reinstall_spec_workflow()
            case "data-curation":
                return self._run_data_curation_workflow()
            case "data-reinstall":
                return self._run_data_reinstall_workflow()
            case _:
                return self._run_explicit_steps()

    def run_workflow(self, name: str, steps: list) -> bool:
        self.logger.info("Running", name, "workflow")
        for step in steps:
            self.logger.debug(f"Running step {step.__name__}.")
            if not step():
                return self.logger.error(f"FAILED running step {step.__name__}.")
        return self.logger.info("Workflow", name, "completed.")

    def _run_development_workflow(self) -> bool:
        """Execute steps for spec/notebook development workflow."""
        if self.run_workflow(
            "spec development / curation",
            [
                self._clone_repos,
                self._compile_requirements,
                self._initialize_environment,
                self._install_packages,
                self._save_final_spec,
            ],
        ):
            return self._run_explicit_steps()
        return False

    def _run_data_curation_workflow(self) -> bool:
        """Execute steps for data curation workflow, defining spec for data."""
        if self.run_workflow(
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
        ):
            return self._run_explicit_steps()
        return False

    def _run_submit_build_workflow(self) -> bool:
        """Execute steps for the build submission workflow."""
        if self.run_workflow(
            "submit-for-build",
            [
                self._validate_spec,
                self._delete_spi_repo,
                self._clone_repos,
                self._submit_for_build,
            ],
        ):
            return self._run_explicit_steps()
        return False

    def _run_reinstall_spec_workflow(self) -> bool:
        """Execute steps for environment recreation from spec workflow."""
        required_outputs = (
            "mamba_spec",
            "pip_compiler_output",
        )
        assert self.spec_manager is not None  # guaranteed by __init__
        if not self.spec_manager.outputs_exist(*required_outputs):
            return self.logger.error(
                "This workflow requires a precompiled spec with outputs for",
                required_outputs,
            )
        if not self.run_workflow(
            "install-compiled-spec",
            [
                # self._clone_repos,
                self._validate_spec,
                self._spec_add,
                self._initialize_environment,
                self._install_packages,
            ],
        ):
            return False
        return self._run_explicit_steps()

    def _run_data_reinstall_workflow(self) -> bool:
        """Execute steps for data curation workflow, defining spec for data."""
        if self.run_workflow(
            "data download / validation / unpacking",
            [
                self._validate_spec,
                self._spec_add,
                self._data_download,
                self._data_validate,
                self._data_unpack,
            ],
        ):
            return self._run_explicit_steps()
        return False

    def _run_explicit_steps(self) -> bool:
        """Execute steps for spec/notebook development workflow."""
        self.logger.info("Running explicitly selected steps, if any.")
        flags_and_steps = [
            (self.config.clone_repos, self._clone_repos),
            (self.config.compile_packages, self._compile_requirements),
            (self.config.init_env, self._initialize_environment),
            (self.config.install_packages, self._install_packages),
            (self.config.test_imports, self._test_imports),
            (self.config.test_notebooks, self._test_notebooks),
            (self.config.inject_spi, self.injector.inject),
            (self.config.update_spec_hash, self._update_spec_sha256),
            (self.config.validate_spec, self._validate_spec),
            (self.config.pack_env, self._pack_environment),
            (self.config.unpack_env, self._unpack_environment),
            (self.config.register_env, self._register_environment),
            (self.config.unregister_env, self._unregister_environment),
            (self.config.spec_add, self._spec_add),
            (self.config.data_collect, self._data_collect),
            (self.config.data_list, self._data_list),
            (self.config.data_download, self._data_download),
            (self.config.data_delete, self._data_delete),
            (self.config.data_update, self._data_update),
            (self.config.data_validate, self._data_validate),
            (self.config.data_unpack, self._data_unpack),
            (self.config.data_pack, self._data_pack),
            (self.config.delete_repos, self._delete_repos),
            (self.config.uninstall_packages, self._uninstall_packages),
            (self.config.delete_env, self._delete_environment),
            (self.config.compact, self._compact),
            (self.config.reset_spec, self._reset_spec),
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
        if (
            self.config.omit_spi_packages
            and not self.config.inject_spi
            and not self.config.submit_for_build
        ):
            injector_url = None
        else:
            injector_url = self.injector.url
            if not self.repo_manager.setup_repos([injector_url], single_branch=False):
                return False
        if not self.repo_manager.setup_repos(notebook_repo_urls):
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
            add_sha256=not self.config.ignore_spec_hash,
            notebook_repo_urls=notebook_repo_urls,
            injector_url=injector_url,
            test_notebooks=notebook_paths,
            test_imports=test_imports,
            nb_to_imports=nb_to_imports,
        )

    def _spec_add(self):
        """Add a new spec to the pantry."""
        self.pantry_shelf.set_wrangler_spec(self.config.spec_file)
        return True

    def _data_collect(self):
        """Collect data from notebook repos."""
        self.logger.info("Collecing information from notebook repo data specs.")
        repo_urls = self.spec_manager.get_output_data("notebook_repo_urls")
        data_validator = RefdataValidator.from_repo_urls(
            self.config.repos_dir, repo_urls
        )
        section_env_vars = data_validator.get_data_section_env_vars()
        pantry_env_vars = data_validator.get_data_pantry_env_vars(
            self.pantry_shelf.abstract_data_path
        )
        other_env_vars = data_validator.get_data_other_env_vars()
        local_exports = dict()
        local_exports.update(other_env_vars)
        local_exports.update(section_env_vars)
        local_exports.update(other_env_vars)
        pantry_exports = dict()
        pantry_exports.update(other_env_vars)
        pantry_exports.update(pantry_env_vars)
        self.pantry_shelf.save_exports_file("nbw-local-exports.sh", local_exports)
        self.pantry_shelf.save_exports_file("nbw-pantry-exports.sh", pantry_exports)
        return self.spec_manager.revise_and_save(
            Path(self.config.spec_file).parent,
            data=dict(
                spec_inputs=data_validator.todict(),
                local_exports=local_exports,
                pantry_exports=pantry_exports,
            ),
        )

    def _get_data_url_tuples(self) -> tuple[dict[str, Any], list[tuple[str, str, str, str]]]:
        data = self.spec_manager.get_output_data("data")
        spec_inputs = data["spec_inputs"]
        data_validator = RefdataValidator.from_dict(spec_inputs)
        urls = data_validator.get_data_urls(self.config.data_select)
        return data, urls

    def _data_list(self):
        self.logger.info("Listing selected data archives.")
        _data, urls = self._get_data_url_tuples()
        for url in urls[:-1]:
            print(url)
        return True

    def _data_download(self):
        self.logger.info("Downloading selected data archives.")
        _data, urls = self._get_data_url_tuples()
        if self.pantry_shelf.download_all_data(urls):
            return self.logger.error("One or more data archive downloads failed.")
        return self.logger.info("Selected data downloaded successfully.")

    def _data_delete(self):
        self.logger.info(f"Deleting selected data files of types {self.config.data_delete}.")
        _data, urls = self._get_data_url_tuples()
        if self.pantry_shelf.delete_archives(self.config.data_delete, urls):
            return self.logger.error("One or more data archive deletes failed.")
        return self.logger.info(f"All selected data files of types {self.config.data_delete} removed successfully.")


    def _data_update(self):
        self.logger.info("Collecting metadata for downloaded data archives.")
        data, urls = self._get_data_url_tuples()
        data["metadata"] = self.pantry_shelf.collect_all_metadata(urls)
        return self.spec_manager.revise_and_save(
            Path(self.config.spec_file).parent,
            data=data,
        )

    def _data_validate(self):
        self.logger.info("Validating all downloaded data archives.")
        data, urls = self._get_data_url_tuples()
        metadata = data.get("metadata")
        if metadata:
            if self.pantry_shelf.validate_all_data(urls, metadata):
                return self.logger.error("Some data archives did not validate.")
            else:
                return self.logger.info("All data archives validated.")
        else:
            return self.logger.error(
                "Before it can be validated, data metadata must be updated."
            )

    def _data_unpack(self):
        self.logger.info("Unpacking downloaded data archives to live locations.")
        errors = False
        data, archive_tuples = self._get_data_url_tuples()
        for archive_tuple in archive_tuples:
            src_archive = self.pantry_shelf.archive_filepath(archive_tuple)
            dest_path = self.pantry_shelf.data_path
            # self.logger.info(f"Unpacking '{src_archive}' to '{dest_path}'.")
            errors = self.env_manager.unarchive(src_archive, dest_path, "") or errors
        self.pantry_shelf.save_exports_file(
            "nbw-local-exports.sh", data["local_exports"]
        )
        self.pantry_shelf.save_exports_file(
            "nbw-pantry-exports.sh", data["pantry_exports"]
        )
        return errors

    def _data_pack(self):
        self.logger.info("Packing downloaded data archives from live locations.")
        errors = False
        for archive_tuple in self._get_data_url_tuples()[1]:
            dest_archive = self.pantry_shelf.archive_filepath(archive_tuple)
            src_path = self.pantry_shelf.data_path
            # self.logger.info(f"Packing '{dest_archive}' from '{src_path}'.")
            errors = self.env_manager.archive(dest_archive, src_path, "") or errors
        return errors

    def _delete_repos(self):
        """Delete notebook and SPI repo clones."""
        urls = self.spec_manager.get_outputs("notebook_repo_urls")
        if spi_url := self.spec_manager.get_outputs("injector_url"):
            urls.append(spi_url)
        return self.repo_manager.delete_repos(urls)

    def _delete_spi_repo(self):
        """Remove the 'SPI injector repo' used to make PR's for image builds
        ensuring the next copy will be clean.
        """
        return self.repo_manager.delete_repos(
            [self.spec_manager.get_outputs("injector_url")]
        )

    def _generate_target_mamba_spec(self) -> str | bool:
        """Unconditionally generate mamba environment .yml spec."""
        self.logger.info(
            f"Generating mamba spec for target environment {self.mamba_spec_file}."
        )
        mamba_packages = list(self.spec_manager.extra_mamba_packages)
        spec_out: dict[str, Any] = dict(injector_url=self.injector.url)
        if not self.config.omit_spi_packages:
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
                add_sha256=not self.config.ignore_spec_hash,
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
        if not self.config.omit_spi_packages:
            spi_requirements_files = self.injector.find_spi_pip_files()
            requirements_files.extend(spi_requirements_files)
        self.compiler.compile_requirements(
            requirements_files, self.pip_output_file, self.config.add_pip_hashes
        )
        with self.pip_output_file.open("r") as f:
            yaml_str = utils.yaml_block(f.read())
        requirements_files_str = list(str(f) for f in requirements_files)
        pip_map = utils.files_to_map(requirements_files_str)
        return self.spec_manager.revise_and_save(
            self.config.output_dir,
            add_sha256=not self.config.ignore_spec_hash,
            pip_compiler_output=yaml_str,
            pip_requirements_files=requirements_files_str,
            pip_map=pip_map,
        )

    def _initialize_environment(self) -> bool:
        """Unconditionally initialize the target environment."""
        if self.env_manager.environment_exists(self.env_name):
            return self.logger.info(
                f"Environment {self.env_name} already exists, skipping re-install.  Use --delete-env to remove."
            )
        mamba_spec = str(self.spec_manager.get_outputs("mamba_spec"))
        with open(self.mamba_spec_file, "w+") as spec_file:
            spec_file.write(mamba_spec)
        if not self.env_manager.create_environment(self.env_name, self.mamba_spec_file):
            return False
        if not self.env_manager.register_environment(
            self.env_name, self.kernel_display_name
        ):
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
            add_sha256=not self.config.ignore_spec_hash,
        )

    def _save_final_spec(self) -> bool:
        """Overwrite the original spec with the updated spec."""
        self.logger.debug("Updating spec with final results.")
        return self.spec_manager.save_spec(
            Path(self.config.spec_file).parent,
            add_sha256=not self.config.ignore_spec_hash,
        )

    def _update_spec_sha256(self) -> bool:
        return self.spec_manager.save_spec(
            Path(self.config.spec_file).parent, add_sha256=True
        )

    def _validate_spec_sha256(self) -> bool:
        if self.config.ignore_spec_hash:
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
        if test_imports := self.spec_manager.get_outputs("test_imports"):
            return self.env_manager.test_imports(self.env_name, test_imports)
        else:
            return self.logger.warning("Found no imports to check in spec'd notebooks.")

    def _test_notebooks(self) -> bool:
        """Unconditionally test notebooks matching the configured pattern."""
        notebook_paths = self.spec_manager.get_outputs("test_notebooks")
        if filtered_notebooks := self.tester.filter_notebooks(
            notebook_paths, self.config.test_notebooks or ""
        ):
            return self.tester.test_notebooks(self.env_name, filtered_notebooks)
        else:
            return self.logger.warning(
                f"Found no notebooks to test matching regex '{self.config.test_notebooks}'."
            )

    def _reset_spec(self) -> bool:
        return self.spec_manager.reset_spec()

    def _unpack_environment(self) -> bool:
        if not self.env_manager.unpack_environment(
            self.env_name, self.spec_manager.moniker, self.archive_format
        ):
            return False
        if not self.env_manager.register_environment(
            self.env_name, self.kernel_display_name
        ):
            return False
        return True

    def _pack_environment(self) -> bool:
        return self.env_manager.pack_environment(
            self.env_name, self.spec_manager.moniker, self.archive_format
        )

    def _delete_environment(self) -> bool:
        """Unregister its kernel and delete the test environment."""
        self.env_manager.unregister_environment(self.env_name)
        return self.env_manager.delete_environment(self.env_name)

    def _compact(self) -> bool:
        return self.env_manager.compact()

    def _register_environment(self) -> bool:  # post-start-hook / user support
        """Register the target environment with Jupyter as a kernel."""
        return self.env_manager.register_environment(
            self.env_name, self.kernel_display_name
        )

    def _unregister_environment(self) -> bool:
        """Unregister the target environment from Jupyter."""
        return self.env_manager.unregister_environment(self.env_name)

    def _submit_for_build(self) -> bool:
        return self.injector.submit_for_build()
