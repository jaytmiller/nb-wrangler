"""Tests for hubenv export, status, doctor (Phase 10)."""

import json
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.utils import yaml_dumps


@pytest.fixture(autouse=True)
def _set_config(tmp_path):
    """Ensure a WranglerConfig is set for all tests."""
    set_args_config(
        WranglerConfig(
            workflows=[],
            spec_file="",
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
        )
    )


def _patch_nbw_root(tmp_path):
    """Patch NBW_ROOT in hubenv.config."""
    return patch("nb_wrangler.hubenv.config.NBW_ROOT", tmp_path)


def _patch_list_kernelspecs(return_value=None):
    """Patch _list_kernelspecs to return a known dict."""
    return patch(
        "nb_wrangler.hubenv.status.list_kernelspecs", return_value=return_value or {}
    )


def _default_check(key: str) -> dict:
    """Return a default passing check result for *key*."""
    return {"check": key, "pass": True, "detail": "ok", "hint": ""}


def _all_checks_context(**overrides):
    """Return an ExitStack that patches all doctor checks.

    Pass keyword args to override default return values, e.g.
    ``_all_checks_context(mamba={"pass": False, ...})`` makes only
    the mamba check fail while the others pass.
    """
    stack = ExitStack()
    patches = [
        ("nb_wrangler.hubenv.doctor.check_mamba_availability", "mamba"),
        ("nb_wrangler.hubenv.doctor.check_pantry_writability", "pantry"),
        ("nb_wrangler.hubenv.doctor.check_efs_mount", "efs"),
        ("nb_wrangler.hubenv.doctor.check_kernel_json_sanity", "kernel"),
    ]
    for target, key in patches:
        stack.enter_context(
            patch(target, return_value=overrides.get(key, _default_check(key)))
        )
    return stack


def _make_spec(name="demo", with_pip=True):
    """Create a mamba spec dict."""
    deps = ["python=3.11", "pip"]
    if with_pip:
        deps.append({"pip": ["numpy", "pandas"]})
    return {
        "name": name,
        "channels": ["conda-forge"],
        "dependencies": deps,
    }


def _write_spec(tmp_path, name, spec):
    """Write a spec file to the expected location."""
    spec_path = tmp_path / "envs" / name / ".hubenv-spec.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(yaml_dumps(spec))
    return spec_path


# ---------------------------------------------------------------------------
# parser tests
# ---------------------------------------------------------------------------


class TestParser:
    """Tests for argparse parser structure for export/status/doctor."""

    def test_parses_export(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["export", "demo", "--to-requirements", "-o", "-"])
        assert args.command == "export"
        assert args.name == "demo"
        assert args.to_requirements is True
        assert args.output == "-"

    def test_parses_export_default_output(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["export", "demo"])
        assert args.output == "-"

    def test_parses_status(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["status", "--format", "json"])
        assert args.command == "status"
        assert args.format == "json"

    def test_parses_doctor(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["doctor", "--format", "json"])
        assert args.command == "doctor"
        assert args.format == "json"

    def test_export_format_mutually_exclusive(self):
        from nb_wrangler.hubenv.cli import build_parser

        parser = build_parser()
        try:
            parser.parse_args(
                ["export", "demo", "--to-mamba-spec", "--to-requirements"]
            )
        except SystemExit:
            return
        raise AssertionError("Expected SystemExit for conflicting format flags")


# ---------------------------------------------------------------------------
# export tests
# ---------------------------------------------------------------------------


