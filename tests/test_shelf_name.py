"""Regression tests for ``SpecManager.shelf_name``.

The shelf directory name must default to the ``moniker`` (filesystem-safe
``image_name``) — the historical pantry layout.  It must NOT resolve the
environment/kernel name: doing so (a) orphaned existing shelves once the
kernel name differed from the moniker (e.g. ``python3`` -> ``base`` on the
TIKE spec), and (b) raised ``AttributeError`` at construction for external
``environment_spec`` specs that have not been compiled yet.

An explicit ``shelf_name`` header field remains the documented override.
"""

import re
import shutil
from pathlib import Path

from nb_wrangler.config import WranglerConfig, set_args_config
from nb_wrangler.spec_manager import SpecManager

SAMPLES = Path(__file__).resolve().parents[1] / "sample-specs"


def _load(tmp_path: Path, sample: str) -> SpecManager:
    """Load *sample* into a fresh SpecManager with empty workflows."""
    set_args_config(WranglerConfig(workflows=[], repos_dir=tmp_path / "repos"))
    sm = SpecManager()
    spec_file = tmp_path / Path(sample).name
    shutil.copy(SAMPLES / sample, spec_file)
    assert sm.load_spec(spec_file), f"failed to load {sample}"
    return sm


def test_shelf_name_defaults_to_moniker_not_env_name(tmp_path):
    """python3 kernel maps to the shared 'base' env; the shelf must stay on
    the moniker so existing pantry layouts keep resolving."""
    sm = _load(tmp_path, "tike-wrangler-k1.yaml")
    assert sm.kernel_name == "python3"
    assert sm.environment_name == "base"
    assert sm.shelf_name == sm.moniker == "TIKE-2025.07-beta"


def test_shelf_name_needs_no_kernel_for_external_spec(tmp_path):
    """External environment_spec specs resolve a shelf before the compiler
    has fetched the env spec (kernel_name alone would raise)."""
    sm = _load(tmp_path, "uri-mamba-spec.yaml")
    # Make the kernel genuinely unresolvable: strip the compiled out data.
    text = sm.spec_file.read_text()
    stripped = re.sub(r"(?ms)^out:.*\Z", "", text)
    sm.spec_file.write_text(stripped)
    sm2 = SpecManager()
    assert sm2.load_spec(sm.spec_file)
    assert sm2.shelf_name == sm2.moniker == "Test-URI-Spec"


def test_explicit_shelf_name_header_trumps_everything(tmp_path):
    """An explicit header ``shelf_name`` overrides the moniker default."""
    sm = _load(tmp_path, "RomanNexus-2026.2.yaml")
    assert sm.shelf_name == sm.moniker  # no shelf_name in shipped spec
    text = sm.spec_file.read_text()
    stamped = text.replace(
        "image_spec_header:", "image_spec_header:\n  shelf_name: custom-shelf", 1
    )
    sm.spec_file.write_text(stamped)
    sm2 = SpecManager()
    assert sm2.load_spec(sm.spec_file)
    assert sm2.shelf_name == "custom-shelf"
