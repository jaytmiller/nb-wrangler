"""Tests for non-mutating spec save/validate behavior (copy semantics) and
retained update semantics for the designated spec-updating paths.

See readonly-specs-plan.md:  --reinstall and --data-reinstall must not modify
the wrangler spec in any form (date_updated, spec_sha256, or content),
while explicit update steps keep their current behavior.
"""

from pathlib import Path
from unittest.mock import patch

import yaml

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.injector import SpiInjector
from nb_wrangler.spec_manager import SpecManager

ORIGINAL_DATE = "2026-01-01T00:00:00"


def _make_valid_spec_dict():
    """Create a minimal valid wrangler spec dict, with a known date_updated."""
    return {
        "image_spec_header": {
            "image_name": "test-image",
            "kernel_name": "test-kernel",
            "deployment_name": "wrangler",
            "python_version": "3.12",
            "valid_on": "2026-01-01",
            "expires_on": "2027-01-01",
        },
        "repositories": {},
        "extra_mamba_packages": [],
        "common_mamba_packages": [],
        "extra_pip_packages": [],
        "common_pip_packages": [],
        "apt_packages": [],
        "system": {
            "spec_version": 2.3,
            "spi": {"repo": "https://example.com/spi.git"},
            "nb-wrangler": {"repo": "https://example.com/nbw.git"},
            "date_updated": ORIGINAL_DATE,
        },
    }


def _write_spec(tmp_path, spec_dict, name="spec.yaml"):
    path = tmp_path / name
    path.write_text(yaml.dump(spec_dict, default_flow_style=False))
    return path


def _load_manager(spec_file):
    sm = SpecManager()
    assert sm.load_spec(spec_file) is True
    return sm


def _load_yaml(path):
    return yaml.safe_load(Path(path).read_text())


def _stored_hash_matches(spec_file, expected_hash):
    """Verify a stored spec_sha256 the same way SpecManager.add_sha256 computes it."""
    check = SpecManager()
    assert check.load_spec(spec_file) is True
    return check.add_sha256() == expected_hash


class TestSaveSpecIsFaithfulCopy:
    def test_save_spec_preserves_date_and_hash(self, tmp_path):
        """save_spec must write out the current state without modifying it."""
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_file = _write_spec(tmp_path, _make_valid_spec_dict())
        sm = _load_manager(spec_file)
        original_hash = sm.add_sha256()
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        source_bytes = spec_file.read_bytes()

        assert sm.save_spec(out_dir) is True

        # In-memory state untouched.
        assert sm.system["date_updated"] == ORIGINAL_DATE
        assert sm.system["spec_sha256"] == original_hash

        # Written copy is faithful to the source.
        written = _load_yaml(out_dir / "spec.yaml")
        assert written["system"]["date_updated"] == ORIGINAL_DATE
        assert written["system"]["spec_sha256"] == original_hash

        # Source file unchanged.
        assert spec_file.read_bytes() == source_bytes


class TestValidateSha256NonMutating:
    def test_valid_hash_passes_without_mutation(self, tmp_path):
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_file = _write_spec(tmp_path, _make_valid_spec_dict())
        sm = _load_manager(spec_file)
        sm.add_sha256()
        before = sm.to_string()

        assert sm.validate_sha256() is True

        assert sm.to_string() == before
        assert sm.system["date_updated"] == ORIGINAL_DATE

    def test_invalid_hash_fails_without_mutation(self, tmp_path):
        """A failed validation must not rewrite the in-memory hash."""
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_file = _write_spec(tmp_path, _make_valid_spec_dict())
        sm = _load_manager(spec_file)
        sm.system["spec_sha256"] = "0" * 64
        before = sm.to_string()

        assert sm.validate_sha256() is False

        assert sm.to_string() == before
        assert sm.system["spec_sha256"] == "0" * 64


class TestReviseAndSaveIsTheUpdatePath:
    def test_refreshes_date_and_computes_hash(self, tmp_path):
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_file = _write_spec(tmp_path, _make_valid_spec_dict())
        sm = _load_manager(spec_file)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert (
            sm.revise_and_save(out_dir, add_sha256=True, test_notebooks=["a.ipynb"])
            is True
        )

        written = _load_yaml(out_dir / "spec.yaml")
        assert written["system"]["date_updated"] != ORIGINAL_DATE
        assert "test_notebooks" in written["out"]
        stored_hash = written["system"]["spec_sha256"]
        # The stored hash is a valid hash of the written content itself.
        assert _stored_hash_matches(out_dir / "spec.yaml", stored_hash)

    def test_with_add_sha256_false_removes_stale_hash(self, tmp_path):
        """Updates without re-hashing must not leave an outdated hash in place."""
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_file = _write_spec(tmp_path, _make_valid_spec_dict())
        sm = _load_manager(spec_file)
        sm.add_sha256()
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert sm.revise_and_save(out_dir, some_key="v") is True

        written = _load_yaml(out_dir / "spec.yaml")
        assert "spec_sha256" not in written["system"]
        assert written["system"]["date_updated"] != ORIGINAL_DATE
        assert written["out"]["some_key"] == "v"