class TestExport:
    """Tests for hubenv export."""

    def test_export_to_mamba_spec_stdout(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        spec = _make_spec()
        _write_spec(tmp_path, "demo", spec)

        with _patch_nbw_root(tmp_path):
            rc = main(["export", "demo", "--to-mamba-spec", "-o", "-"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "name: demo" in out
        assert "conda-forge" in out
        assert "numpy" in out

    def test_export_to_mamba_spec_file(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        spec = _make_spec()
        _write_spec(tmp_path, "demo", spec)
        outfile = tmp_path / "demo-spec.yaml"

        with _patch_nbw_root(tmp_path):
            rc = main(["export", "demo", "--to-mamba-spec", "-o", str(outfile)])

        assert rc == 0
        content = outfile.read_text()
        assert "name: demo" in content
        assert "numpy" in content

    def test_export_to_requirements(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        spec = _make_spec()
        _write_spec(tmp_path, "demo", spec)

        with _patch_nbw_root(tmp_path):
            rc = main(["export", "demo", "--to-requirements", "-o", "-"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "numpy" in out
        assert "pandas" in out

    def test_export_to_wrangler_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        spec = _make_spec()
        _write_spec(tmp_path, "demo", spec)
        outfile = tmp_path / "demo-wrangler.yaml"

        with _patch_nbw_root(tmp_path):
            rc = main(["export", "demo", "--to-wrangler-spec", "-o", str(outfile)])

        assert rc == 0
        content = outfile.read_text()
        assert "image_spec_header" in content
        assert "extra_pip_packages" in content

    def test_export_default_is_mamba_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        spec = _make_spec()
        _write_spec(tmp_path, "demo", spec)

        with _patch_nbw_root(tmp_path):
            rc = main(["export", "demo", "-o", "-"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "name: demo" in out

    def test_export_missing_spec(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        with _patch_nbw_root(tmp_path):
            rc = main(["export", "nonexistent", "-o", "-"])

        assert rc == 1
        err = capsys.readouterr().err
        assert "no spec" in err.lower()


# ---------------------------------------------------------------------------
# status tests
# ---------------------------------------------------------------------------


class TestStatus:
    """Tests for hubenv status."""

    def test_status_table(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        (tmp_path / "envs" / "demo").mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_list_kernelspecs({}),
        ):
            rc = main(["status"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "Active env" in out
        assert "demo" in out
        assert "Pantries" in out

    def test_status_json(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        (tmp_path / "envs" / "demo").mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_list_kernelspecs({"demo": {}}),
        ):
            rc = main(["status", "--format", "json"])

        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "active_env" in data
        assert "pantries" in data
        assert "environments" in data
        assert any(e["name"] == "demo" for e in data["environments"])

    def test_status_no_active_env(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        with (
            patch.dict("os.environ", {}, clear=True),
            _patch_nbw_root(tmp_path),
            _patch_list_kernelspecs({}),
        ):
            rc = main(["status"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "(none)" in out

    def test_status_shows_pantry_rw(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        with (
            _patch_nbw_root(tmp_path),
            _patch_list_kernelspecs({}),
        ):
            rc = main(["status"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "r/o" in out or "r/w" in out

    def test_status_shows_kernel_state(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        (tmp_path / "envs" / "demo").mkdir(parents=True)

        with (
            _patch_nbw_root(tmp_path),
            _patch_list_kernelspecs({"demo": {"argv": ["python"]}}),
        ):
            rc = main(["status"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "registered" in out


# ---------------------------------------------------------------------------
# doctor tests
# ---------------------------------------------------------------------------


class TestDoctor:
    """Tests for hubenv doctor."""

    def test_doctor_all_pass(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        with (
            _patch_nbw_root(tmp_path),
            _all_checks_context(),
        ):
            rc = main(["doctor"])

        assert rc == 0

    def test_doctor_all_fail(self, tmp_path):
        from nb_wrangler.hubenv.cli import main

        fail = {"check": "fail", "pass": False, "detail": "bad", "hint": "fix"}
        with (
            _patch_nbw_root(tmp_path),
            _all_checks_context(mamba=fail, pantry=fail, efs=fail, kernel=fail),
        ):
            rc = main(["doctor"])

        assert rc == 1

    def test_doctor_json(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        with (
            _patch_nbw_root(tmp_path),
            _all_checks_context(),
        ):
            rc = main(["doctor", "--format", "json"])

        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "checks" in data
        assert "all_pass" in data
        assert len(data["checks"]) == 4

    def test_doctor_table_output(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        with (
            _patch_nbw_root(tmp_path),
            _all_checks_context(),
        ):
            rc = main(["doctor"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "self-test" in out

    def test_doctor_table_shows_fail(self, tmp_path, capsys):
        from nb_wrangler.hubenv.cli import main

        fail = {
            "check": "mamba",
            "pass": False,
            "detail": "not found",
            "hint": "install",
        }
        with (
            _patch_nbw_root(tmp_path),
            _all_checks_context(mamba=fail),
        ):
            rc = main(["doctor"])

        assert rc == 1
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "3/4 checks passed" in out


# ---------------------------------------------------------------------------
# unit tests for export helpers
# ---------------------------------------------------------------------------


class TestExportHelpers:
    """Tests for export helper functions."""

    def test_spec_to_requirements(self):
        from nb_wrangler.hubenv.export import spec_to_requirements

        spec = {"dependencies": [{"pip": ["numpy", "pandas"]}]}
        result = spec_to_requirements(spec)
        assert "numpy" in result
        assert "pandas" in result

    def test_spec_to_requirements_empty(self):
        from nb_wrangler.hubenv.export import spec_to_requirements

        spec = {"dependencies": ["python=3.11", "pip"]}
        result = spec_to_requirements(spec)
        assert result == ""

    def test_spec_to_wrangler(self):
        from nb_wrangler.hubenv.export import spec_to_wrangler

        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["python=3.11", "scipy", "pip", {"pip": ["numpy"]}],
        }
        wspec = spec_to_wrangler(spec)
        assert wspec["image_spec_header"]["image_name"] == "demo"
        assert wspec["image_spec_header"]["python_version"] == "3.11"
        assert "scipy" in wspec["extra_mamba_packages"]
        assert "numpy" in wspec["extra_pip_packages"]

    def test_spec_to_wrangler_no_python(self):
        from nb_wrangler.hubenv.export import spec_to_wrangler

        spec = {
            "name": "demo",
            "channels": ["conda-forge"],
            "dependencies": ["scipy", "pip", {"pip": ["numpy"]}],
        }
        wspec = spec_to_wrangler(spec)
        assert wspec["image_spec_header"]["python_version"] is None

    def test_extract_python_version(self):
        from nb_wrangler.hubenv.export import extract_python_version

        assert extract_python_version(["python=3.11"]) == "3.11"
        assert extract_python_version(["python=3.11.5", "numpy"]) == "3.11.5"
        assert extract_python_version(["numpy"]) is None

    def test_split_conda_pip(self):
        from nb_wrangler.hubenv.export import split_conda_pip

        deps = ["python=3.11", {"pip": ["numpy", "pandas"]}]
        conda, pip = split_conda_pip(deps)
        assert "python=3.11" in conda
        assert "numpy" in pip
        assert "pandas" in pip
