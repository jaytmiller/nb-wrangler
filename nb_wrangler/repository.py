"""Repository management for cloning and updating notebook repositories."""

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from .config import WranglerConfigurable
from .logger import WranglerLoggable
from .environment import WranglerEnvable
from .constants import REPO_CLONE_TIMEOUT


class RepositoryManager(WranglerConfigurable, WranglerLoggable, WranglerEnvable):
    """Manages git repository operations for notebook collections."""

    def __init__(self, repos_dir: Path):
        super().__init__()
        self.repos_dir = repos_dir

    def run(self, *args, **keys):
        return self.env_manager.wrangler_run(*args, **keys)

    def handle_result(self, *args, **keys):
        return self.env_manager.handle_result(*args, **keys)

    def setup_repos(
        self,
        repo_urls: list[str],
        single_branch=False,
        repo_branches: Optional[dict[str, str | None]] = None,
    ) -> bool:
        """set up all specified repositories."""
        self.logger.debug(f"Setting up repos. urls={repo_urls}.")
        for repo_url in repo_urls:
            branch = repo_branches.get(repo_url) if repo_branches else None
            repo_path = self._setup_remote_repo(
                repo_url, single_branch=single_branch, branch=branch
            )
            if not repo_path:
                return False
        return True

    def _repo_path(self, repo_url: str) -> Path:
        """Get the path for a repository."""
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_name = repo_name.split("@")[0]
        return self.repos_dir / repo_name

    def _setup_remote_repo(
        self, repo_url: str, single_branch: bool = True, branch: Optional[str] = None
    ) -> Optional[Path]:
        """set up a remote repository by cloning or updating."""
        repo_path = self._repo_path(repo_url)
        if repo_path.exists():
            self.logger.info(f"Using existing local clone at {repo_path}")
            return repo_path
        else:
            try:
                return self._clone_repo(
                    repo_url, repo_path, single_branch=single_branch, branch=branch
                )
            except Exception as e:
                self.logger.exception(e, f"Failed to setup repository {repo_url}.")
                return None

    def _clone_repo(
        self,
        repo_url: str,
        repo_dir: Path,
        single_branch=True,
        branch: Optional[str] = None,
    ) -> Path:
        """Clone a new repository."""
        single_branch_arg = "--single-branch" if single_branch else ""
        branch_arg = f"--branch {branch}" if branch else ""
        clone_args = " ".join(filter(None, [single_branch_arg, branch_arg]))

        branch_msg = f" (branch: {branch})" if branch else ""
        self.logger.info(f"Cloning repository {repo_url}{branch_msg} to {repo_dir}.")
        if self.env_manager is None:
            raise RuntimeError("Environment manager not available")
        self.run(
            f"git clone {clone_args} {repo_url} {str(repo_dir)}",
            check=True,
            timeout=REPO_CLONE_TIMEOUT,
        )
        self.logger.info(f"Successfully cloned repository to {repo_dir}.")
        return repo_dir

    def delete_repos(self, urls: list[str]) -> bool:
        """Clean up cloned repositories."""
        try:
            for url in urls:
                path = self._repo_path(url)
                if path.exists():
                    self.logger.debug("Removing repo directory:", str(path))
                    shutil.rmtree(path)
                else:
                    self.logger.debug("Skipping delete for nonexistent:", str(path))
            remaining_contents = [str(obj) for obj in self.repos_dir.glob("*")]
            if not remaining_contents:
                self.logger.debug(
                    "Removing empty repos directory:", str(self.repos_dir)
                )
                self.repos_dir.rmdir()
            else:
                self.logger.debug(
                    "Skipping removal of non-empty repos directory:",
                    str(self.repos_dir),
                    "due remaining contents:",
                    remaining_contents,
                )
            return True
        except Exception as e:
            return self.logger.exception(e, "Error during repository deletion:")

    def is_clean(self, repo_root: str | Path) -> bool:
        stats: str = self.run("git status --porcelain", check=True, cwd=repo_root)
        stats = "clean" if stats == "" else "dirty"
        self.logger.debug(f"Repo '{repo_root}' status is: {stats}.")
        return stats == "clean"

    def branch_repo(
        self, repo_name: str, new_branch: str, ingest_branch: str = "origin/main"
    ) -> bool:
        repo_root = self.repos_dir / repo_name
        if not repo_root.exists():
            return self.logger.error(f"Can't branch non-existent repo {repo_name}.")
        if not self.is_clean(repo_root):
            return self.logger.error(f"Won't branch dirty repo {repo_name}.")
        self.logger.debug(
            f"Branching {repo_name} from {ingest_branch} to {new_branch}."
        )
        if not self.git_checkout(repo_name, ingest_branch):
            return False
        if not self.git_create_branch(repo_name, new_branch):
            return False
        return True

    def git_checkout(self, repo_name: str, branch: str) -> bool:
        repo_root = self.repos_dir / repo_name
        result = self.run(f"git checkout {branch}", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed checking out repo {repo_name} existing branch {branch}: ",
            f"Checked out repo {repo_name} existing branch {branch}.",
        )

    def git_create_branch(self, repo_name, new_branch):
        repo_root = self.repos_dir / repo_name
        result = self.run(f"git checkout -b {new_branch}", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed creating new branch {new_branch} of repo {repo_name}: ",
            f"Created new branch {new_branch} of repo {repo_name}.",
        )

    def git_add(self, repo_name: str, path_to_add: str | Path) -> bool:
        path_to_add = str(path_to_add)
        repo_root = self.repos_dir / repo_name
        result = self.run(f"git add {path_to_add}", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed adding {path_to_add} from {repo_name}: ",
            f"Added {path_to_add} to {repo_name}.",
        )

    def git_commit(self, repo_name: str, commit_msg: str) -> bool:
        repo_root = self.repos_dir / repo_name
        with tempfile.NamedTemporaryFile(mode="w+") as temp:
            temp.write(commit_msg)
            temp.flush()
            result = self.run(f"git commit -F {temp.name}", check=False, cwd=repo_root)
            return self.handle_result(
                result,
                f"Failed commiting {repo_name}: ",
                f"Commited {repo_name}.",
            )

    def git_push(self, repo_name: str, branch_name: str) -> bool:
        repo_root = self.repos_dir / repo_name
        result = self.run(f"git push origin {branch_name}", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed pushing repo {repo_name} branch {branch_name}: ",
            f"Pushed repo {repo_name} branch {branch_name}.",
        )

    def github_create_pr(
        self, repo_name: str, merge_to: str, title: str, body_msg: str
    ) -> bool:
        repo_root = self.repos_dir / repo_name
        with tempfile.NamedTemporaryFile(mode="w+") as temp:
            temp.write(body_msg)
            temp.flush()
            result = self.run(
                (
                    "gh",
                    "pr",
                    "create",
                    # "--base",
                    # merge_to,
                    "--no-maintainer-edit",
                    "--title",
                    "'" + title + "'",
                    "--body-file",
                    temp.name,
                ),
                check=False,
                cwd=repo_root,
            )
            return self.handle_result(
                result,
                f"Failed creating PR {title} for {repo_name}: ",
                f"Created PR {title} to {merge_to} for {repo_name}.",
            )

    def github_merge_pr(
        self, repo_name: str, merge_from: str, title: str, body_msg: str
    ) -> bool:
        repo_root = self.repos_dir / repo_name
        with tempfile.NamedTemporaryFile(mode="w+") as temp:
            temp.write(body_msg)
            temp.flush()
            result = self.run(
                (
                    "gh",
                    "pr",
                    "merge",
                    merge_from,
                    "--rebase",
                    "-t",
                    "'" + title + "'",
                    "--body-file",
                    temp.name,
                ),
                check=False,
                cwd=repo_root,
            )
            return self.handle_result(
                result,
                f"Failed merging PR {title} to {repo_name}: ",
                f"Merged PR {title} to {repo_name}.",
            )
