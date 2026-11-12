"""Functional tests (with fakes) for per-repository `data: off` behavior.

Uses real SpecManager/DataWrangler objects over fake repo trees carrying
`refdata_dependencies.yaml` files; all network-touching and unpacking pantry
operations are replaced by spies so the tests assert *what would have happened*
without any external services.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from nb_wrangler.config import WranglerConfig, set_args_config

_REPO_A_REFERENCE_YAML = """
install_files:
  fakepkg_a:
    version: 1.0
    data_url:
      - https://example.org/fakepkg-a-1.0.tar
    environment_variable: FAKE_A_PATH
    install_path: home
    data_path: fake-a-data
other_variables:
  FAKE_A_VAR: /opt/fake-a
"""

_REPO_B_REFERENCE_YAML = """
install_files:
  fakepkg_b:
    version: 1.0
    data_url:
      - https://example.org/fakepkg-b-1.0.tar
    environment_variable: FAKE_B_PATH
    install_path: home
    data_path: fake-b-data
other_variables:
  FAKE_B_VAR: /opt/fake-b
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spec(repositories, refdata_dependencies=None):
    spec = {
        "image_spec_header": {
            "image_name": "data-off-pipeline",
            "kernel_name": "dataoff",
            "deployment_name": "wrangler",
            "python_version": "3.12",
            "valid_on": "2026-01-01",
            "expires_on": "2027-01-01",
        },
        "repositories": repositories,
        "system": {
            "spec_version": 2.3,
            "spi": {"repo": "https://example.com/spi.git"},
            "nb-wrangler": {"repo": "https://example.com/nbw.git"},
            "date_updated": "2026-01-01T00:00:00",
        },
    }
    if refdata_dependencies is not None:
        spec["refdata_dependencies"] = refdata_dependencies
    return spec


def _write_spec(tmp_path: Path, spec_dict: dict) -> Path:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(yaml.dump(spec_dict, sort_keys=False))
    return spec_file


def _make_reference_tree(tmp_path: Path, repo_names):
    """Create <tmp>/references/<repo>/refdata_dependencies.yaml for each repo."""
    refs = tmp_path / "references"
    for name in repo_names:
        refdata_file = refs / name / "refdata_dependencies.yaml"
        refdata_file.parent.mkdir(parents=True, exist_ok=True)
        if name == "repo_a":
            refdata_file.write_text(_REPO_A_REFERENCE_YAML)
        else:
            refdata_file.write_text(_REPO_B_REFERENCE_YAML)
    return refs


_BLOCKED = {
    "download_all_data",
    "validate_all_data",
    "collect_all_metadata",
    "delete_archives",
    "unarchive",
    "archive",
}


def _block_network(shelf) -> dict:
    """Replace pantry network/mutation ops with spies.

    Returns a dict of {name: list-of-args-calls}.  If any blocked op is
    actually invoked the test fails with an AssertionError.
    """
    calls: dict = {name: [] for name in _BLOCKED}

    def _spy(name: str, *args, **kwargs):
        raise AssertionError(f"pantry.{name} attempted in a no-op data test: {args}")

    for name in _BLOCKED:
        bound = (lambda n=name: _spy)(name)
        bound.__name__ = name
        setattr(shelf, name, bound)
    return calls


def _make_dw(tmp_path: Path, spec_dict, seed_out_data=None):
    """Wire a DataWrangler against real fakes for the given spec dict."""
    from nb_wrangler.data_wrangler import DataWrangler
    from nb_wrangler.pantry import NbwPantry
    from nb_wrangler.repository import RepositoryManager
    from nb_wrangler.spec_manager import SpecManager

    spec_file = _write_spec(tmp_path, spec_dict)
    refs = tmp_path / "references"
    set_args_config(
        WranglerConfig(
            workflows=[],
            spec_file=str(spec_file),
            repos_dir=refs,
            output_dir=tmp_path / "output",
        )
    )
    sm = SpecManager()
    assert sm.load_spec(spec_file) is True, "spec failed to load"
    assert sm.validate() is True, "spec failed to validate"
    # Mirror what the curation flow stores in out.repositories (_spec_add).
    sm.set_output_data(
        "repositories",
        {
            name: {"url": repo.get("url"), "ref": repo.get("ref", "main")}
            for name, repo in (spec_dict.get("repositories") or {}).items()
        },
    )
    if seed_out_data is not None:
        sm.set_output_data("data", seed_out_data)

    pantry = NbwPantry(tmp_path / "pantry")
    env_manager = MagicMock()
    env_manager.register_environment.return_value = True
    dw = DataWrangler(sm, pantry, RepositoryManager(refs), env_manager)
    # Patch the exact shelf instance DataWrangler uses (get_shelf returns a
    # fresh NbwShelf per call).
    shelf = dw.pantry_shelf
    return dw, sm, shelf, env_manager


