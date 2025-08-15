"""Repository management for cloning and updating notebook repositories."""

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from .logger import CuratorLogger
from .environment import EnvironmentManager
from .constants import REPO_CLONE_TIMEOUT


class RepositoryManager:
    """Manages git repository operations for notebook collections."""

    def __init__(
        self,
        logger: CuratorLogger,
        repos_dir: Path,
        env_manager: EnvironmentManager | None = None,
    ):
        self.repos_dir = repos_dir
        self.logger = logger
        self.env_manager = env_manager

    def run(self, *args, **keys):
        return self.env_manager.curator_run(*args, **keys)

    def handle_result(self, *args, **keys):
        return self.env_manager.handle_result(*args, **keys)

    def setup_repos(self, repo_urls: list[str]) -> bool:
        """set up all specified repositories."""
        self.logger.debug(f"Setting up repos. urls={repo_urls}.")
        for repo_url in repo_urls:
            repo_path = self._setup_remote_repo(repo_url)
            if not repo_path:
                return False
        return True

    def _repo_path(self, repo_url: str) -> Path:
        """Get the path for a repository."""
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        return self.repos_dir / repo_name

    def _setup_remote_repo(self, repo_url: str) -> Optional[Path]:
        """set up a remote repository by cloning or updating."""
        repo_path = self._repo_path(repo_url)
        if repo_path.exists():
            self.logger.info(f"Using existing local clone at {repo_path}")
            return repo_path
        else:
            try:
                return self._clone_repo(repo_url, repo_path)
            except Exception as e:
                self.logger.exception(e, f"Failed to setup repository {repo_url}.")
                return None

    def _clone_repo(self, repo_url: str, repo_dir: Path) -> Path:
        """Clone a new repository."""
        self.logger.info(f"Cloning repository {repo_url} to {repo_dir}.")
        if self.env_manager is None:
            raise RuntimeError("Environment manager not available")
        self.run(
            f"git clone --single-branch {repo_url} {str(repo_dir)}",
            check=True,
            timeout=REPO_CLONE_TIMEOUT,
        )
        self.logger.info(f"Successfully cloned repository to {repo_dir}.")
        return repo_dir

    def delete_repos(self) -> bool:
        """Clean up cloned repositories."""
        try:
            if self.repos_dir.exists():
                self.logger.info(f"Deleting repository directory: {self.repos_dir}.")
                shutil.rmtree(self.repos_dir)
            return True
        except Exception as e:
            return self.logger.exception(e, "Error during repository deletion.")

    def is_clean(self, repo_root: str | Path) -> bool:
        stats: str = self.run("git status --porcelain", check=True, cwd=repo_root)
        stats = "clean" if stats == "" else "dirty"
        self.logger.debug(f"Repo '{repo_root}' status is: {stats}.")
        return stats == "clean"

    def branch_repo(
        self, repo_name: str, new_branch: str, source_branch: str = "origin/main"
    ) -> bool:
        repo_root = self.repos_dir / repo_name
        if not repo_root.exists():
            return self.logger.error(f"Can't branch non-existent repo {repo_name}.")
        if not self.is_clean(repo_root):
            return self.logger.error(f"Won't branch dirty repo {repo_name}.")
        result = self.run(f"git checkout {source_branch}", cwd=repo_root)
        if not self.handle_result(
            result,
            f"Failed checking out source branch {source_branch} of repo {repo_name}: ",
        ):
            return False
        result = self.run(f"git checkout -b {new_branch}", cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed creating new branch {new_branch} of repo {repo_name}: ",
            f"Created new branch {new_branch} of repo {repo_name}.",
        )

    def add_dir(self, repo_name: str, dir_to_add: str) -> bool:
        repo_root = self.repos_dir / repo_name
        result = self.run(f"git add {dir_to_add}", cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed adding {dir_to_add}: ",
        )

    def commit(self, repo_name: str, commit_msg: str) -> bool:
        repo_root = self.repos_dir / repo_name
        with tempfile.NamedTemporaryFile(mode="w+") as temp:
            temp.write(commit_msg)
            temp.flush()
            result = self.run(f"git commit -F {temp.name}", cwd=repo_root)
            return self.handle_result(
                result,
                f"Failed commiting {repo_name}: ",
            )
