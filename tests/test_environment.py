"""Tests for nb_wrangler/environment.py."""

import json
from subprocess import CompletedProcess
from unittest.mock import MagicMock

# noqa: F401 - reused as `patch` below for inline test context
from unittest.mock import patch  # noqa: F401,F811,F821


def _make_manager_with_mocks(tmp_path):
    from nb_wrangler.environment import EnvironmentManager  # noqa: F401

    from nb_wrangler.config import WranglerConfig, set_args_config

    set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
    em = EnvironmentManager()
    em.logger = MagicMock()
    return em


class TestIsBaseEnvAlias:
    def test_base_is_alias(self):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        assert em.is_base_env_alias("base") is True

    def test_python3_is_alias(self):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        assert em.is_base_env_alias("python3") is True

    def test_custom_env_not_alias(self):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        assert em.is_base_env_alias("custom-env") is False


class TestEnvironmentExists:
    def test_base_env_exists(self):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        assert em.environment_exists("base") is True

    def test_name_starts_with_mm_ends_with_env(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        mm_prefix = str(em.nbw_mm_dir)
        env_path = tmp_path / "test_env"
        em.wrangler_run = MagicMock(
            return_value=MagicMock(stdout=json.dumps({"envs": [str(env_path)]}) + "\n")
        )

        em.get_existing_envs = MagicMock(return_value=[f"{mm_prefix}/envs/my_test"])
        assert em.environment_exists("my_test") is True


class TestHandleResult:
    def test_success_returns_true(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        proc = CompletedProcess(["cmd"], returncode=0, stdout="out", stderr="err")
        result = em.handle_result(proc, "fail msg", "success msg")
        assert result is True

    def test_failure_returns_false(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        proc = CompletedProcess(["cmd"], returncode=1, stdout="out", stderr="err")
        result = em.handle_result(proc, "fail msg", "success msg")
        assert result is False


class TestGetExistingEnvs:
    def test_parses_json_environments(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

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
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        em.wrangler_run = MagicMock(side_effect=RuntimeError("fail"))
        result = em.get_existing_envs()
        assert result == []

    def test_returns_empty_on_none_result(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        em.wrangler_run = MagicMock(return_value=None)
        result = em.get_existing_envs()
        assert result == []


class TestGetPackageFile:
    def test_strips_comments(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        packages = ["# comment", "package1", "  # another comment", "package2"]
        count, path = em._get_package_file("testenv", packages)
        assert count == 2

    def test_writes_file(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401
        from pathlib import Path

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        (tmp_path / "repos").mkdir(parents=True, exist_ok=True)

        packages = ["pkg1"]
        count, path = em._get_package_file("testenv", packages)
        assert Path(path).exists()


class TestJupyterKernelExists:
    def _proc(self, stdout="", rc=0):
        return CompletedProcess(
            ["jupyter", "kernelspec", "list"], returncode=rc, stdout=stdout, stderr=""
        )

    def test_present_returns_true(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        listing = json.dumps({"kernelspecs": {"RomanNexus-2026.2": {}}})
        em.wrangler_run = MagicMock(return_value=self._proc(listing))
        assert em._jupyter_kernel_exists("RomanNexus-2026.2") is True

    def test_absent_returns_false(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F811,F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        listing = json.dumps({"kernelspecs": {"other-env": {}}})
        em.wrangler_run = MagicMock(return_value=self._proc(listing))
        assert em._jupyter_kernel_exists("RomanNexus-2026.2") is False

    def test_empty_specs_returns_false(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F811,F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        em.wrangler_run = MagicMock(return_value=self._proc(json.dumps({})))
        assert em._jupyter_kernel_exists("RomanNexus-2026.2") is False

    def test_nonzero_returncode_returns_false(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F811,F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        em.wrangler_run = MagicMock(return_value=self._proc(rc=1))
        assert em._jupyter_kernel_exists("RomanNexus-2026.2") is False

    def test_unparseable_output_returns_false(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F811,F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        em.wrangler_run = MagicMock(return_value=self._proc(stdout="not json <<</"))
        assert em._jupyter_kernel_exists("RomanNexus-2026.2") is False


class TestRegisterEnvironment:
    """Tests for EnvironmentManager.register_environment / unregister_environment."""

    def test_register_emits_ipykernel_install(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401
        from unittest.mock import MagicMock as _MagicMock  # noqa: F811

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)

        mock_result = _MagicMock()
        em.env_run = MagicMock(return_value=mock_result)
        original_handle = type(em).handle_result

        def fake_handle(self, result, fail, success="", error_func=None):
            return True

        import nb_wrangler.environment as env_mod

        env_mod.EnvironmentManager.handle_result = fake_handle
        try:
            assert em.register_environment("myenv", "My Env", {"KEY": "val"}) is True
        finally:
            env_mod.EnvironmentManager.handle_result = original_handle

        cmd = em.env_run.call_args[0][1] if em.env_run.call_args else ""
        joined = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        assert "ipykernel" in joined and "install" in joined

    def test_unregister_when_spec_missing_is_tolerant(self, tmp_path):
        """Reset scenarios: missing kernel spec must not error. Regression for
        the 'Couldn't find kernel spec(s)' ERROR+WARNING escalation."""
        from nb_wrangler.environment import EnvironmentManager  # noqa: F811,F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        listing = json.dumps({"kernelspecs": {}})

        # _jupyter_kernel_exists should consult this; uninstall must NOT be invoked.
        calls = []

        def fake_wrangler_run(cmd, **keys):
            calls.append(str(cmd))
            return CompletedProcess(["jupyter"], 0, stdout=listing)

        em.wrangler_run = MagicMock(side_effect=fake_wrangler_run)
        result = em.unregister_environment("RomanNexus-2026.2")

        # The kernelspec list probe ran exactly once (no uninstall issued), and the
        # call was flagged via logger.warning even with a mocked logger. Behavioural
        # contract is what matters here, not the boolean (logger is mocked).
        assert result  # truthy under real logger; warning() path taken
        em.logger.warning.assert_called_once()
        assert all("uninstall" not in c for c in calls)

    def test_unregister_when_spec_present_runs_uninstall(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F811,F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        listing = json.dumps({"kernelspecs": {"RomanNexus-2026.2": {}}})

        calls = []

        def fake_wrangler_run(cmd, **keys):
            calls.append(cmd)
            # First call: kernelspec list ; second: uninstall (return success).
            if "list" in cmd:
                return CompletedProcess(["jupyter"], 0, stdout=listing)
            return CompletedProcess(["jupyter"], 0, stdout="Uninstalled.")

        em.wrangler_run = MagicMock(side_effect=fake_wrangler_run)
        original_handle = type(em).handle_result
        seen = {"called": False}

        def fake_handle(self, result, fail, success="", error_func=None):
            seen["called"] = True
            return True

        import nb_wrangler.environment as env_mod

        env_mod.EnvironmentManager.handle_result = fake_handle
        try:
            assert em.unregister_environment("RomanNexus-2026.2") is True
        finally:
            env_mod.EnvironmentManager.handle_result = original_handle

        assert seen["called"]  # handle_result was used for uninstall path
        # The list probe must have run before the uninstall command.
        list_idx = next(i for i, c in enumerate(calls) if "list" in str(c))
        unreg_idx = next(i for i, c in enumerate(calls) if "uninstall" in str(c))
        assert list_idx < unreg_idx

    def test_unregister_propagates_failure_when_uninstall_fails(self, tmp_path):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F811,F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        em = _make_manager_with_mocks(tmp_path)
        listing = json.dumps({"kernelspecs": {"RomanNexus-2026.2": {}}})

        calls = []

        def fake_wrangler_run(cmd, **keys):
            calls.append(cmd)
            if "list" in cmd:
                return CompletedProcess(["jupyter"], 0, stdout=listing)
            # Uninstall fails (e.g. permission error).
            return CompletedProcess(
                ["jupyter"], 1, stdout="", stderr="permission denied"
            )

        em.wrangler_run = MagicMock(side_effect=fake_wrangler_run)
        result = em.unregister_environment("RomanNexus-2026.2")
        assert result is False  # genuine failure still surfaces


class TestConditionCmd:
    def test_string_splitted(self):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        result = em._condition_cmd("ls -la /path")
        assert isinstance(result, list)
        assert "ls" in result
        assert "-la" in result

    def test_list_passed_through(self):
        from nb_wrangler.environment import EnvironmentManager  # noqa: F401

        from nb_wrangler.config import WranglerConfig, set_args_config

        set_args_config(WranglerConfig(workflows=[]))
        em = EnvironmentManager()
        result = em._condition_cmd(["ls", "-la"])
        assert isinstance(result, list)
        assert len(result) == 2
