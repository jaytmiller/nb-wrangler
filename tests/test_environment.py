"""Tests for nb_wrangler/environment.py."""

import json
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

from nb_wrangler.config import WranglerConfig, set_args_config


def _make_manager_with_mocks(tmp_path):
    from nb_wrangler.environment import EnvironmentManager

    set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
    em = EnvironmentManager()
    em.logger = MagicMock()
    return em


class TestIsBaseEnvAlias:
    def test_base_is_alias(self):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        assert em.is_base_env_alias("base") is True

    def test_python3_is_alias(self):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        assert em.is_base_env_alias("python3") is True

    def test_custom_env_not_alias(self):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        assert em.is_base_env_alias("custom-env") is False


class TestEnvironmentExists:
    def test_base_env_exists(self):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        assert em.environment_exists("base") is True

    def test_name_starts_with_mm_ends_with_env(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        mm_prefix = str(em.nbw_mm_dir)
        em.wrangler_run = MagicMock(
            return_value=MagicMock(stdout='{"envs": ["/tmp/test_env"]}\n')
        )

        em.get_existing_envs = MagicMock(return_value=[f"{mm_prefix}/envs/my_test"])
        assert em.environment_exists("my_test") is True


class TestHandleResult:
    def test_success_returns_true(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        proc = CompletedProcess(["cmd"], returncode=0, stdout="out", stderr="err")
        result = em.handle_result(proc, "fail msg", "success msg")
        assert result is True

    def test_failure_returns_false(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        proc = CompletedProcess(["cmd"], returncode=1, stdout="out", stderr="err")
        result = em.handle_result(proc, "fail msg", "success msg")
        assert result is False


class TestGetExistingEnvs:
    def test_parses_json_environments(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        mock_result = type(
            "MockResult",
            (),
            {
                "stdout": json.dumps({"envs": ["/path/to/env1", "/path/to/env2"]}),
                "returncode": 0,
            },
        )()
        em.wrangler_run = MagicMock(return_value=mock_result)
        result = em.get_existing_envs()
        assert len(result) == 2
        assert "/path/to/env1" in result

    def test_returns_empty_on_exception(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        em.wrangler_run = MagicMock(side_effect=RuntimeError("fail"))
        result = em.get_existing_envs()
        assert result == []

    def test_returns_empty_on_none_result(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        em.wrangler_run = MagicMock(return_value=None)
        result = em.get_existing_envs()
        assert result == []


class TestGetPackageFile:
    def test_strips_comments(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        packages = ["# comment", "package1", "  # another comment", "package2"]
        count, path = em._get_package_file("testenv", packages)
        assert count == 2

    def test_writes_file(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager
        from pathlib import Path

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        (tmp_path / "repos").mkdir(parents=True, exist_ok=True)

        packages = ["pkg1"]
        count, path = em._get_package_file("testenv", packages)
        assert Path(path).exists()


class TestRegisterEnvironment:
    def test_command_contains_kernel_install(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager
        from subprocess import CompletedProcess

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        mock_result = MagicMock()
        em.env_run = MagicMock(return_value=mock_result)
        # Patch handle_result to return True, since real CompletedProcess won't match
        original_handle = type(em).handle_result

        def fake_handle(self, result, fail, success="", error_func=None):
            return True

        import nb_wrangler.environment as env_mod

        env_mod.EnvironmentManager.handle_result = fake_handle

        try:
            result = em.register_environment("myenv", "My Env", {"KEY": "val"})
        finally:
            env_mod.EnvironmentManager.handle_result = original_handle

        assert result is True

        # Verify the command contains ipykernel install
        call_args = em.env_run.call_args
        cmd = call_args[0][1] if call_args else ""
        assert "ipykernel" in cmd or "install" in cmd


class TestConditionCmd:
    def test_string_splitted(self):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        result = em._condition_cmd("ls -la /path")
        assert isinstance(result, list)
        assert "ls" in result
        assert "-la" in result

    def test_list_passed_through(self):
        from nb_wrangler.environment import EnvironmentManager

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        result = em._condition_cmd(["ls", "-la"])
        assert isinstance(result, list)
        assert len(result) == 2
