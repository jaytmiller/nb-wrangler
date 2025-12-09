"""Notebook testing functionality."""

import datetime
import glob
import os
import shutil
import stat
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

from .config import WranglerConfigurable
from .logger import WranglerLoggable
from .environment import WranglerEnvable


class NotebookTester(WranglerConfigurable, WranglerLoggable, WranglerEnvable):
    """Tests notebooks by executing them in isolated environments."""

    def __init__(self):
        super().__init__()

    def filter_notebooks(
        self,
        notebook_configs: dict[str, dict],
        include_patterns: str,
        exclude_patterns: str,
    ) -> dict[str, dict]:
        """Filter notebooks based on test patterns."""
        import re

        include_patterns = include_patterns or ".*"
        exclude_patterns = exclude_patterns or r"^$"
        include_list = [p for p in include_patterns.split(",") if p]
        exclude_list = [p for p in exclude_patterns.split(",") if p]

        unique_notebooks = set()
        for nb_path in sorted(notebook_configs.keys()):
            for include_regex in include_list:
                if re.search(include_regex, nb_path):
                    self.logger.debug(
                        f"Including '{nb_path}' due to inclusion pattern '{include_regex}'."
                    )
                    for exclude_regex in exclude_list:
                        if re.search(exclude_regex, nb_path):
                            self.logger.debug(
                                f"Excluding '{nb_path}' due to exclusion pattern '{exclude_regex}'."
                            )
                            break
                    else:
                        unique_notebooks.add(nb_path)

        filtered_paths = sorted(unique_notebooks)
        filtered_configs = {
            path: notebook_configs[path] for path in filtered_paths
        }
        self.logger.info(f"Filtered notebook list to {len(filtered_configs)} entries:")
        for notebook in filtered_configs:
            self.logger.info(notebook)
        return filtered_configs

    def test_notebooks(
        self, environment: str, notebook_configs: dict[str, dict]
    ) -> bool:
        """Test multiple notebooks in parallel."""

        max_jobs = max(1, min(self.config.jobs, len(notebook_configs)))
        self.logger.info(
            f"Testing {len(notebook_configs)} notebooks with {max_jobs} jobs"
        )

        failing_notebooks = []

        with ProcessPoolExecutor(max_workers=max_jobs) as executor:
            notebook_items = list(notebook_configs.items())
            results = executor.map(
                self._test_single_notebook,
                [item[0] for item in notebook_items],
                [item[1] for item in notebook_items],
                [environment] * len(notebook_items),
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
        self, notebook: str, config: dict, environment: str
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
        err = False
        try:
            tests = config.get("tests", {"papermill": True})
            if tests.get("papermill", True):
                papermill_err, papermill_output = self._run_papermill_test(
                    notebook, environment, self.config.timeout
                )
                output += papermill_output
                err = err or papermill_err
            else:
                output += f"Skipping default papermill/headess testing for {notebook}\n"
            if "playwright" in tests:
                playwright_script = tests["playwright"]
                playwright_err, playwright_output = self._run_playwright_test(
                    notebook, environment, playwright_script, self.config.timeout
                )
                output += playwright_output
                err = err or playwright_err
        except Exception as e:
            output += f"Exception during testing: {str(e)}\n"
            err = True
        finally:
            os.chdir(here)

        elapsed = datetime.datetime.now() - start
        status = "OK" if not err else "FAIL"
        output += self._print_divider(f"Tested {base_nb} {status} {elapsed}")

        return err, notebook, output

    def _run_papermill_test(
        self, notebook: str, environment: str, timeout: int
    ) -> tuple[bool, str]:
        """Test a single notebook in isolation using papermill."""

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

    def _run_playwright_test(
        self, notebook: str, environment: str, script: str, timeout: int
    ) -> tuple[bool, str]:
        """Test a single notebook in isolation using playwright."""
        self.logger.info(
            f"Playwright testing for '{notebook}' with script '{script}' is not yet implemented."
        )
        return False, "Playwright test skipped (not implemented)"

    def _print_divider(self, title: str, char: str = "*", width: int = 100) -> str:
        """Create a divider string with centered title."""
        return f" {title} ".center(width, char) + "\n"
