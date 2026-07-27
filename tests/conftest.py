"""Shared helpers for nb_wrangler tests that need WranglerConfig setup."""

from pathlib import Path
from nb_wrangler.config import WranglerConfig, set_args_config


def _base_config(tmp_path: Path, **overrides) -> WranglerConfig:
    """Build a WranglerConfig with sensible defaults for tests.

    All new test files should call ``set_args_config(_base_config(tmp_path, ...))``
    before instantiating any WranglerConfigurable / WranglerEnvable subclass.

    Parameters that *can* be overridden are passed through **overrides**.
    """
    return set_args_config(
        WranglerConfig(
            workflows=[],
            spec_file="",
            repos_dir=tmp_path / "repos",
            output_dir=tmp_path / "output",
            **overrides,
        )
    )
