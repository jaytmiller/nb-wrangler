"""Main NotebookCurator class orchestrating the curation process."""

from typing import Optional

from .config import CuratorConfig
from .logging import CuratorLogger
from .spec_manager import SpecManager
from .repository import RepositoryManager
from .nb_processor import NotebookImportProcessor
from .environment import EnvironmentManager
from .compiler import RequirementsCompiler
from .notebook_tester import NotebookTester
from .injector import get_injector


class NotebookCurator:
    """Main class orchestrating the notebook curation process."""

    def __init__(self, config: CuratorConfig):
        self.config = config
        self.logger = CuratorLogger(config.verbose, config.debug)
        self.spec_manager = SpecManager.load_and_validate(
            self.logger,
            self.config.spec_file,
        )
        self.env_manager = EnvironmentManager(
            self.logger,
            self.config.micromamba_path,
        )
        self.repo_manager = RepositoryManager(
            self.logger, config.repos_dir, self.env_manager
        )
        self.notebook_import_processor = NotebookImportProcessor(self.logger)
        self.tester = NotebookTester(self.logger, self.config, self.env_manager)
        self.compiler = RequirementsCompiler(self.logger, self.env_manager)
        self.injector = get_injector(self.logger, config.repos_dir, self.spec_manager)

        # Create output directories
        config.output_dir.mkdir(parents=True, exist_ok=True)
        config.repos_dir.mkdir(parents=True, exist_ok=True)

    @property
    def deployment_name(self):
        return self.spec_manager.deployment_name if self.spec_manager else None

    @property
    def environment_name(self):
        return self.spec_manager.kernel_name if self.spec_manager else None

    @property
    def extra_pip_requirements(self):
        return self.spec_manager.extra_pip_requirements if self.spec_manager else None

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
        """Main execution method."""
        try:
            return self._main_uncaught_core()
        except Exception as e:
            return self.logger.exception(e, f"Error during curation: {e}")

    def _main_uncaught_core(self) -> bool:
        """Execute the complete curation workflow."""

        if self.config.reset_spec:
            self.spec_manager.reset_spec()

        # Setup repositories
        if not self._clone_setup():
            return self.log.error("Basic repo notebook setup and selection failed.")

        # Set up basic empty target/test environment and kernel
        target_env_exists = self.env_manager.environment_exists(self.environment_name)
        if self.config.init_env or not target_env_exists:
            if not self._initialize_environment():
                return False

        # Handle target environment pip requirements file locations and constraint resolution
        if self.config.compile_packages:
            if not self._compile_requirements():
                return False

        # Install compiled pip package versions into the target environment, test explicit notebook imports
        if self.config.install_packages:
            if not self._install_packages():
                return False

        # Run spec'ed notebooks themselves directly in the target environment, nominally headless, fail on exception
        if self.config.test_notebooks:
            if not self._test_notebooks():
                return False

        # Inject critical output fields from the finished spec into the build environment clone.
        # The clone should then be requirements complete for a manual or automated notebook image build.
        if self.config.inject_spi:
            self.injector.inject()

        # Remove the compiled list of packages but leave behind the basic target environment.
        if self.config.uninstall_packages:
            if not self.env_manager.uninstall_packages(
                self.environment_name, [self.pip_output_file]
            ):
                return False

        # Delete all aspects of the basic target environment defined by the spec.
        if self.config.delete_env:
            if not self._delete_environment():
                return False

        # Remove all notebook and/or build environment repo clones.
        if self.config.delete_repos:
            if not self.repo_manager.delete_repos():
                return False

        return True

    def _clone_setup(self):
        """Based on the spec and cloned repos, collect specified notebook paths
        and scrape them for package imports.
        """
        notebook_repo_urls = self.spec_manager.get_repository_urls()
        if not self.repo_manager.setup_repos(notebook_repo_urls + self.injector.urls):
            return False

        notebook_paths = self.spec_manager.collect_notebook_paths(
            self.config.repos_dir, notebook_repo_urls
        )
        if not notebook_paths:
            return False

        test_imports = self.notebook_import_processor.extract_imports(notebook_paths)
        if not test_imports:
            self.logger.warning(
                "No imports found in notebooks. Import tests will be skipped."
            )

        return self.spec_manager.revise_and_save(
            output_dir=self.config.output_dir,
            notebook_repo_urls=notebook_repo_urls,
            test_notebooks=notebook_paths,
            test_imports=test_imports,
            injector_urls=self.injector.urls,
        )

    def _initialize_environment(self) -> bool:
        """Initialize the target environment."""
        mamba_spec = self._generate_mamba_spec()
        if not mamba_spec:
            return False
        if not self.compiler.write_mamba_spec_file(self.mamba_spec_file, mamba_spec):
            return False
        if not self.env_manager.create_environment(
            self.environment_name, self.mamba_spec_file
        ):
            return False
        return self.env_manager.register_environment(self.environment_name)

    def _generate_mamba_spec(self) -> Optional[str]:
        """Generate mamba environment specification."""
        mamba_files = self.injector.find_spi_mamba_requirements_files()
        mamba_spec = self.compiler.generate_mamba_spec(
            self.spec_manager.kernel_name, mamba_files
        )
        if not mamba_spec:
            return None
        self.spec_manager.revise_and_save(
            output_dir=self.config.output_dir,
            mamba_requirements_files=mamba_files,
            mamba_spec=mamba_spec,
            injector_urls=self.injector.urls,
        )
        return mamba_spec

    def _compile_requirements(self) -> bool:
        """Compile requirements and update spec."""
        notebook_paths = self.spec_manager.get_outputs("test_notebooks")
        requirements_files = self.compiler.find_requirements_files(notebook_paths)
        if not requirements_files:
            return False
        if not self.compiler.write_pip_requirements_file(
            self.extra_pip_output_file, self.extra_pip_requirements
        ):
            return False
        requirements_files.append(self.extra_pip_output_file)
        package_versions = self.compiler.compile_requirements(
            requirements_files, self.pip_output_file
        )
        if not package_versions:
            return False
        return self.spec_manager.revise_and_save(
            output_dir=self.config.output_dir,
            pip_requirements_files=requirements_files,
            package_versions=package_versions,
        )

    def _install_packages(self) -> bool:
        """Install packages and test imports."""
        package_versions, test_imports = self.spec_manager.get_outputs(
            "package_versions", "test_imports"
        )
        if not package_versions:
            return False
        self.compiler.write_pip_requirements_file(
            self.pip_output_file, package_versions
        )
        if not self.env_manager.install_packages(
            self.environment_name, [self.pip_output_file]
        ):
            return False
        return self.env_manager.test_imports(self.environment_name, test_imports)

    def _test_notebooks(self) -> bool:
        """Test notebooks matching the configured pattern."""
        notebook_paths = self.spec_manager.get_outputs("test_notebooks")
        filtered_notebooks = self.tester.filter_notebooks(
            notebook_paths, self.config.test_notebooks
        )
        return self.tester.test_notebooks(self.environment_name, filtered_notebooks)

    def _delete_environment(self) -> bool:
        """Unregister its kernel and delete the test environment."""
        self.env_manager.unregister_environment(self.environment_name)
        return self.env_manager.delete_environment(self.environment_name)

    def print_log_counters(self):
        """Print summary of logged messages."""
        self.logger.print_log_counters()