class TestResetStillRemovesHashAndRefreshesDate:
    def test_reset_spec_removes_hash_and_refreshes_date(self, tmp_path):
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_dict = _make_valid_spec_dict()
        spec_dict["out"] = {"data": {"spec_inputs": {"x": "y"}}}
        spec_file = _write_spec(tmp_path, spec_dict)
        sm = _load_manager(spec_file)
        sm.add_sha256()

        assert sm.reset_spec() is True

        written = _load_yaml(spec_file)
        assert "spec_sha256" not in written["system"]
        assert written["system"]["date_updated"] != ORIGINAL_DATE


class TestReinstallStepsKeepSpecUntouched:
    def test_reinstall_spec_steps_do_not_modify_source(self, tmp_path, monkeypatch):
        """Simulate the --reinstall spec-touched steps and assert the source
        spec file is unchanged and the env-dir copy is faithful to it."""
        from nb_wrangler.wrangler import NotebookWrangler

        pantry_dir = tmp_path / "pantry"
        pantry_dir.mkdir()
        mm_dir = tmp_path / "mm"
        mm_dir.mkdir()
        monkeypatch.setenv("NBW_MM", str(mm_dir))

        spec_file = Path(__file__).parent.parent / "sample-specs/tike-wrangler-k1.yaml"
        source_bytes = spec_file.read_bytes()
        source = yaml.safe_load(source_bytes)
        stored_hash = source["system"]["spec_sha256"]

        config = WranglerConfig(
            workflows=["reinstall"],
            spec_file=str(spec_file),
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
            spec_ignore_hash=True,
        )
        set_args_config(config)

        with patch("nb_wrangler.pantry.NBW_PANTRY", pantry_dir):
            wrangler = NotebookWrangler()
            assert wrangler._validate_spec()
            assert wrangler._spec_add()
            assert wrangler._copy_spec_to_env()

            # Env-dir copy is faithful: hash preserved, and no fields added
            # or removed relative to the source (which the old save path did).
            env_copy = mm_dir / spec_file.name
            assert env_copy.exists()
            copy = yaml.safe_load(env_copy.read_bytes())
            assert copy["system"]["spec_sha256"] == stored_hash
            assert set(copy["system"]) == set(source["system"])
            for key in (
                "image_name",
                "kernel_name",
                "deployment_name",
                "python_version",
            ):
                assert (
                    copy["image_spec_header"][key] == source["image_spec_header"][key]
                )

            # Pantry shelf copy is byte-identical to the source.
            assert wrangler.pantry_shelf.spec_path.read_bytes() == source_bytes

        # Source spec file is unchanged after the reinstall steps.
        assert spec_file.read_bytes() == source_bytes

    def test_reinstall_validated_hash_keeps_spec_untouched(self, tmp_path, monkeypatch):
        """--reinstall without --spec-ignore-hash on a spec with a valid
        stored hash: validation and the env-dir copy must leave the spec
        untouched in memory and on disk (no rehash, no date change)."""
        from nb_wrangler.wrangler import NotebookWrangler

        pantry_dir = tmp_path / "pantry"
        pantry_dir.mkdir()
        mm_dir = tmp_path / "mm"
        mm_dir.mkdir()
        monkeypatch.setenv("NBW_MM", str(mm_dir))

        # A spec with a valid stored hash (the sample's stored hash predates
        # the current hash computation).
        src_file = Path(__file__).parent.parent / "sample-specs/tike-wrangler-k1.yaml"
        spec_file = tmp_path / "tike-wrangler-k1.yaml"
        spec_file.write_bytes(src_file.read_bytes())
        locker = SpecManager()
        assert locker.load_spec(spec_file) is True
        locker.add_sha256()
        assert locker.save_spec_as(spec_file) is True
        source = _load_yaml(spec_file)
        stored_hash = source["system"]["spec_sha256"]
        source_bytes = spec_file.read_bytes()

        config = WranglerConfig(
            workflows=["reinstall"],
            spec_file=str(spec_file),
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
        )
        set_args_config(config)

        with patch("nb_wrangler.pantry.NBW_PANTRY", pantry_dir):
            wrangler = NotebookWrangler()
            in_memory_before = wrangler.spec_manager.to_dict()
            assert wrangler._validate_spec()
            assert wrangler._spec_add()
            assert wrangler._copy_spec_to_env()

            # Env-dir copy is a value-for-value copy of the source.
            env_copy = mm_dir / spec_file.name
            assert env_copy.exists()
            copy = _load_yaml(env_copy)
            assert copy["system"]["spec_sha256"] == stored_hash
            assert copy["system"] == source["system"]

            # No in-memory mutation on the validated-hash path either.
            assert wrangler.spec_manager.to_dict() == in_memory_before

        # Source spec file is unchanged after the reinstall steps.
        assert spec_file.read_bytes() == source_bytes


