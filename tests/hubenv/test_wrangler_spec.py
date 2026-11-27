"""Tests for the hubenv shadow spec as a conforming nbw wrangler spec.

Covers the two valid forms (simple / inline two-doc), a valid ``spec_sha256``
on every write, the CLI > wrangler > inline-mamba precedence, the inline
name/python override (with descriptive logging and stale-pin clearing), the
self-consistency invariant (stale compiled pip lock cleared), and relock.
"""

from pathlib import Path

from unittest.mock import patch, MagicMock

import pytest

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.hubenv.config import PantryStore
from nb_wrangler.hubenv.env_spec import (
    load_hubenv_spec,
    save_hubenv_spec,
)
from nb_wrangler.hubenv.seeds import (
    DISPLAY_NAME_FLAG,
    INLINE_FLAG,
    seed_from_empty,
    seed_from_wrangler_spec,
)
from nb_wrangler.spec_manager import SpecManager

# ---------------------------------------------------------------------------
# Fixture sources
# ---------------------------------------------------------------------------

_SIMPLE_SRC = """\
image_spec_header:
  image_name: srcenv
  kernel_name: srcenv
  display_name: srcenv
  deployment_name: wrangler
  valid_on: 1970-01-01
  expires_on: 2099-12-31
  python_version: "3.10"
repositories: {}
system:
  spec_version: "2.3"
  spec_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  date_updated: "2026-01-01T00:00:00"
extra_mamba_packages:
  - numpy
extra_pip_packages:
  - requests
"""

# doc2 carries the name & python pin for the inline form; the header may
# additionally carry kernel_name/python_version (header wins on conflict).
_INLINE_SRC = """\
image_spec_header:
  image_name: src2
  display_name: src2
  deployment_name: wrangler
  valid_on: 1970-01-01
  expires_on: 2099-12-31
repositories: {}
system:
  spec_version: "2.3"
  spec_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  date_updated: "2026-01-01T00:00:00"
extra_mamba_packages:
  - scipy
extra_pip_packages:
  - pandas
---
name: src2
channels:
  - conda-forge
dependencies:
  - python=3.10
  - numpy
  - pip
  - pip:
      - scikit-learn
"""

# Inline seed that carries a *stale compiled* pip lock (python-tagged) for
# the self-consistency invariant.
_INLINE_LOCKED_SRC = """\
image_spec_header:
  image_name: locked
  display_name: locked
  deployment_name: wrangler
  valid_on: 1970-01-01
  expires_on: 2099-12-31
repositories: {}
system:
  spec_version: "2.3"
  spec_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  date_updated: "2026-01-01T00:00:00"
---
name: locked
channels:
  - conda-forge
dependencies:
  - python=3.10
  - pip
  - pip:
      - "scikit-learn==1.0.0-cp310-cp310-manylinux_2_17"
      - plain-pkg
"""

# Hybrid inline spec: header kernel_name/python_version differ from the
# second document's name/python pin — header must win the delegation.
_HYBRID_SRC = """\
image_spec_header:
  image_name: hybrid
  kernel_name: hybrid-header
  python_version: "3.11"
  display_name: hybrid
  deployment_name: wrangler
  valid_on: 1970-01-01
  expires_on: 2099-12-31
repositories: {}
extra_mamba_packages:
  - scipy
extra_pip_packages:
  - pandas
---
name: hybrid-inline
channels:
  - conda-forge
dependencies:
  - python=3.10
  - numpy
  - pip
  - pip:
      - scikit-learn
"""


@pytest.fixture(autouse=True)
def _set_config(tmp_path):
    """Ensure the global args_config is set so SpecManager/EnvironmentManager work."""
    set_args_config(
        WranglerConfig(
            workflows=[],
            spec_file="",
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
        )
    )
    return tmp_path


def _pantry(tmp_path) -> PantryStore:
    pantry = tmp_path / "pantry"
    pantry.mkdir(exist_ok=True)
    return PantryStore(paths=[pantry])