def _all_data_steps(dw):
    return [
        dw.list_data,
        dw.download,
        dw.delete,
        dw.update,
        dw.validate,
        dw.unpack,
        dw.pack,
        dw.symlink_install_data,
        dw.clean_symlink_install_data,
    ]


# ---------------------------------------------------------------------------
# Fully data-off spec: empty declarations, no-op reinstall steps
# ---------------------------------------------------------------------------


class TestAllOff:
    def test_collect_defines_empty_declarations(self, tmp_path):
        _make_reference_tree(tmp_path, ["repo_a", "repo_b"])
        dw, sm, shelf, env_manager = _make_dw(
            tmp_path,
            _spec(
                {
                    "repo_a": {
                        "url": "https://example.com/repo_a.git",
                        "data": "off",
                    },
                    "repo_b": {
                        "url": "https://example.com/repo_b.git",
                        "data": "off",
                    },
                }
            ),
        )
        assert dw.collect() is True

        out_data = sm.get_output_data("data")
        assert out_data == {
            "spec_inputs": {},
            "spec_exports": {},
            "pantry_exports": {},
        }, f"expected empty data declarations, got {out_data}"

        # Exports files are written but carry no export lines.
        for filename in ("nbw-spec-exports.sh", "nbw-pantry-exports.sh"):
            exports_file = shelf.path / filename
            assert exports_file.exists(), f"{filename} was not written"
            assert "export " not in exports_file.read_text()

        # Environment registered with an empty env-var dict.
        assert env_manager.register_environment.called
        env_vars = env_manager.register_environment.call_args.args[2]
        assert env_vars == {}

    def test_reinstall_steps_noop_without_network(self, tmp_path):
        _make_reference_tree(tmp_path, ["repo_a", "repo_b"])
        dw, sm, shelf, env_manager = _make_dw(
            tmp_path,
            _spec(
                {
                    "repo_a": {
                        "url": "https://example.com/repo_a.git",
                        "data": "off",
                    },
                    "repo_b": {
                        "url": "https://example.com/repo_b.git",
                        "data": "off",
                    },
                }
            ),
        )
        assert dw.collect() is True
        _block_network(shelf)
        for step in _all_data_steps(dw):
            assert step() is True, f"{step.__name__} should no-op under data: off"

    def test_data_off_after_curation_reinstall_noop(self, tmp_path):
        """A spec curated while a repo was on stays a no-op once it is turned off."""
        _make_reference_tree(tmp_path, ["repo_a", "repo_b"])
        refs = tmp_path / "references"
        repos = {
            "repo_a": {"url": "https://example.com/repo_a.git", "data": "off"},
            "repo_b": {"url": "https://example.com/repo_b.git", "data": "off"},
        }
        dw, sm, shelf, env_manager = _make_dw(
            tmp_path,
            _spec(repos),
            seed_out_data={
                "spec_inputs": {
                    str(refs / "repo_a" / "refdata_dependencies.yaml"): yaml.safe_load(
                        _REPO_A_REFERENCE_YAML
                    ),
                    str(refs / "repo_b" / "refdata_dependencies.yaml"): yaml.safe_load(
                        _REPO_B_REFERENCE_YAML
                    ),
                },
                "spec_exports": {},
                "pantry_exports": {},
            },
        )
        _block_network(shelf)
        for step in _all_data_steps(dw):
            assert (
                step() is True
            ), f"{step.__name__} should no-op for a spec turned off after curation"


# ---------------------------------------------------------------------------
# Mixed spec: only data-enabled repos are curated / installed
# ---------------------------------------------------------------------------


