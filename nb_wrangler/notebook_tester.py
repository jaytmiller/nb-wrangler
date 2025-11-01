"""Notebook testing functionality."""

import datetime
import glob
import os
import shutil
import stat
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

from .logger import WranglerLogger
from .config import WranglerConfig
from .environment import EnvironmentManager


class NotebookTester:
    """Tests notebooks by executing them in isolated environments."""

    def __init__(
        self,
        logger: WranglerLogger,
        config: WranglerConfig,
        env_manager: EnvironmentManager,
    ):
        self.logger = logger
        self.config = config
        self.env_manager = env_manager

    def filter_notebooks(
        self, notebook_paths: list[str], test_patterns: str
    ) -> list[str]:
        """Filter notebooks based on test patterns."""
        import re

        unique_notebooks = set()
        for nb_path in sorted(notebook_paths):
            for regex in test_patterns.split(","):
                if re.search(regex, nb_path):
                    unique_notebooks.add(nb_path)

        filtered = sorted(unique_notebooks)
        self.logger.info(f"Filtered notebook list to {len(filtered)} entries")
        return filtered

    def test_notebooks(self, environment: str, notebook_paths: list[str]) -> bool:
        """Test multiple notebooks in parallel."""
        self.logger.info(
            f"Testing {len(notebook_paths)} notebooks with {self.config.jobs} jobs"
        )

        failing_notebooks = []

        with ProcessPoolExecutor(max_workers=self.config.jobs) as executor:
            results = executor.map(
                self._test_single_notebook,
                notebook_paths,
                [environment] * len(notebook_paths),
            )

            for failed, notebook, output in results:
                sys.stdout.write(output)
                sys.stdout.flush()
                if failed:
                    failing_notebooks.append(notebook)

        if failing_notebooks:
            self._print_divider("FAILED")
            for notebook in failing_notebooks:
                self.logger.error(f"Notebook {notebook} failed tests")
            return False

        return self.logger.info("All notebooks passed tests")

    def _test_single_notebook(
        self, notebook: str, environment: str
    ) -> tuple[bool, str, str]:
        """Test a single notebook in isolation."""
        if notebook.startswith("#"):
            return False, notebook, self._print_divider(f"Skipping {notebook}")

        base_nb = os.path.basename(notebook)
        start = datetime.datetime.now()
        output = self._print_divider(
            f"Testing '{base_nb}' on environment '{environment}'"
        )
        here = os.getcwd()
        try:
            err, combined_output = self._test_single_notebook_core(
                notebook, environment, self.config.timeout
            )
            output += combined_output
        except Exception as e:
            output += f"Exception during testing: {str(e)}\n"
            err = True
        finally:
            os.chdir(here)

        elapsed = datetime.datetime.now() - start
        status = "OK" if not err else "FAIL"
        output += self._print_divider(f"Tested {base_nb} {status} {elapsed}")

        return err, notebook, output

    def _test_single_notebook_core(
        self, notebook: str, environment: str, timeout: int
    ) -> tuple[bool, str]:
        """Test a single notebook in isolation."""

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.dirname(os.path.abspath(notebook))
            test_dir = os.path.join(temp_dir, "notebook-test")
            shutil.copytree(source_path, test_dir)
            os.chdir(test_dir)

            # set permissions
            os.chmod(test_dir, stat.S_IRWXU)
            for path in glob.glob("*"):
                os.chmod(path, stat.S_IRWXU)

            # Run the notebook
            if notebook.endswith(".ipynb"):
                cmd = f"papermill --no-progress-bar {os.path.basename(notebook)} -k {environment} test.ipynb"
            elif notebook.endswith(".py"):
                cmd = f"python {os.path.basename(notebook)}"
            else:
                raise ValueError(f"Unhandled test file extension: {notebook}")
            result = self.env_manager.wrangler_run(
                cmd,
                output_mode="combined",
                timeout=timeout,
                check=False,
                env=os.environ,
            )
            err = result.returncode != 0
            return err, result.stdout

    def _print_divider(self, title: str, char: str = "*", width: int = 100) -> str:
        """Create a divider string with centered title."""
        return f" {title} ".center(width, char) + "\n"
