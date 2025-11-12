"""Requirements compilation and dependency resolution."""

import sys
from pathlib import Path

from .config import WranglerConfigurable
from .logger import WranglerLoggable
from .environment import WranglerEnvable
from .constants import TARGET_PACKAGES, PIP_COMPILE_TIMEOUT
from .utils import get_yaml, yaml_dumps


class RequirementsCompiler(WranglerConfigurable, WranglerLoggable, WranglerEnvable):
    """Compiles and resolves package requirements."""

    def __init__(
        self,
        python_path: str = sys.executable,
        python_version: str = "3.11",
    ):
        super().__init__()
        self.python_path = python_path
        self.python_version = python_version

    def find_requirements_files(self, notebook_paths: list[str]) -> list[Path]:
        """Find requirements.txt files in notebook directories."""
        requirements_files = []
        notebook_dirs = {Path(nb_path).parent for nb_path in notebook_paths}
        for dir_path in notebook_dirs:
            req_file = dir_path / "requirements.txt"
            if req_file.exists():
                requirements_files.append(req_file)
                self.logger.debug(f"Found requirements file: {req_file}")
        self.logger.info(
            f"Found {len(requirements_files)} notebook requirements.txt files."
        )
        return requirements_files

    def compile_requirements(
        self,
        requirements_files: list[Path],
        output_path: Path,
        use_hashes: bool = False,
    ) -> bool:
        """Compile requirements files into pinned versions,  outputs
        the result to a file at `output_path` and then loads the
        output and returns a list of package versions for insertion
        into other commands and specs.
        """
        if not requirements_files:
            return self.logger.warning("No requirements files to compile.")
        self.logger.info(
            "Compiling combined pip requirements to determine package versions "
            "adding hashes."
            if use_hashes
            else "w/o hashes."
        )
        if not self._run_uv_compile(output_path, requirements_files, use_hashes):
            self.logger.error(
                "========== Failed compiling combined pip requirements =========="
            )
            return self.logger.error(self.annotated_requirements(requirements_files))
        package_versions = self.read_package_lines(output_path)
        self.logger.info(
            f"Compiled combined pip requirements to {len(package_versions)} package versions."
        )
        return True

    def _run_uv_compile(
        self,
        output_file: Path,
        requirements_files: list[Path],
        use_hashes: bool = False,
    ) -> bool:
        """Run uv pip compile command to resolve pip package constraints."""
        hash_sw = "--generate-hashes" if use_hashes else ""
        cmd = (
            f"uv pip compile --quiet --output-file {str(output_file)} --python {self.python_path}"
            + f" --python-version {self.python_version} --universal {hash_sw} "
            + "--no-header --annotate --constraints"
        )
        for f in requirements_files:
            cmd += " " + str(f)
        result = self.env_manager.wrangler_run(
            cmd, check=False, timeout=PIP_COMPILE_TIMEOUT
        )
        return self.env_manager.handle_result(result, "uv pip compile failed:")

    def read_package_versions(self, requirements_files: list[Path]) -> list[str]:
        """Read package versions from a list of requirements files omitting blank
        and comment lines.
        """
        package_versions = []
        for req_file in sorted(requirements_files):
            lines = self.read_package_lines(req_file)
            package_versions.extend(lines)
        return sorted(package_versions)

    def read_package_lines(self, requirements_file: Path) -> list[str]:
        """Read package lines from requirements file omitting blank and comment lines.
        Should work with most forms of requirements.txt file,
        input or compiled,  and reduce it to a pure list of package versions.
        """
        lines = []
        with open(requirements_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith(("#", "--hash")):
                    lines.append(line)
        return sorted(lines)

    def annotated_requirements(self, requirements_files: list[Path]) -> str:
        """Create an annotated input requirements listing to correlate version
        constraints with the notebooks which impose them,  primarily as an aid
        for direct conflict resolution.   Strictly speaking this is a WIP since
        without compiling individual notebook requirements first dependencies
        are not included which can be where the real conflicts occur without
        necessarily a common root import.
        """
        result: list[tuple[str, str]] = []
        for req_file in sorted(requirements_files):
            lines = self.read_package_lines(req_file)
            result.extend((pkg, str(req_file)) for pkg in lines)  # note difference
        result = sorted(result)
        return "\n".join(f"{pkg:<20}  : {path:<55}" for pkg, path in result)

    def generate_target_mamba_spec(
        self, kernel_name: str, dependencies: list[str], use_hashes: bool = False
    ) -> str | bool:
        """Generate mamba environment specification and return dict for YAML."""
        try:
            self.logger.debug(
                "Generating spec for empty mamba environment " "using hashes."
                if use_hashes
                else "without hashes."
            )
            return self._generate_mamba_spec_core(kernel_name, dependencies, use_hashes)
        except Exception as e:
            return self.logger.exception(
                e, f"Failed generating spec for empty mamba environment: {e}:"
            )

    def _generate_mamba_spec_core(
        self, kernel_name: str, dependencies_in: list[str], use_hashes: bool = False
    ) -> str:
        """Uncaught core processing of generate_mamba_spec."""
        dependencies = [
            f"python={self.python_version}" if self.python_version else "python",
        ]
        dependencies += TARGET_PACKAGES
        dependencies += dependencies_in
        dependencies = sorted(list(set(dependencies)))
        mamba_spec = {
            "name": kernel_name,
            "channels": ["conda-forge"],
            "dependencies": dependencies,
        }
        self.logger.debug(
            "Generated mamba_spec:", "\n" + self.logger.pformat(mamba_spec)
        )
        return yaml_dumps(mamba_spec)

    def write_mamba_spec_file(self, filepath: Path, mamba_spec: dict) -> bool:
        """Write mamba spec dictionary to YAML file."""
        try:
            with filepath.open("w+") as f:
                get_yaml().dump(mamba_spec, f)
        except Exception as e:
            return self.logger.exception(e, f"Failed writing mamba spec {filepath}")
        self.logger.debug(f"Wrote mamba spec to '{filepath}'")
        return True

    def write_pip_requirements_file(
        self, filepath: str, package_versions: list
    ) -> bool:
        """Write package versions to pip requirements file."""
        try:
            with Path(filepath).open("w+") as f:
                for package_version in package_versions:
                    f.write(f"{package_version}\n")
        except Exception as e:
            return self.logger.exception(
                e, f"Failed writing pip requirements to '{filepath}'."
            )
        self.logger.debug(f"Wrote pip target env package versions to '{filepath}'")
        return True