def _write(path, text: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def _assert_valid_spec(path):
    """The file must validate structurally and pass nbw's hash check."""
    sm = SpecManager.load_and_validate(path)
    assert sm is not None
    assert sm.validate() is True
    assert sm.validate_sha256() is True


def _seed(src: str, name=None, python=None, display_name=None, tmp_path=None):
    p = Path(tmp_path or "/tmp") / "src.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(src)
    return seed_from_wrangler_spec(name, str(p), python, display_name)


# ---------------------------------------------------------------------------
# 1. Two-form writing + validity
# ---------------------------------------------------------------------------


class TestTwoForms:
    """save_hubenv_spec must emit the form matching the source and stay valid."""

    def test_simple_form_single_doc_valid(self, _set_config):
        seed = seed_from_empty("demo", "3.11")
        store = _pantry(_set_config)
        save_hubenv_spec(store, "demo", seed)
        path = store.shelf_spec_path("demo")
        assert "\n---\n" not in path.read_text()
        _assert_valid_spec(path)
        w = load_hubenv_spec(store, "demo")
        assert w.get(INLINE_FLAG) is False
        assert w["name"] == "demo"

    def test_inline_form_two_docs_valid(self, _set_config):
        src = _write(_set_config / "src.yaml", _INLINE_SRC)
        seed = seed_from_wrangler_spec("demo", str(src))
        assert seed.get(INLINE_FLAG) is True
        store = _pantry(_set_config)
        save_hubenv_spec(store, "demo", seed)
        path = store.shelf_spec_path("demo")
        assert "\n---\n" in path.read_text()
        _assert_valid_spec(path)
        w = load_hubenv_spec(store, "demo")
        assert w.get(INLINE_FLAG) is True
        assert "python=3.10" in w["dependencies"]

    def test_inline_header_carries_effective_name_python(self, _set_config):
        """The saved inline shelf spec's header records the effective
        ``kernel_name`` (CLI-won here) and ``python_version`` (doc2 pin)."""
        src = _write(_set_config / "src.yaml", _INLINE_SRC)
        seed = seed_from_wrangler_spec("demo", str(src))
        store = _pantry(_set_config)
        save_hubenv_spec(store, "demo", seed)
        import nb_wrangler.utils as u

        docs = list(u.get_yaml().load_all(store.shelf_spec_path("demo").read_text()))
        header = docs[0].get("image_spec_header") or {}
        assert header.get("kernel_name") == "demo"
        assert header.get("python_version") == "3.10"
        assert header.get("name") is None  # no name slot in doc1 for inline


# ---------------------------------------------------------------------------
# 2. Hash round-trip
# ---------------------------------------------------------------------------


class TestHashRoundTrip:
    def test_hash_valid_after_write_and_reload_simple(self, _set_config):
        seed = seed_from_empty("r", "3.11")
        store = _pantry(_set_config)
        save_hubenv_spec(store, "r", seed)
        path = store.shelf_spec_path("r")
        _assert_valid_spec(path)
        w = load_hubenv_spec(store, "r")
        save_hubenv_spec(store, "r", w)
        _assert_valid_spec(path)

    def test_hash_valid_after_write_and_reload_inline(self, _set_config):
        src = _write(_set_config / "src.yaml", _INLINE_SRC)
        seed = seed_from_wrangler_spec("r", str(src))
        store = _pantry(_set_config)
        save_hubenv_spec(store, "r", seed)
        path = store.shelf_spec_path("r")
        _assert_valid_spec(path)
        w = load_hubenv_spec(store, "r")
        save_hubenv_spec(store, "r", w)
        _assert_valid_spec(path)
        assert "\n---\n" in path.read_text()  # form preserved


# ---------------------------------------------------------------------------
# 3. Precedence (CLI > wrangler > inline mamba)
# ---------------------------------------------------------------------------


class TestPrecedence:
    def test_simple_cli_overrides_header(self, _set_config):
        seed = _seed(_SIMPLE_SRC, name="cli-name", python="3.12", tmp_path=_set_config)
        assert seed["name"] == "cli-name"
        assert any(
            d == "python=3.12" for d in seed["dependencies"] if isinstance(d, str)
        )
        assert "numpy" in seed["dependencies"]  # header recipe preserved
        assert seed.get(INLINE_FLAG) is False

    def test_simple_no_cli_uses_header(self, _set_config):
        seed = _seed(_SIMPLE_SRC, name=None, python=None, tmp_path=_set_config)
        assert seed["name"] == "srcenv"
        assert any(
            d == "python=3.10" for d in seed["dependencies"] if isinstance(d, str)
        )
        assert seed.get(INLINE_FLAG) is False

    def test_inline_cli_overrides_doc2(self, _set_config):
        seed = _seed(_INLINE_SRC, name="cli2", python="3.13", tmp_path=_set_config)
        assert seed["name"] == "cli2"
        assert any(
            d == "python=3.13" for d in seed["dependencies"] if isinstance(d, str)
        )
        assert any(d == "numpy" for d in seed["dependencies"])  # doc2 recipe kept
        assert seed["channels"] == ["conda-forge"]
        assert seed.get(INLINE_FLAG) is True

    def test_inline_no_cli_uses_doc2(self, _set_config):
        seed = _seed(_INLINE_SRC, name=None, python=None, tmp_path=_set_config)
        assert seed["name"] == "src2"
        assert any(
            d == "python=3.10" for d in seed["dependencies"] if isinstance(d, str)
        )
        assert seed.get(INLINE_FLAG) is True

    def test_inline_header_overrides_doc2(self, _set_config, caplog):
        """Header kernel_name/python_version differ from doc2: header wins;
        the saved shelf spec stays a valid two-doc inline spec with the
        header recording the effective values."""
        import logging

        import nb_wrangler.utils as u

        caplog.set_level(logging.INFO)
        src = _write(_set_config / "hybrid.yaml", _HYBRID_SRC)
        seed = seed_from_wrangler_spec(None, str(src))
        assert seed["name"] == "hybrid-header"
        assert any(
            d == "python=3.11" for d in seed["dependencies"] if isinstance(d, str)
        )
        assert "Using wrangler header name 'hybrid-header' instead of" in caplog.text
        assert seed.get(INLINE_FLAG) is True

        store = _pantry(_set_config)
        save_hubenv_spec(store, "hybrid-header", seed)
        path = store.shelf_spec_path("hybrid-header")
        _assert_valid_spec(path)
        assert "\n---\n" in path.read_text()  # form preserved
        docs = list(u.get_yaml().load_all(path.read_text()))
        header = docs[0].get("image_spec_header") or {}
        assert header.get("kernel_name") == "hybrid-header"
        assert header.get("python_version") == "3.11"
        assert docs[1].get("name") == "hybrid-header"  # doc2 aligned to header

    def test_simple_python_missing_from_all_sources_raises(self, _set_config):
        """Simple form with no python anywhere must raise ValueError."""
        src = (
            "image_spec_header:\n"
            "  image_name: nopy\n"
            "  kernel_name: nopy\n"
            "  display_name: nopy\n"
            "  deployment_name: wrangler\n"
            "  valid_on: 1970-01-01\n"
            "  expires_on: 2099-12-31\n"
            "repositories: {}\n"
            "system:\n"
            '  spec_version: "2.3"\n'
            '  spec_sha256: "' + "a" * 64 + '"\n'
            '  date_updated: "2026-01-01T00:00:00"\n'
            "extra_mamba_packages:\n"
            "  - numpy\n"
        )
        p = _write(_set_config / "nopy.yaml", src)
        with pytest.raises(ValueError, match="No Python pin"):
            seed_from_wrangler_spec("nopy", str(p))
        # CLI --python satisfies the requirement
        seed = _seed(src, name="nopy", python="3.11", tmp_path=_set_config)
        assert any(
            d == "python=3.11" for d in seed["dependencies"] if isinstance(d, str)
        )


# ---------------------------------------------------------------------------
# 4. Inline override + stale pin clearing + logging
# ---------------------------------------------------------------------------


class TestInlineOverride:
    def test_name_and_python_override_logged(self, _set_config, caplog):
        import logging

        caplog.set_level(logging.INFO)
        src = _write(_set_config / "src.yaml", _INLINE_SRC)
        seed = seed_from_wrangler_spec("cli2", str(src), "3.13")
        out = caplog.text
        assert "Overriding name from 'src2' to 'cli2' (CLI)." in out
        assert "Overriding python from '3.10' to '3.13' (CLI)." in out
        # stale pin cleared & replaced
        py = [
            d
            for d in seed["dependencies"]
            if isinstance(d, str) and d.startswith("python")
        ]
        assert py == ["python=3.13"]

    def test_recipe_not_rewritten(self, _set_config):
        """CLI override must not touch channels / other conda deps."""
        src = _write(_set_config / "src.yaml", _INLINE_SRC)
        seed = seed_from_wrangler_spec("cli2", str(src), "3.13")
        assert seed["channels"] == ["conda-forge"]
        assert any(d == "numpy" for d in seed["dependencies"])  # recipe intact


# ---------------------------------------------------------------------------
# 5. Self-consistency (stale pip lock)
# ---------------------------------------------------------------------------


class TestPipLockConsistency:
    def _pip_section(self, seed):
        return next(
            d["pip"] for d in seed["dependencies"] if isinstance(d, dict) and "pip" in d
        )

    def test_stale_compiled_lock_cleared_on_python_change(self, _set_config):
        seed = _seed(
            _INLINE_LOCKED_SRC, name="cli", python="3.13", tmp_path=_set_config
        )
        pip = self._pip_section(seed)
        # the cp310 compiled entry must be gone (stale for 3.13)
        assert not any("cp310" in p for p in pip)
        # plain (python-independent) name preserved
        assert "plain-pkg" in pip
        assert any(
            "python=3.13" in d for d in seed["dependencies"] if isinstance(d, str)
        )

    def test_plain_names_preserved_when_no_python_change(self, _set_config):
        # same python as source -> lock left untouched
        seed = _seed(
            _INLINE_LOCKED_SRC, name="cli", python="3.10", tmp_path=_set_config
        )
        pip = self._pip_section(seed)
        assert any("cp310" in p for p in pip)  # untouched
        assert "plain-pkg" in pip

    def test_no_compiled_lock_no_op(self, _set_config):
        """A plain package list should never be mangled by a python change."""
        src = _write(_set_config / "src.yaml", _INLINE_SRC)
        seed = seed_from_wrangler_spec("cli", str(src), "3.13")
        pip = self._pip_section(seed)
        assert "scikit-learn" in pip  # plain name preserved
        assert not any("cp310" in p for p in pip)


# ---------------------------------------------------------------------------
# 6. Relock keeps the shadow spec valid (both forms)
# ---------------------------------------------------------------------------


class TestRelock:
    def _run_relock(self, tmp_path, name, dry_run=False, inline=False):
        store = _pantry(tmp_path)
        if inline:
            src = _write(tmp_path / "src.yaml", _INLINE_SRC)
            seed = seed_from_wrangler_spec(name, str(src))
        else:
            seed = seed_from_empty(name, "3.11")
        save_hubenv_spec(store, name, seed)
        from nb_wrangler.hubenv.env_relock import do_relock

        with patch(
            "nb_wrangler.hubenv.env_relock.compile_pip_packages",
            return_value=["a==1", "b==2"],
        ):
            rc = do_relock(store, MagicMock(), name, dry_run)
        return store.shelf_spec_path(name), rc

    def test_relock_inline_stays_valid_and_two_doc(self, _set_config):
        path, rc = self._run_relock(_set_config, "r", inline=True)
        assert rc == 0
        assert "\n---\n" in path.read_text()
        _assert_valid_spec(path)

    def test_relock_simple_stays_valid_and_single_doc(self, _set_config):
        path, rc = self._run_relock(_set_config, "r")
        assert rc == 0
        assert "\n---\n" not in path.read_text()
        _assert_valid_spec(path)

    def test_relock_updates_pip_to_compiled(self, _set_config):
        store = _pantry(_set_config)
        seed = seed_from_empty("r", "3.11")
        save_hubenv_spec(store, "r", seed)
        from nb_wrangler.hubenv.env_relock import apply_relock

        spec = load_hubenv_spec(store, "r")
        apply_relock(store, "r", spec, ["a==1", "b==2"])
        path = store.shelf_spec_path("r")
        _assert_valid_spec(path)
        w = load_hubenv_spec(store, "r")
        pip = next(
            d["pip"] for d in w["dependencies"] if isinstance(d, dict) and "pip" in d
        )
        assert "a==1" in pip and "b==2" in pip


# ---------------------------------------------------------------------------
# 7. Display name (CLI > header > name, recorded in the saved header)
# ---------------------------------------------------------------------------


class TestDisplayName:
    """Display name resolves CLI > header ``display_name`` > name and round-trips
    through the saved shelf spec."""

    def test_header_display_name_wins_without_cli(self, _set_config):
        seed = _seed(_SIMPLE_SRC, name=None, python=None, tmp_path=_set_config)
        assert seed[DISPLAY_NAME_FLAG] == "srcenv"

        seed = _seed(_INLINE_SRC, name=None, python=None, tmp_path=_set_config)
        assert seed[DISPLAY_NAME_FLAG] == "src2"

    def test_cli_display_name_wins_and_is_logged(self, _set_config, caplog):
        import logging

        caplog.set_level(logging.INFO)
        seed = _seed(
            _SIMPLE_SRC,
            name="demo",
            python="3.11",
            display_name="CLI Display",
            tmp_path=_set_config,
        )
        assert seed[DISPLAY_NAME_FLAG] == "CLI Display"
        assert (
            "Overriding display name from 'srcenv' to 'CLI Display' (CLI)."
            in caplog.text
        )

    def test_display_name_recorded_in_saved_header_round_trip(self, _set_config):
        import nb_wrangler.utils as u

        seed = _seed(
            _SIMPLE_SRC,
            name="demo",
            python="3.11",
            display_name="CLI Display",
            tmp_path=_set_config,
        )
        store = _pantry(_set_config)
        save_hubenv_spec(store, "demo", seed)
        path = store.shelf_spec_path("demo")
        _assert_valid_spec(path)
        docs = list(u.get_yaml().load_all(path.read_text()))
        assert (docs[0].get("image_spec_header") or {}).get(
            "display_name"
        ) == "CLI Display"

        w = load_hubenv_spec(store, "demo")
        assert w.get(DISPLAY_NAME_FLAG) == "CLI Display"
        save_hubenv_spec(store, "demo", w)
        _assert_valid_spec(path)
        docs = list(u.get_yaml().load_all(path.read_text()))
        assert (docs[0].get("image_spec_header") or {}).get("display_name") == (
            "CLI Display"
        )
