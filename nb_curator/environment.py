"""Environment management for package installation and testing."""

import sys
import json
import subprocess
from subprocess import CompletedProcess
from pathlib import Path
from typing import List, Any


from .logging import CuratorLogger


class EnvironmentManager:
    """Manages Python environment setup and package installation."""

    CURATOR_PACKAGES = [
        "uv",
        "mamba",
        "papermill",
        "ipykernel",
        "jupyter",
        "setuptools",
    ]

    def __init__(self, logger: CuratorLogger, micromamba_path: str = "micromamba"):
        self.logger = logger
        self.micromamba_path = micromamba_path

    def curator_run(
        self,
        command: List[str],
        check=True,
        timeout=300,
        capture_output=True,
        text=True,
        **extra_parameters,
    ) -> str | CompletedProcess[Any] | None:
        """Run a command in the current environment."""
        command = [str(word) for word in command]
        parameters = dict(
            capture_output=capture_output,
            text=text,
            check=check,
            timeout=timeout,
        )
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
        command = mm_prefix + ["-c", "conda-forge"] + ["-f", str(micromamba_specfile)]
        result = self.curator_run(command, check=False)
        return self.handle_result(
            result,
            f"Failed to create environment {environment_name}",
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
        result = self.curator_run(command, check=False)
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
        result = self.env_run(environment_name, cmd, check=False)
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
        result = self.env_run(environment_name, cmd, check=False)
        return self.handle_result(
            result,
            "Package un-installation failed:",
            "Package un-installation completed successfully.",
        )

    def test_imports(self, environment_name: str, imports: list[str]) -> bool:
        """Test package imports."""
        self.logger.info(f"Testing {len(imports)} imports")
        # Use inline Python to avoid path contamination between environments
        import_code = f"""
import sys
import traceback

imports = {imports!r}
errs = []
for pkg in imports:
    if pkg.startswith("#"):
        print("Skipping", pkg)
        continue
    try:
        print("Importing", pkg, "... ", end="")
        __import__(pkg)
        print("ok")
    except Exception:
        traceback.print_exc()
        print("FAIL")
        errs.append(pkg)
    sys.stdout.flush()
    sys.stderr.flush()
print("=" * 80)
print(f" Failing imports: {{len(errs)}} ".center(80, "=") + "\\n", "\\n".join(errs), sep="")
sys.exit(int(len(errs) != 0))
"""
        result = self.env_run(
            environment_name,
            ["python", "-c", import_code],
            check=False,
        )
        return self.handle_result(
            result,
            "Failed to import notebook packages:",
            "All imports succeeded.",
        )

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
        cmd = [
            self.micromamba_path,
            "env",
            "list",
            "--json"
        ]
        try:
            result = self.curator_run(cmd, check=True)
        except:
            return self.logger.error(f"Checking for existence of environment '{environment_name}' completely failed. You may need to use 'nb-curator bootstrap' to set up.")
        else:
            envs = json.loads(result)["envs"]
            for env in envs:
                self.logger.debug(f"Checking existence of {environment_name} against {env}.")
                if env.endswith(environment_name):
                    return self.logger.info(f"Environment '{environment_name}' already exists. Skipping auto-init. Use --init-env to force.")
            self.logger.info(f"Environment '{environment_name}' does not exist.  Auto-initing basic empty environment.")
            return False
