"""Environment management for package installation and testing.

The basic model is that micromamba is used to bootstrap and manage
both the curation and target environments.

micromamba is used to install only pre-required mamba packages.
uv is used to manage pip packages in the target environment.

environmentsinstall non-pip Python packages
"""

import os
import json
import shutil
import shlex
import subprocess
from subprocess import CompletedProcess
from pathlib import Path
from typing import Any


from .logger import CuratorLogger
from .config import NBC_ROOT, NBC_PANTRY

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

    def __init__(
        self, logger: CuratorLogger, micromamba_path: str | Path = "micromamba"
    ):
        self.logger = logger
        self.micromamba_path = str(micromamba_path)

    @property
    def nbc_root_dir(self) -> Path:
        return NBC_ROOT

    @property
    def nbc_mm_dir(self) -> Path:
        return NBC_ROOT / "mm"

    @property
    def nbc_pantry_dir(self) -> Path:
        return NBC_PANTRY

    @property
    def mm_envs_dir(self) -> Path:
        return self.nbc_mm_dir / "envs"

    @property
    def mm_pkgs_dir(self) -> Path:
        return self.nbc_mm_dir / "pkgs"

    @property
    def nbc_cache_dir(self) -> Path:
        cache_path = os.environ.get("NBC_CACHE")
        return Path(cache_path) if cache_path else self.nbc_root_dir / "cache"

    def env_store_path(self, environment_name: str) -> Path:
        return self.nbc_pantry_dir / "envs" / (environment_name.lower() + ".zst")

    def env_live_path(self, environment_name: str) -> Path:
        return self.mm_envs_dir / environment_name

    def _condition_cmd(self, cmd: list[str] | str) -> list[str]:
        """Condition the command into a list of UNIX CLI 'words'.

        If command is already a string,  split it into string "words".
        If it is a list,  make sure every element is a string.
        """
        if isinstance(cmd, (list, tuple)):
            return [str(word) for word in cmd]
        elif isinstance(cmd, str):
            return shlex.split(cmd)
        else:
            raise TypeError("cmd must be a list or str")

    def curator_run(
        self,
        command: list[str] | str,
        check=True,
        cwd=None,
        timeout=DEFAULT_TIMEOUT,
        text=True,
        output_mode="separate",
        **extra_parameters,
    ) -> str | CompletedProcess[Any] | None:
        """Run a command in the current environment."""
        command = self._condition_cmd(command)
        parameters = dict(
            text=text,
            check=check,
            cwd=cwd,
            timeout=timeout,
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
        # self.logger.debug(f"For trying it this may work anyway: {' '.join(command)}")
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
        self, environment, command: list[str] | str, **keys
    ) -> str | CompletedProcess[Any] | None:
        """Run a command in the specified environment.

        See EnvironmentManager.run for **keys optional settings.
        """
        command = self._condition_cmd(command)
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
        requirements_paths: list[Path],
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
        requirements_paths: list[Path],
    ) -> bool:
        """Uninstall the compiled package lists."""
        self.logger.info(f"Uninstalling packages from: {requirements_paths}")

        cmd = "uv pip uninstall --yes"
        for path in requirements_paths:
            cmd += " -r " + str(path)

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
                f"python -c 'import {import_}'",
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
            self.logger.error(
                f"Failed to import {len(failed_imports)}: {failed_imports}"
            )
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
        cmd = self._condition_cmd(
            f"python -m ipykernel install --user --name {environment_name} --display-name "
        )
        cmd += [
            display_name or environment_name
        ]  # display name may be multi-word,  string splits break quoting
        result = self.env_run(environment_name, cmd, check=False)
        return self.handle_result(
            result, f"Failed to register environment {environment_name}: "
        )

    def unregister_environment(self, environment_name: str) -> bool:
        """Unregister Jupyter environment for the environment."""
        cmd = f"jupyter kernelspec uninstall --yes {environment_name}"
        result = self.env_run(environment_name, cmd, check=False)
        return self.handle_result(
            result, f"Failed to unregister environment {environment_name}: "
        )

    def environment_exists(self, environment_name: str) -> bool:
        """Return True IFF `environment_name` exists."""
        cmd = self.micromamba_path + " env list --json"
        try:
            result = self.curator_run(cmd, check=True)
        except Exception as e:
            return self.logger.exception(
                e,
                f"Checking for existence of environment '{environment_name}' completely failed. See README.md for info on bootstrapping.",
            )
        else:
            result_str = result.stdout if hasattr(result, 'stdout') else str(result)
            envs = json.loads(result_str)["envs"]
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

    def archive(self, source_dirpath: Path, archive_filepath: Path) -> bool:
        Path(archive_filepath).mkdir(parents=True, exist_ok=True)
        Path(source_dirpath).mkdir(parents=True, exist_ok=True)
        cmd = f"tar -acf {archive_filepath} ."
        result = self.curator_run(cmd, cwd=source_dirpath, check=False)
        return self.handle_result(
            result, f"Failed to pack {source_dirpath} into {archive_filepath}:"
        )

    def unarchive(
        self, archive_filepath: str | Path, destination_dirpath: str | Path
    ) -> bool:
        Path(destination_dirpath).mkdir(parents=True, exist_ok=True)
        cmd = f"tar -axf {archive_filepath} ."
        result = self.curator_run(cmd, cwd=destination_dirpath, check=False)
        return self.handle_result(
            result, f"Failed to unpack {archive_filepath} into {destination_dirpath}:"
        )

    def pack_environment(self, environment_name: str):
        return self.archive(
            self.env_live_path(environment_name), self.env_store_path(environment_name)
        )

    def unpack_environment(self, environment_name: str):
        return self.archive(
            self.env_live_path(environment_name), self.env_store_path(environment_name)
        )

    def pack_curator(self, archive_filepath: Path | str) -> bool:
        archive_path = Path(archive_filepath)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        return self.archive(self.nbc_root_dir, archive_path)

    def unpack_curator(self, archive_filepath: Path | str):
        self.nbc_root_dir.mkdir(parents=True, exist_ok=True)
        return self.unarchive(archive_filepath, self.nbc_root_dir)

    def compact_curator(self) -> bool:
        try:
            if self.mm_pkgs_dir.exists():
                shutil.rmtree(str(self.mm_pkgs_dir))
            if self.nbc_cache_dir.exists():
                shutil.rmtree(str(self.nbc_cache_dir))
            self.logger.debug("Curator compacted successfully")
            return True
        except Exception as e:
            return self.logger.exception(e, f"Failed to compact curator: {e}")
