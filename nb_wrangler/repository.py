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
        floating_mode: bool = True,
        repo_refs: Optional[dict[str, str | None]] = None,
    ) -> dict[str, str]:
        """set up all specified repositories."""
        self.logger.debug(f"Setting up repos. urls={repo_urls}.")
        repo_states = {}
        for repo_url in repo_urls:
            ref = repo_refs.get(repo_url) if repo_refs else None
            repo_path = self._setup_remote_repo(
                repo_url,
                floating_mode=floating_mode,
                ref=ref,
            )
            if not repo_path:
                raise RuntimeError(f"Failed to setup repository {repo_url}")
            current_hash = self.get_hash(repo_path)
            if not current_hash:
                raise RuntimeError(f"Failed to get hash for repository {repo_url}")
            repo_states[repo_url] = current_hash
        return repo_states

    def _repo_path(self, repo_url: str) -> Path:
        """Get the path for a repository."""
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_name = repo_name.split("@")[0]
        return self.repos_dir / repo_name

    def _setup_remote_repo(
        self,
        repo_url: str,
        floating_mode: bool,
        ref: Optional[str] = None,
    ) -> Optional[Path]:
        """set up a remote repository by cloning or updating."""
        repo_path = self._repo_path(repo_url)
        if repo_path.exists():
            self.logger.info(f"Using existing local clone at {repo_path}")
            if floating_mode:
                self.logger.info(f"Floating mode: updating repo {repo_url}")
                self.run("git fetch", check=True, cwd=repo_path)
                ref_to_checkout = ref or "origin/main"  # a default
                self.run(f"git checkout {ref_to_checkout}", check=True, cwd=repo_path)
                if ref:
                    self.run("git pull", check=True, cwd=repo_path)  # pull updates
            else:  # locked mode
                if ref:
                    self.logger.info(
                        f"Locked mode: checking out ref {ref} for repo {repo_url}"
                    )
                    self.run("git fetch", check=True, cwd=repo_path)
                    self.run(f"git checkout {ref}", check=True, cwd=repo_path)
                else:
                    self.logger.warning(
                        f"Locked mode enabled, but no ref provided for {repo_url}. Using existing state."
                    )
            return repo_path
        else:
            try:
                repo_path = self._clone_repo(repo_url, repo_path, ref=ref)
                if not floating_mode and ref:
                    self.logger.info(
                        f"Locked mode: checking out ref {ref} for repo {repo_url}"
                    )
                    self.run(f"git checkout {ref}", check=True, cwd=repo_path)
                return repo_path
            except Exception as e:
                self.logger.exception(e, f"Failed to setup repository {repo_url}.")
                return None

    def _clone_repo(
        self,
        repo_url: str,
        repo_dir: Path,
        ref: Optional[str] = None,
    ) -> Path:
        """Clone a new repository."""
        # single_branch_arg is removed to allow checking out arbitrary commits
        branch_arg = f"--branch {ref}" if ref else ""
        clone_args = " ".join(filter(None, [branch_arg]))

        branch_msg = f" (ref: {ref})" if ref else ""
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

    def get_hash(self, repo_path: str | Path) -> Optional[str]:
        """Get the current commit hash of a repository."""
        if not self.is_clean(repo_path):
            self.logger.warning(
                f"Repo '{repo_path}' is dirty, hash may not be accurate."
            )
        result = self.run("git rev-parse HEAD", check=False, cwd=repo_path)
        if result.returncode == 0:
            return result.stdout.strip()
        self.logger.error(f"Failed to get git hash for repo {repo_path}")
        return None

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

    def git_remote_add(self, remote_name: str, remote_url: str) -> bool:
        repo_path = self._repo_path(remote_url)
        result = self.run(
            f"git remote add {remote_name} {remote_url}", check=False, cwd=repo_path
        )
        return self.handle_result(
            result,
            f"Failed adding remote {remote_name} = {remote_url} to {repo_path}: ",
            f"Added remote {remote_name} to {repo_path}.",
            error_func=self.logger.debug,
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

    def prepare_repository(self, repo_url: str, desired_ref: str) -> bool:
        """Ensure a repository is cloned and at the correct, clean ref."""
        self.logger.info(f"Preparing repository {repo_url} at ref {desired_ref}")
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_path = self._repo_path(repo_url)

        if not repo_path.exists():
            self.logger.info(f"Repository {repo_name} not found locally. Cloning...")
            return bool(self._clone_repo(repo_url, repo_path, ref=desired_ref))

        if not self.is_clean(repo_path):
            self.logger.warning(
                f"Repository '{repo_name}' has uncommitted local changes."
            )
            if self.config.overwrite_local_changes:
                self.logger.info(
                    f"Overwriting local changes in {repo_name} due to --overwrite-local-changes flag."
                )
                if not self.git_reset_hard(repo_name):
                    return False
            elif self.config.stash_local_changes:
                self.logger.info(
                    f"Stashing local changes in {repo_name} due to --stash-local-changes flag."
                )
                if not self.git_stash(repo_name):
                    return False
            else:
                while True:
                    prompt = f"Repo '{repo_name}' is dirty. [S]tash changes, [D]iscard changes, or [A]bort? (S/D/A): "
                    choice = input(prompt).upper()
                    if choice == "A":
                        self.logger.error("Operation aborted by user.")
                        return False
                    elif choice == "S":
                        if not self.git_stash(repo_name):
                            return False
                        break
                    elif choice == "D":
                        if not self.git_reset_hard(repo_name):
                            return False
                        break

        # Now the repo is clean, check if it's on the correct commit
        current_sha = self.get_hash(repo_path)
        target_sha = self.resolve_ref_to_sha(repo_name, desired_ref)

        if current_sha == target_sha:
            sha_info = f" ({target_sha[:7]})" if target_sha else ""
            self.logger.info(
                f"Repository {repo_name} is already at the desired ref {desired_ref}{sha_info}."
            )
            return True

        self.logger.info(f"Updating repository {repo_name} to ref {desired_ref}...")
        return self.git_checkout(repo_name, desired_ref)

    def git_stash(self, repo_name: str) -> bool:
        """Stash local changes in the given repository."""
        repo_root = self.repos_dir / repo_name
        self.logger.info(f"Stashing local changes in {repo_root}")
        result = self.run("git stash", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed to stash changes in {repo_name}: ",
            f"Stashed local changes in {repo_name}.",
        )

    def git_reset_hard(self, repo_name: str) -> bool:
        """Reset the repository, discarding all local changes."""
        repo_root = self.repos_dir / repo_name
        self.logger.warning(
            f"Discarding local changes in {repo_root} with 'git reset --hard HEAD'"
        )
        result = self.run("git reset --hard HEAD", check=False, cwd=repo_root)
        return self.handle_result(
            result,
            f"Failed to reset repository {repo_name}: ",
            f"Successfully reset {repo_name}, discarding local changes.",
        )

    def resolve_ref_to_sha(self, repo_name: str, ref: str) -> Optional[str]:
        """Resolve a git ref (branch, tag) to its specific commit SHA."""
        repo_root = self.repos_dir / repo_name
        self.logger.debug(f"Resolving ref '{ref}' to SHA in {repo_root}")
        # Fetch first to ensure the ref is available locally
        fetch_result = self.run("git fetch", check=False, cwd=repo_root)
        if fetch_result.returncode != 0:
            self.logger.error(f"Failed to fetch {repo_root} before resolving ref.")
            return None
        # Use rev-parse to get the commit SHA
        result = self.run(f"git rev-parse {ref}", check=False, cwd=repo_root)
        if result.returncode == 0:
            return result.stdout.strip()
        self.logger.error(f"Failed to resolve ref '{ref}' in repo {repo_name}")
        return None
