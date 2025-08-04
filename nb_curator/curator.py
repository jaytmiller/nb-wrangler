# nb_curator/curator.py
"""Main NotebookCurator class orchestrating the curation process."""

from .config import CuratorConfig
from .spec_manager import SpecManager
from .repository import RepositoryManager
from .nb_processor import NotebookImportProcessor
from .environment import EnvironmentManager
from .compiler import RequirementsCompiler
from .notebook_tester import NotebookTester
from .injector import get_injector
from . import utils


class NotebookCurator:
    """Main curator class for processing notebooks."""

    def __init__(self, config: CuratorConfig):
        self.config = config
        if config.logger is None:
            raise RuntimeError("Logger not initialized in config")
        self.logger = config.logger
        self.logger.info("Loading and validating spec", self.config.spec_file)
        spec_manager = SpecManager.load_and_validate(
            self.logger,
            self.config.spec_file,
        )
        if spec_manager is None:
            raise RuntimeError("Failed to load and validate spec")
        self.spec_manager = spec_manager
        self.env_manager = EnvironmentManager(
            self.logger,
            self.config.micromamba_path,
        )
        if config.repos_dir is None:
            raise RuntimeError("repos_dir not configured")
        self.repo_manager = RepositoryManager(
            self.logger, config.repos_dir, self.env_manager
        )
        self.notebook_import_processor = NotebookImportProcessor(self.logger)
        self.tester = NotebookTester(self.logger, self.config, self.env_manager)
        self.compiler = RequirementsCompiler(self.logger, self.env_manager)
        self.injector = get_injector(
            self.logger, str(config.repos_dir), self.spec_manager
        )

        # Create output directories
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.config.repos_dir.mkdir(parents=True, exist_ok=True)

    @property
    def deployment_name(self):
        return self.spec_manager.deployment_name if self.spec_manager else None

    @property
    def environment_name(self):
        return self.spec_manager.kernel_name if self.spec_manager else None

    @property
    def mamba_spec_file(self):
        return self.config.output_dir / f"{self.spec_manager.moniker}-mamba.yml"

    @property
    def pip_output_file(self):
        return self.config.output_dir / f"{self.spec_manager.moniker}-pip.txt"

    @property
    def extra_pip_output_file(self):
        return self.config.output_dir / f"{self.spec_manager.moniker}-extra-pip.txt"

    def main(self) -> bool:
        """Main processing method."""
        self.logger.debug(f"Starting curator configuration: {self.config}")
        try:
            return self._main_uncaught_core()
        except Exception as e:
            return self.logger.exception(e, f"Error during curation: {e}")

    def _main_uncaught_core(self) -> bool:
        """Execute the complete curation workflow based on configured workflow type."""
        match self.config.workflow:
            case "curation":
                return self._run_development_workflow()
            case "reinstall":
                return self._run_from_spec_workflow()
            case _:
                return self._run_explicit_steps()

    def run_workflow(self, name: str, steps: list):
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
            ],
        ):
            return self._run_explicit_steps()
        return False

    def _run_from_spec_workflow(self) -> bool:
        """Execute steps for environment recreation from spec workflow."""
        self.logger.info("Running install-from-precompiled-spec workflow.")
        required_outputs = (
            "mamba_spec",
            "package_versions",
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
                self._clone_repos,
                self._initialize_environment,
                self._install_packages,
            ],
        ):
            return False
        return self._run_explicit_steps()

    def _run_explicit_steps(self) -> bool:
        """Execute steps for spec/notebook development workflow."""
        self.logger.info("Running explicitly selected steps.")
        flags_and_steps = [
            (self.config.clone_repos, self._clone_repos),
            (self.config.compile_packages, self._compile_requirements),
            (self.config.init_env, self._initialize_environment),
            (self.config.install_packages, self._install_packages),
            (self.config.test_imports, self._test_imports),
            (self.config.test_notebooks, self._test_notebooks),
            (self.config.inject_spi, self.injector.inject),
            (self.config.reset_spec, self._reset_spec),
            (self.config.validate_spec, self.spec_manager.validate),
            (self.config.delete_repos, self.repo_manager.delete_repos),
            (self.config.uninstall_packages, self._uninstall_packages),
            (self.config.delete_env, self._delete_environment),
            (self.config.pack_env, self._pack_environment),
            (self.config.unpack_env, self._unpack_environment),
            (self.config.compact, self._compact),
        ]
        for flag, step in flags_and_steps:
            if flag:
                self.logger.debug("Running step", step.__name__)
                if not step():
                    self.logger.error("FAILED step", step.__name__, "... stopping...")
                    return False
        return True

    def _clone_repos(self) -> bool:
        """Based on the spec unconditionally clone repos, collect specified notebook paths,
        and scrape notebooks for package imports.
        """
        self.logger.info("Setting up repository clones unconditionally.")
        notebook_repo_urls = self.spec_manager.get_repository_urls()
        if self.config.omit_spi_packages and not self.config.inject_spi:
            injector_urls = []
        else:
            injector_urls = self.injector.urls
        if not self.repo_manager.setup_repos(notebook_repo_urls + injector_urls):
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
            notebook_repo_urls=notebook_repo_urls,
            injector_urls=injector_urls,
            test_notebooks=notebook_paths,
            test_imports=test_imports,
            nb_to_imports=nb_to_imports,
        )

    def _generate_target_mamba_spec(self) -> str | bool:
        """Unconditionally generate mamba environment .yml spec."""
        self.logger.info(
            f"Generating mamba spec for target environment {self.mamba_spec_file}."
        )
        mamba_packages = list(self.spec_manager.extra_mamba_packages)
        spec_out = dict(injector_urls=self.injector.urls)
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
            result = self.spec_manager.revise_and_save(
                self.config.output_dir, **spec_out
            )
            return str(result) if result else False

    def _compile_requirements(self) -> bool:
        """Unconditionally identify notebooks, compile requirements, and update spec outputs
        for both mamba and pip.
        """
        if not self._generate_target_mamba_spec():
            return self.logger.error("Failed generating mamba spec.")
        notebook_paths = self.spec_manager.get_outputs("test_notebooks")
        requirements_files = notebook_requirements_files = (
            self.compiler.find_requirements_files(notebook_paths)
        )
        if not self.compiler.write_pip_requirements_file(
            self.extra_pip_output_file, self.spec_manager.extra_pip_packages
        ):
            return False
        requirements_files.append(self.extra_pip_output_file)
        if not self.config.omit_spi_packages:
            spi_requirements_files = self.injector.find_spi_pip_files()
            requirements_files.extend(spi_requirements_files)
        package_versions = self.compiler.compile_requirements(
            requirements_files, self.pip_output_file
        )
        if not package_versions:
            self.logger.warning(
                "Combined packages defined by notebooks and spec are empty."
            )
        return self.spec_manager.revise_and_save(
            self.config.output_dir,
            package_versions=package_versions,
            pip_requirements_files=notebook_requirements_files,
            pip_compiler_output=utils.yaml_block(open(self.pip_output_file).read()),
        )

    def _initialize_environment(self) -> bool:
        """Unconditionally initialize the target environment."""
        if self.env_manager.environment_exists(self.environment_name):
            return self.logger.info(
                "Environment already exists, skipping re-install.  Use --delete-env to remove."
            )
        mamba_spec = self.spec_manager.get_outputs("mamba_spec")
        with open(self.mamba_spec_file, "w+") as spec_file:
            spec_file.write(str(mamba_spec))
        if not self.env_manager.create_environment(
            self.environment_name, self.mamba_spec_file
        ):
            return False
        return self.env_manager.register_environment(self.environment_name)

    def _install_packages(self) -> bool:
        """Unconditionally install packages and test imports."""
        pip_compiler_output = self.spec_manager.get_outputs("pip_compiler_output")
        if pip_compiler_output:
            with open(self.pip_output_file, "w+") as pkgs:
                pkgs.write(str(pip_compiler_output))
            if not self.env_manager.install_packages(
                self.environment_name, [self.pip_output_file]
            ):
                return False
        else:
            self.logger.warning("Found no pip requirements to install.")
        return True

    def _uninstall_packages(self) -> bool:
        """Unconditionally uninstall pip packages from target environment."""
        if not self.env_manager.uninstall_packages(self.environment_name, []):
            self.logger.error(
                "Failed to uninstall packages for environment", self.environment_name
            )
            return False
        else:
            self.logger.info(
                "Removed pip packages from environment", self.environment_name
            )
            return True

    def _test_imports(self) -> bool:
        """Unconditionally run import checks if test_imports are defined."""
        if test_imports := self.spec_manager.get_outputs("test_imports"):
            return self.env_manager.test_imports(self.environment_name, test_imports)
        else:
            self.logger.warning("Found no imports to check in spec'd notebooks.")
            return True

    def _test_notebooks(self) -> bool:
        """Unconditionally test notebooks matching the configured pattern."""
        notebook_paths = self.spec_manager.get_outputs("test_notebooks")
        filtered_notebooks = self.tester.filter_notebooks(
            notebook_paths, self.config.test_notebooks or ""
        )
        return self.tester.test_notebooks(self.environment_name, filtered_notebooks)

    def _reset_spec(self) -> bool:
        self.logger.info("Resetting/clearing spec outputs.")
        return self.spec_manager.reset_spec()

    def _unpack_environment(self) -> bool:
        if self.env_manager.unpack_environment(self.environment_name):
            self.logger.info("Unpacked environment", self.environment_name)
            return True
        else:
            self.logger.error("Failed unpacking environment", self.environment_name)
            return False

    def _pack_environment(self) -> bool:
        if self.env_manager.pack_environment(self.environment_name):
            self.logger.info("Packed environment", self.environment_name)
            return True
        else:
            self.logger.error("Failed packing environment", self.environment_name)
            return False

    def _delete_environment(self) -> bool:
        """Unregister its kernel and delete the test environment."""
        self.env_manager.unregister_environment(self.environment_name)
        if self.env_manager.delete_environment(self.environment_name):
            self.logger.info("Deleted environment", self.environment_name)
            return True
        else:
            self.logger.error("Failed deleting environment", self.environment_name)
            return False

    def _compact(self) -> bool:
        if self.env_manager.compact():
            self.logger.info("Compacted curator, removing install caches, etc.")
            return True
        else:
            self.logger.error("Failed compacting curator.")
            return False
