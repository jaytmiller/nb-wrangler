"""Docker registry interaction for pulling images and extracting specs."""

import subprocess
import fnmatch
from typing import Optional

import requests

from .config import WranglerConfigurable
from .logger import WranglerLoggable
from .environment import WranglerEnvable
from .constants import DEFAULT_REGISTRY, DEFAULT_PROJECT


class RegistryManager(WranglerConfigurable, WranglerLoggable, WranglerEnvable):
    """Manages interactions with Docker registries and images."""

    def __init__(self):
        super().__init__()

    def pull(self, image: str) -> bool:
        """Pull a Docker image from a registry."""
        image = self.resolve_image(image, preferred_prefix="nbw_")
        self.logger.info(f"Pulling Docker image: {image}")
        result = self.env_manager.wrangler_run(
            ["docker", "pull", image], check=False, output_mode="uncaught"
        )
        return self.env_manager.handle_result(
            result,
            f"Failed to pull Docker image {image}.",
            f"Successfully pulled Docker image {image}.",
        )

    def cat_spec(self, image: str, spec_path: Optional[str] = None) -> Optional[str]:
        """Extract and return the content of a spec file from a Docker image."""
        image = self.resolve_image(image, preferred_prefix="nbs_")

        # If no path provided, try a list of common locations
        paths_to_try = (
            [spec_path] if spec_path else ["/spec.yaml", "/nbw-wrangler-spec.yaml"]
        )

        self.logger.info(f"Extracting spec from Docker image: {image}")

        # 1. Create a temporary container
        result = self.env_manager.wrangler_run(
            ["docker", "create", image, "/bin/true"],
            check=False,
            output_mode="separate",
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

            self.logger.error(
                f"Could not find a wrangler spec in {image}. Tried paths: {paths_to_try}"
            )
            return None

        finally:
            # 3. Remove the temporary container
            self.env_manager.wrangler_run(
                ["docker", "rm", container_id], check=False, output_mode="separate"
            )

    def resolve_image(self, shorthand: str, preferred_prefix: str = "") -> str:
        """Resolve a shorthand image name or tag to a full URI.

        Examples:
            _40 -> ghcr.io/spacetelescope/nb-wrangler:nbw_*_40
            RomanNexus*_40 -> ghcr.io/spacetelescope/nb-wrangler:nbw_RomanNexus*_40
            myorg/myproj:tag -> ghcr.io/myorg/myproj:tag
        """
        if not shorthand:
            return ""

        # If it looks like a full URI (has protocol or registry with port/multiple components and a tag), return as is
        if "://" in shorthand or (shorthand.count("/") >= 2 and ":" in shorthand):
            return shorthand

        registry = DEFAULT_REGISTRY
        project = DEFAULT_PROJECT
        tag_pattern = shorthand

        # If it contains a colon, it's [project]:[tag] or [registry]/[project]:[tag]
        if ":" in shorthand:
            path, tag_pattern = shorthand.split(":", 1)
            if "/" in path:
                parts = path.split("/")
                # If the first part has a dot, it's likely a registry (e.g., ghcr.io, docker.io)
                if "." in parts[0] or len(parts) > 2:
                    registry = parts[0]
                    project = "/".join(parts[1:])
                else:
                    project = path
            else:
                # If it's just a single name, assume it's the project name under the default org
                if "/" in project:
                    project = f"{project.split('/')[0]}/{path}"
                else:
                    project = path

        # If it's a glob or a suffix (starts with _), or we just want to expand it
        if (
            "*" in tag_pattern
            or "?" in tag_pattern
            or tag_pattern.startswith("_")
            or (not ":" in shorthand and preferred_prefix)
        ):
            try:
                tags = self._list_tags(registry, project)
            except Exception as e:
                self.logger.debug(f"Failed to list tags for {registry}/{project}: {e}")
                tags = []

            if tags:
                pattern = tag_pattern
                if tag_pattern.startswith("_"):
                    pattern = "*" + tag_pattern

                # Try with preferred prefix first
                matches = []
                if preferred_prefix and not tag_pattern.startswith(preferred_prefix):
                    prefix_pattern = preferred_prefix + pattern
                    matches = [t for t in tags if fnmatch.fnmatch(t, prefix_pattern)]

                if not matches:
                    matches = [t for t in tags if fnmatch.fnmatch(t, pattern)]

                if matches:
                    # Sort to get the latest (usually highest run number or date)
                    matches.sort()
                    tag = matches[-1]
                    self.logger.info(f"Resolved shorthand '{shorthand}' to tag '{tag}'")
                    return f"{registry}/{project}:{tag}"

        # Fallback to literal if no matches or not a glob
        # If it didn't have a registry/project, add them
        if ":" not in shorthand:
            return f"{registry}/{project}:{shorthand}"
        return f"{registry}/{project}:{tag_pattern}"

    def _list_tags(self, registry: str, project: str) -> list[str]:
        """List tags for a repository in a registry."""
        if registry == "ghcr.io":
            return self._list_ghcr_tags(project)
        # Add support for other registries if needed
        return []

    def _list_ghcr_tags(self, repository: str) -> list[str]:
        """List tags from GHCR using the V2 API."""
        # Public images on GHCR can be listed by getting a temporary token
        token_url = f"https://ghcr.io/token?scope=repository:{repository}:pull"
        resp = requests.get(token_url, timeout=10)
        resp.raise_for_status()
        token = resp.json().get("token")

        tags_url = f"https://ghcr.io/v2/{repository}/tags/list"
        resp = requests.get(
            tags_url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        resp.raise_for_status()
        return resp.json().get("tags", [])


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
            cp_stderr = cp_process.stderr.read().decode() if cp_process.stderr else ""
            cp_process.wait()

            if tar_process.returncode == 0 and cp_process.returncode == 0:
                return stdout

            self.logger.debug(
                f"Failed to extract {path}: cp_err={cp_stderr.strip()}, tar_err={tar_stderr.strip()}"
            )
            return None

        except Exception as e:
            self.logger.debug(f"Exception extracting {path}: {e}")
            return None