class TestMixed:
    def _mixed_spec(self):
        return _spec(
            {
                "repo_a": {"url": "https://example.com/repo_a.git", "data": "on"},
                "repo_b": {
                    "url": "https://example.com/repo_b.git",
                    "data": "off",
                },
            }
        )

    def test_only_on_repo_is_curated(self, tmp_path):
        _make_reference_tree(tmp_path, ["repo_a", "repo_b"])
        dw, sm, shelf, env_manager = _make_dw(tmp_path, self._mixed_spec())

        assert dw.collect() is True
        out_data = sm.get_output_data("data")
        spec_inputs = out_data["spec_inputs"]
        assert any(
            "repo_a" in key for key in spec_inputs
        ), f"repo_a should be in spec_inputs: {list(spec_inputs)}"
        assert not any(
            "repo_b" in key for key in spec_inputs
        ), f"repo_b should be excluded from spec_inputs: {list(spec_inputs)}"
        assert "FAKE_A_PATH" in out_data["spec_exports"]
        assert "FAKE_B_PATH" not in out_data["spec_exports"]

    def test_download_covers_only_on_repo(self, tmp_path):
        _make_reference_tree(tmp_path, ["repo_a", "repo_b"])
        dw, sm, shelf, env_manager = _make_dw(tmp_path, self._mixed_spec())
        assert dw.collect() is True

        downloaded = []

        def download_spy(urls, **kwargs):
            downloaded.extend(urls)
            return True

        shelf.download_all_data = download_spy
        assert dw.download() is True

        assert downloaded, "expected the on-repo's data urls to be downloaded"
        assert all(tuple_url[0] == "repo_a" for tuple_url in downloaded)

    def test_read_time_filter_turned_off_after_curation(self, tmp_path):
        """repo_b was on at curation time; turned off later: only repo_a installs."""
        _make_reference_tree(tmp_path, ["repo_a", "repo_b"])
        refs = tmp_path / "references"
        seed = {
            "spec_inputs": {
                str(refs / "repo_a" / "refdata_dependencies.yaml"): yaml.safe_load(
                    _REPO_A_REFERENCE_YAML
                ),
                str(refs / "repo_b" / "refdata_dependencies.yaml"): yaml.safe_load(
                    _REPO_B_REFERENCE_YAML
                ),
            },
            "spec_exports": {},
            "pantry_exports": {},
        }
        repos = {
            "repo_a": {"url": "https://example.com/repo_a.git", "data": "on"},
            "repo_b": {"url": "https://example.com/repo_b.git", "data": "off"},
        }
        dw, sm, shelf, env_manager = _make_dw(tmp_path, _spec(repos), seed)

        unpacked: list = []

        def unarchive_spy(src, dest, extract="", **kwargs):
            unpacked.append(str(src))
            return True

        shelf.unarchive = unarchive_spy
        download_urls: list = []

        def download_spy(urls, **kwargs):
            download_urls.extend(urls)
            return True

        shelf.download_all_data = download_spy

        assert dw.download() is True
        assert dw.unpack() is True
        assert all(url[0] == "repo_a" for url in download_urls)
        assert not any("repo_b" in name for name in unpacked)


# ---------------------------------------------------------------------------
# Documented edge: image-wide refdata_dependencies is not suppressed
# ---------------------------------------------------------------------------


class TestImageWideRefdata:
    def test_image_wide_data_still_curates_when_repos_off(self, tmp_path):
        _make_reference_tree(tmp_path, ["repo_a", "repo_b"])
        dw, sm, shelf, env_manager = _make_dw(
            tmp_path,
            _spec(
                {
                    "repo_a": {
                        "url": "https://example.com/repo_a.git",
                        "data": "off",
                    },
                    "repo_b": {
                        "url": "https://example.com/repo_b.git",
                        "data": "off",
                    },
                },
                refdata_dependencies={
                    "other_variables": {"GLOBAL_DATA_VAR": "/opt/global"}
                },
            ),
        )
        assert dw.collect() is True
        out_data = sm.get_output_data("data")

        spec_inputs = out_data["spec_inputs"]
        assert (
            len(spec_inputs) == 1
        ), f"only the image-wide entry should remain: {list(spec_inputs)}"
        (entry,) = spec_inputs.values()
        assert entry["other_variables"]["GLOBAL_DATA_VAR"] == "/opt/global"
        assert "GLOBAL_DATA_VAR" in out_data["spec_exports"]

        # No repo urls to download, but the step must *run* (not skip) and no-op.
        download_calls = []

        def download_spy(urls, **kwargs):
            download_calls.append(urls)
            return True

        shelf.download_all_data = download_spy
        assert dw.download() is True
        assert download_calls == [[]]


