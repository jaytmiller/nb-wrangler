"""Docker registry interaction for pulling images and extracting specs."""

import subprocess
from pathlib import Path
from typing import Optional

from .config import WranglerConfigurable
from .logger import WranglerLoggable
from .environment import WranglerEnvable


class RegistryManager(WranglerConfigurable, WranglerLoggable, WranglerEnvable):
    """Manages interactions with Docker registries and images."""

    def __init__(self):
        super().__init__()

    def pull(self, image: str) -> bool:
        """Pull a Docker image from a registry."""
        self.logger.info(f"Pulling Docker image: {image}")
        result = self.env_manager.wrangler_run(
            ["docker", "pull", image],
            check=False,
            output_mode="uncaught"
        )
        return self.env_manager.handle_result(
            result,
            f"Failed to pull Docker image {image}.",
            f"Successfully pulled Docker image {image}."
        )

    def cat_spec(self, image: str, spec_path: Optional[str] = None) -> Optional[str]:
        """Extract and return the content of a spec file from a Docker image."""
        
        # If no path provided, try a list of common locations
        paths_to_try = [spec_path] if spec_path else ["/spec.yaml", "/nbw-wrangler-spec.yaml"]
        
        self.logger.info(f"Extracting spec from Docker image: {image}")

        # 1. Create a temporary container
        result = self.env_manager.wrangler_run(
            ["docker", "create", image, "/bin/true"], check=False, output_mode="separate"
        )
        if result.returncode != 0:
            self.logger.error(
                f"Failed to create temporary container from {image}: {result.stderr}"
            )
            return None

        container_id = result.stdout.strip()

        try:
            for path in paths_to_try:
                self.logger.debug(f"Attempting to extract {path}...")
                content = self._extract_file(container_id, path)
                if content:
                    return content
            
            self.logger.error(f"Could not find a wrangler spec in {image}. Tried paths: {paths_to_try}")
            return None

        finally:
            # 3. Remove the temporary container
            self.env_manager.wrangler_run(
                ["docker", "rm", container_id], check=False, output_mode="separate"
            )

    def _extract_file(self, container_id: str, path: str) -> Optional[str]:
        """Helper to extract a single file from a container."""
        try:
            cp_process = subprocess.Popen(
                ["docker", "cp", f"{container_id}:{path}", "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            tar_process = subprocess.Popen(
                ["tar", "xO"],
                stdin=cp_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, tar_stderr = tar_process.communicate()
            cp_stderr = cp_process.stderr.read().decode()
            cp_process.wait()

            if tar_process.returncode == 0 and cp_process.returncode == 0:
                return stdout
            
            self.logger.debug(f"Failed to extract {path}: cp_err={cp_stderr.strip()}, tar_err={tar_stderr.strip()}")
            return None

        except Exception as e:
            self.logger.debug(f"Exception extracting {path}: {e}")
            return None
