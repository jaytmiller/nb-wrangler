"""Tests for the --spi-image-test CLI switch and injector.image_test parameter handling."""

from pathlib import Path

import pytest

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.injector import SpiInjector


@pytest.fixture(autouse=True)
def setup_config(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("config")
    spec_file = Path(__file__).parent.parent / "specs/samples/tike-wrangler-k1.yaml"
    config = WranglerConfig(
        workflows=[],
        spec_file=str(spec_file),
        repos_dir=tmp_dir / "repos",
        output_dir=tmp_dir / "output",
        prod=True,
    )
    set_args_config(config)


class DummyRepoManager:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.repos_dir = repo_path.parent

    def _setup_remote_repo(self, repo_url, floating_mode=True, ref=None):
        return self.repo_path


class DummySpecManager:
    @property
    def deployment_name(self):
        return "test-deploy"

    @property
    def spec_id(self):
        return None

    @property
    def spi(self):
        return {}

    @property
    def image_name(self):
        return "test-image"


class DummyEnvManager:
    """Captures the result passed to handle_result and returns True."""

    def __init__(self):
        self.last_fail = None
        self.last_success = None

    def handle_result(self, result, fail, success=""):
        # Be tolerant of whatever is returned by repo_manager.run; treat non-None as success.
        if result is None:
            self.last_fail = fail
            return False
        self.last_success = success
        return True


class CapturingRepoManager(DummyRepoManager):
    """DummyRepoManager that records the command passed to run()."""

    def __init__(self, repo_path: Path):
        super().__init__(repo_path)
        self.captured_command = None

    def run(self, *args, **keys):
        # wrangler_run forwards (command, ...) so args[0] is the command.
        cmd = args[0] if args else keys.get("command")
        self.captured_command = list(cmd) if not isinstance(cmd, str) else [cmd]
        return object()  # truthy CompletedProcess-like sentinel


def _build_injector(tmp_path, repo_mgr):
    injector = SpiInjector(
        repo_manager=repo_mgr,
        spec_manager=DummySpecManager(),
    )
    injector.env_manager = DummyEnvManager()
    return injector


def test_image_test_no_params_builds_base_command(tmp_path: Path):
    repo_mgr = CapturingRepoManager(tmp_path / "repos")
    (tmp_path / "repos").mkdir(parents=True, exist_ok=True)
    injector = _build_injector(tmp_path, repo_mgr)

    ok = injector.image_test()
    assert ok is True
    # Base command: scripts/wrangler-run <deployment> image-test
    assert repo_mgr.captured_command == [
        "scripts/wrangler-run",
        "test-deploy",
        "image-test",
    ]


def test_image_test_forwards_params(tmp_path: Path):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True, exist_ok=True)
    repo_mgr = CapturingRepoManager(repos_dir)
    injector = _build_injector(tmp_path, repo_mgr)

    ok = injector.image_test(["--verbose", "--limit=5"])
    assert ok is True
    assert repo_mgr.captured_command == [
        "scripts/wrangler-run",
        "test-deploy",
        "image-test",
        "--verbose",
        "--limit=5",
    ]


def test_image_test_empty_params_uses_base_command(tmp_path: Path):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True, exist_ok=True)
    repo_mgr = CapturingRepoManager(repos_dir)
    injector = _build_injector(tmp_path, repo_mgr)

    ok = injector.image_test([])
    assert ok is True
    assert repo_mgr.captured_command == [
        "scripts/wrangler-run",
        "test-deploy",
        "image-test",
    ]


def test_wrangler_config_spi_image_test_defaults_to_none():
    """The WranglerConfig dataclass default for spi_image_test is None."""
    config = WranglerConfig(workflows=[])
    assert config.spi_image_test is None


def test_spi_image_test_string_split_into_params(tmp_path: Path):
    """A single whitespace-joined --spi-image-test string is split into params
    forwarded to the injector's image_test method for a nested argparse script."""
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True, exist_ok=True)
    repo_mgr = CapturingRepoManager(repos_dir)

    config = WranglerConfig(
        workflows=[],
        spec_file=str(
            Path(__file__).parent.parent / "specs/samples/tike-wrangler-k1.yaml"
        ),
        repos_dir=repos_dir,
        prod=True,
    )
    set_args_config(config)
    injector = _build_injector(tmp_path, repo_mgr)

    ok = injector.image_test(["--model=x", "--verbose"])
    assert ok is True
    assert repo_mgr.captured_command == [
        "scripts/wrangler-run",
        "test-deploy",
        "image-test",
        "--model=x",
        "--verbose",
    ]


def test_spi_image_test_string_split_helper():
    from nb_wrangler.config import WranglerConfig as WC

    assert WC._split_spi_image_test(None) is None
    assert WC._split_spi_image_test("") == []
    assert WC._split_spi_image_test("   ") == []
    assert WC._split_spi_image_test("--a --b=c") == ["--a", "--b=c"]