# ---------------------------------------------------------------------------
# Regression: spec without any data key behaves exactly as before
# ---------------------------------------------------------------------------


class TestRegressionNoDataKey:
    def test_all_repos_curated_when_flag_absent(self, tmp_path):
        _make_reference_tree(tmp_path, ["repo_a", "repo_b"])
        dw, sm, shelf, env_manager = _make_dw(
            tmp_path,
            _spec(
                {
                    "repo_a": {"url": "https://example.com/repo_a.git"},
                    "repo_b": {"url": "https://example.com/repo_b.git"},
                }
            ),
        )
        assert dw.collect() is True
        out_data = sm.get_output_data("data")
        assert any("repo_a" in key for key in out_data["spec_inputs"])
        assert any("repo_b" in key for key in out_data["spec_inputs"])
        assert "FAKE_A_PATH" in out_data["spec_exports"]
        assert "FAKE_B_PATH" in out_data["spec_exports"]


# ---------------------------------------------------------------------------
# spec_sha256: the new field participates in the canonical hash
# ---------------------------------------------------------------------------


class TestSpecSha256:
    def test_hash_changes_with_data_flag(self, tmp_path):
        from nb_wrangler.spec_manager import SpecManager

        spec_file = _write_spec(
            tmp_path,
            _spec({"repo_a": {"url": "https://example.com/repo_a.git", "data": "off"}}),
        )
        set_args_config(
            WranglerConfig(workflows=[], spec_file=str(spec_file), repos_dir=tmp_path)
        )
        sm = SpecManager()
        assert sm.load_spec(spec_file) is True
        hash_off = sm.add_sha256()
        assert sm.validate_sha256() is True
        sm._spec["repositories"]["repo_a"]["data"] = "on"
        hash_on = sm.add_sha256()
        assert hash_off != hash_on
        assert sm.validate_sha256() is True


# ---------------------------------------------------------------------------
# hubenv stays a thin wrapper over the same guarded flag-driven path
# ---------------------------------------------------------------------------


class TestHubenvThinWrapper:
    def test_hubenv_data_config_maps_to_shared_data_flags(self, tmp_path):
        from nb_wrangler.data_manager import _data_wrangler_config

        spec_path = tmp_path / "shelf" / "nbw-wrangler-spec.yaml"
        cfg = _data_wrangler_config(spec_path, data_download=True, data_select=".*")
        assert cfg.workflows == []
        assert cfg.data_download is True
        assert cfg.data_select == ".*"

        cfg = _data_wrangler_config(spec_path, data_unpack=True)
        assert cfg.workflows == []
        assert cfg.data_unpack is True

    def test_cli_data_steps_noop_on_data_off_spec(self, tmp_path):
        """Building a full NotebookWrangler for a data-off spec: every guarded
        data step returns True without touching the pantry (no network)."""
        from nb_wrangler.wrangler import NotebookWrangler

        _make_reference_tree(tmp_path, ["repo_a", "repo_b"])
        spec_file = _write_spec(
            tmp_path,
            _spec(
                {
                    "repo_a": {
                        "url": "https://example.com/repo_a.git",
                        "data": "off",
                    },
                    "repo_b": {
                        "url": "https://example.com/repo_b.git",
                        "data": "off",
                    },
                }
            ),
        )
        set_args_config(
            WranglerConfig(
                workflows=[],
                spec_file=str(spec_file),
                repos_dir=tmp_path / "references",
                output_dir=tmp_path / "output",
            )
        )
        pantry_dir = tmp_path / "pantry"
        pantry_dir.mkdir(exist_ok=True)
        with patch("nb_wrangler.pantry.NBW_PANTRY_DIRS", [pantry_dir]):
            wrangler = NotebookWrangler()
            dw = wrangler.data_wrangler
            _block_network(dw.pantry_shelf)
            for step in _all_data_steps(dw):
                assert step() is True, f"{step.__name__} should no-op under data: off"
