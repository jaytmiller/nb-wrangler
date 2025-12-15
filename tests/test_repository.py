import subprocess
import pytest
from pathlib import Path

from nb_wrangler.repository import RepositoryManager
from nb_wrangler.environment import EnvironmentManager

@pytest.fixture
def env_manager(tmp_path):
    return EnvironmentManager(wrangler_dir=tmp_path / "wrangler")

@pytest.fixture
def repo_manager(tmp_path, env_manager):
    manager = RepositoryManager(repos_dir=tmp_path / "repos")
    manager.env_manager = env_manager
    return manager

@pytest.fixture
def git_repo(tmp_path):
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    (repo_path / "test.txt").write_text("initial commit")
    subprocess.run(["git", "add", "test.txt"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_path, check=True)
    first_commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_path).strip().decode()

    (repo_path / "test.txt").write_text("second commit")
    subprocess.run(["git", "add", "test.txt"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "second commit"], cwd=repo_path, check=True)
    second_commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_path).strip().decode()

    return str(repo_path), first_commit_hash, second_commit_hash

def test_setup_repo_with_commit_hash(repo_manager, git_repo):
    repo_url, first_commit, second_commit = git_repo
    repo_path = repo_manager._setup_remote_repo(repo_url, floating_mode=False, ref=first_commit)

    assert repo_path is not None
    assert repo_manager.get_hash(repo_path) == first_commit

    # Now, try to "update" to the same commit. This should not fail.
    repo_path = repo_manager._setup_remote_repo(repo_url, floating_mode=True, ref=first_commit)
    assert repo_path is not None
    assert repo_manager.get_hash(repo_path) == first_commit

    # And updating to a different commit should also work
    repo_path = repo_manager._setup_remote_repo(repo_url, floating_mode=True, ref=second_commit)
    assert repo_path is not None
    assert repo_manager.get_hash(repo_path) == second_commit