class _DummyRepoManager:
    def __init__(self, repos_dir: Path):
        self.repos_dir = repos_dir


class TestSetWranglerSpecIsFaithfulCopy:
    """SpiInjector.set_wrangler_spec writes the spec to the SPI
    environments directory under the generic name as a faithful copy:
    stored spec_sha256/date_updated are preserved, and a missing
    spec_sha256 is set so the archived spec has an identity."""

    def _make_injector(self, tmp_path: Path, sm: SpecManager) -> SpiInjector:
        injector = SpiInjector(
            repo_manager=_DummyRepoManager(tmp_path / "repo"), spec_manager=sm
        )
        env_dir = tmp_path / "environments"
        env_dir.mkdir()
        injector.environments_path = env_dir
        return injector

    def test_preserves_stored_hash_and_date(self, tmp_path):
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_file = _write_spec(tmp_path, _make_valid_spec_dict())
        sm = _load_manager(spec_file)
        stored_hash = sm.add_sha256()
        before = sm.to_dict()

        injector = self._make_injector(tmp_path, sm)

        assert injector.set_wrangler_spec() is True

        out_file = tmp_path / "environments" / "nbw-wrangler-spec.yaml"
        written = _load_yaml(out_file)
        assert written["system"]["spec_sha256"] == stored_hash
        assert written["system"]["date_updated"] == ORIGINAL_DATE
        # In-memory spec untouched (pure copy).
        assert sm.to_dict() == before

    def test_sets_hash_when_spec_has_none(self, tmp_path):
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_file = _write_spec(tmp_path, _make_valid_spec_dict())
        sm = _load_manager(spec_file)
        assert sm.system.get("spec_sha256") is None

        injector = self._make_injector(tmp_path, sm)

        assert injector.set_wrangler_spec() is True

        out_file = tmp_path / "environments" / "nbw-wrangler-spec.yaml"
        written = _load_yaml(out_file)
        written_hash = written["system"]["spec_sha256"]
        # In-memory spec gains the same identity; written spec is self-consistent.
        assert sm.system["spec_sha256"] == written_hash
        verify = SpecManager()
        assert verify.load_spec(out_file) is True
        assert verify.validate_sha256() is True


class TestUpdateAndSaveProtocol:
    """update_and_save is the single designated spec-update path: it
    refreshes date_updated, and the saved file carries either a freshly
    computed spec_sha256 or none at all. A stale hash is unrepresentable."""

    def test_drops_stale_hash_when_not_rehashing(self, tmp_path):
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_file = _write_spec(tmp_path, _make_valid_spec_dict())
        sm = _load_manager(spec_file)
        sm.add_sha256()  # hash valid for the current, unmutated state
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        # Mutate content (any stored hash becomes stale), then update.
        sm.set_output_data("new_key", "v")
        assert sm.update_and_save(out_dir / "spec.yaml") is True

        written = _load_yaml(out_dir / "spec.yaml")
        assert written["system"]["date_updated"] != ORIGINAL_DATE
        assert "spec_sha256" not in written["system"]
        assert sm.system.get("spec_sha256") is None
        assert written["out"]["new_key"] == "v"

    def test_stamps_fresh_valid_hash_when_rehashing(self, tmp_path):
        set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
        spec_file = _write_spec(tmp_path, _make_valid_spec_dict())
        sm = _load_manager(spec_file)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        out_file = out_dir / "spec.yaml"

        sm.set_output_data("new_key", "v")
        assert sm.update_and_save(out_file, add_sha256=True) is True

        # In-memory state and the written file both carry a matching hash.
        assert sm.validate_sha256() is True
        written = _load_yaml(out_file)
        assert written["system"]["date_updated"] != ORIGINAL_DATE
        assert written["system"]["spec_sha256"] == sm.system["spec_sha256"]
        assert _stored_hash_matches(out_file, written["system"]["spec_sha256"])
