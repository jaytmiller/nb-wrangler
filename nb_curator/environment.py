"""Environment management for package installation and testing.

The basic model is that micromamba is used to bootstrap and manage
both the curation and target environments.

micromamba is used to install only pre-required mamba packages.
uv is used to manage pip packages in the target environment.

environmentsinstall non-pip Python packages
"""

import json
import subprocess
from subprocess import CompletedProcess
from pathlib import Path
from typing import List, Any


from .logging import CuratorLogger

DEFAULT_TIMEOUT = 300


class EnvironmentManager:
    """Manages Python environment setup and package installation."""

    # Currently limited to uv, older build tools for packages not yet
    # updated to pyproject.toml, and jupyter kernel management packages
    # ipykernel and jupyter.
    TARGET_PACKAGES = [
        "uv",
        "pip",
        "ipykernel",
        "jupyter",
        "cython",
        "setuptools",
        "wheel",
    ]

    # The target environment does not currently require papermill to
    # support notebook testing,  it can be run from the curator
    # environment so don't make it a TARGET dependency.
    CURATOR_PACKAGES = [
        "papermill",
    ] + TARGET_PACKAGES

    # IMPORTANT: see also the nb-curator bash script used for bootstrapping
    # the basic nbcurator environment and inlines the above requirements
    # for CURATOR_PACKAGES.
    DEFAULT_TIMEOUT = 300
    REPO_CLONE_TIMEOUT = 300
    ENV_INSTALL__TIMEOUT = 600
    ENV_CREATE_TIMEOUT = 600
    INSTALL_PACKAGES_TIMEOUT = 1200
    PIP_COMPILE_TIMEOUT = 600
    IMPORT_TEST_TIMEOUT = 300

    # ------------------------------------------------------------------------------

    def __init__(self, logger: CuratorLogger, micromamba_path: str = "micromamba"):
        self.logger = logger
        self.micromamba_path = micromamba_path

    def curator_run(
        self,
        command: List[str],
        check=True,
        timeout=DEFAULT_TIMEOUT,
        text=True,
        output_mode="separate",
        **extra_parameters,
    ) -> str | CompletedProcess[Any] | None:
        """Run a command in the current environment."""
        command = [str(word) for word in command]
        parameters = dict(
            text=text,
            check=check,
            timeout=DEFAULT_TIMEOUT,
        )
        if output_mode == "combined":
            parameters.update(
                dict(
                    capture_output=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
            )
        elif output_mode == "separate":
            parameters.update(
                dict(
                    capture_output=True,
                )
            )
        else:
            raise ValueError(f"Invalid output_mode value: {output_mode}")
        parameters.update(extra_parameters)
        self.logger.debug(
            f"Running command with no shell: {command} {extra_parameters}"
        )
        self.logger.debug(f"For trying it this may work anyway: {' '.join(command)}")
        result = subprocess.run(command, **parameters)
        # self.logger.debug(f"Command output: {result.stdout}")
        if check:
            return result.stdout
        else:
            return result

    def handle_result(
        self, result: CompletedProcess[Any] | str | None, fail: str, success: str = ""
    ):
        """Provide standard handling for the check=False case of the xxx_run methods by
        issuing a success info or fail error and returning True or False respectively
        depending on the return code of a subprocess result.

        If either the success or fail log messages (stripped) end in ":" then append
        result.stdout or result.stderr respectively.
        """
        if not isinstance(result, CompletedProcess):
            raise RuntimeError(f"Expected CompletedProcess, got {type(result)}")
        if result.returncode != 0:
            if fail.strip().endswith(":"):
                fail += result.stderr
            return self.logger.error(fail)
        else:
            if success.strip().endswith(":"):
                success += result.stdout
            return self.logger.info(success) if success else True

    def env_run(
        self, environment, command: List[str], **keys
    ) -> str | CompletedProcess[Any] | None:
        """Run a command in the specified environment.

        See EnvironmentManager.run for **keys optional settings.
        """
        self.logger.debug(f"Running command {command} in environment: {environment}")
        mm_prefix = [self.micromamba_path, "run", "-n", environment]
        return self.curator_run(mm_prefix + command, **keys)

    def create_environment(
        self, environment_name: str, micromamba_specfile: Path | None = None
    ) -> bool:
        """Create a new environment."""
        self.logger.info(f"Creating environment: {environment_name}")
        mm_prefix = [self.micromamba_path, "create", "--yes", "-n", environment_name]
        command = mm_prefix + ["-f", str(micromamba_specfile)]
        result = self.curator_run(command, check=False, timeout=self.ENV_CREATE_TIMEOUT)
        return self.handle_result(
            result,
            f"Failed to create environment {environment_name}: \n",
            f"Environment {environment_name} created",
        )

    def delete_environment(
        self, environment_name: str
    ) -> str | CompletedProcess[Any] | None:
        """Delete an existing environment."""
        self.logger.info(f"Deleting environment: {environment_name}")
        command = [
            self.micromamba_path,
            "env",
            "remove",
            "--yes",
            "-n",
            environment_name,
        ]
        result = self.curator_run(command, check=False, timeout=self.ENV_CREATE_TIMEOUT)
        return self.handle_result(
            result,
            f"Failed to delete environment {environment_name}",
            f"Environment {environment_name} deleted",
        )

    def install_packages(
        self,
        environment_name: str,
        requirements_paths: List[Path],
    ) -> bool:
        """Install the compiled package lists."""
        self.logger.info(f"Installing packages from: {requirements_paths}")

        cmd = [
            "uv",
            "pip",
            "install",
        ]
        for path in requirements_paths:
            cmd += ["-r", str(path)]

        # Install packages using uv running in the target environment
        result = self.env_run(
            environment_name, cmd, check=False, timeout=self.INSTALL_PACKAGES_TIMEOUT
        )
        return self.handle_result(
            result,
            "Package installation failed:",
            "Package installation completed successfully.",
        )

    def uninstall_packages(
        self,
        environment_name: str,
        requirements_paths: List[Path],
    ) -> bool:
        """Uninstall the compiled package lists."""
        self.logger.info(f"Uninstalling packages from: {requirements_paths}")

        cmd = [
            "uv",
            "pip",
            "uninstall",
            "--yes",
        ]
        for path in requirements_paths:
            cmd += ["-r", str(path)]

        # Install packages using uv
        result = self.env_run(
            environment_name, cmd, check=False, timeout=self.INSTALL_PACKAGES_TIMEOUT
        )
        return self.handle_result(
            result,
            "Package un-installation failed:",
            "Package un-installation completed successfully.",
        )

    def test_imports(self, environment_name: str, imports: list[str]) -> bool:
        """Test package imports."""
        self.logger.info(f"Testing {len(imports)} imports")
        failed_imports = []
        for import_ in imports:
            self.logger.debug(f"Testing import: {import_}")
            result = self.env_run(
                environment_name,
                ["python", "-c", f"import {import_}"],
                check=False,
                timeout=20,
            )
            succeeded = self.handle_result(
                result,
                f"Failed to import {import_}:",
                f"Import of {import_} succeeded.",
            )
            if not succeeded:
                failed_imports.append(import_)
        if failed_imports:
            self.logger.error(f"Failed to import {len(failed_imports)}: {failed_imports}")
            return False
        else:
            self.logger.info("All imports succeeded.")
            return True

    def register_environment(self, environment_name: str, display_name=None) -> bool:
        """Register Jupyter environment for the environment.

        nbcurator environment should work here since it is modifying
        files under $HOME related to *any* jupyter environment the
        user has.
        """
        cmd = [
            "python",
            "-m",
            "ipykernel",
            "install",
            "--user",
            "--name",
            environment_name,
            "--display-name",
            display_name or environment_name,
        ]
        result = self.env_run(environment_name, cmd, check=False)
        return self.handle_result(
            result, f"Failed to register environment {environment_name}: "
        )

    def unregister_environment(self, environment_name: str) -> bool:
        """Unregister Jupyter environment for the environment."""
        cmd = [
            "jupyter",
            "kernelspec",
            "uninstall",
            "--yes",
            environment_name,
        ]
        result = self.env_run(environment_name, cmd, check=False)
        return self.handle_result(
            result, f"Failed to unregister environment {environment_name}: "
        )

    def environment_exists(self, environment_name: str) -> bool:
        """Return True IFF `environment_name` exists."""
        cmd = [self.micromamba_path, "env", "list", "--json"]
        try:
            result = self.curator_run(cmd, check=True)
        except Exception as e:
            return self.logger.exception(
                e,
                f"Checking for existence of environment '{environment_name}' completely failed. See README.md for info on bootstrapping.",
            )
        else:
            envs = json.loads(result)["envs"]
            for env in envs:
                self.logger.debug(
                    f"Checking existence of {environment_name} against {env}."
                )
                if env.endswith(environment_name):
                    return self.logger.info(
                        f"Environment '{environment_name}' already exists. Skipping auto-init. Use --init-env to force."
                    )
            self.logger.info(
                f"Environment '{environment_name}' does not exist.  Auto-initing basic empty environment."
            )
            return False
