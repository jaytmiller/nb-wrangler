# AGENTS.md

## Project
nb-wrangler constructs Python environments based upon JupyterLab notebook repositories,
specified notebook requirements and imports, and defined notebook support data.  Futher,
once an environment is defined,  nb-wrangler supports the creation of notebook Docker
images that include the environment based upon the locked spec.

Primary tooling: uv or pip, mamba or micromamba, pytest, flake8, mypy, black,
radon, Docker, git, make.

## Non-negotiable rules
- Never read, print, commit, or modify secrets, `.env`, credentials, or private keys.
- Do not edit generated files: `dist/`, `build/`, `coverage/`, `docs/_build/`.
- Do not run destructive Docker commands (`docker system prune`, volume removal,
  compose down -v) without explicit approval.
- Preserve CPU-only execution unless a task explicitly requires GPU support.

## Commands
```bash
make test-functional
make unit-test
make lint/flake8
make lint/black
make lint/radon
make lint/mypy
make black
```
Use these commands instead of inlining the related utility directly with python,
e.g. prefer "make link/black" over "python -m black ...".  Note that each lint/xxx
Makefile rule is diagnostic only, e.g. lint/black detects errors but does not fix
them.  Note that "make black" reformats using our configuration rather than
checking whitespace.

Although uv is used internally and to install nb-wrangler, the test environment
does not include a .venv; hence when needed use "python" instead of
".venv/bin/python" or any other reference to ".venv".

## Architecture
- `nb_wrangler/` and sub-packages contains application packages
- `tests/` uses fakes; integration tests must not call external services by default.
- sample-specs contains sample nb-wrangler specs (e.g. `sample-specs/RomanNexus-2026.2.yaml`)
- the nbw alias script supports running nb_wrangler.main
- the nb-wrangler script optionally supports bootstrapping an nb-wrangler environment
- the nb-wrangler script optionally supports configuring the shell environment for nb-wrangler

## Change requirements
- Make the smallest change that solves the requested problem.
- Keep functions and methods simple and target SLOC within the 5-20 line range.
- In general use wrangler's logger module and subprocess execution routines.
- Do not duplicate nbw functionality in hubenv without strong reasons.
- Add or update focused tests for behavior changes.
- Minimize changes to the nbw app and nb_wrangler/*.py when implementing or modifying the hubenv app.
- Run relevant linting and tests; report commands not run and why.
- Do not modify .git or its contents.  Do not commit to git or push changes.
- Ask before changing public APIs, spec format.

## Post-consolidation governance (single development line)

`nbw` and `hubenv` now share one codebase on one line (`plan-b-rebased`, merging
into `main`).  These rules keep the two apps from diverging again:

- **Shared surface — protected.** A change to any *nbw* module that `hubenv` builds
  on, or to a file listed here, touches both apps.  The shared, behavior-affecting
  surface is: `cli.py`, `config.py`, `constants.py`, `spec_manager.py`,
  `spec_validator.py`, `pantry.py`, `wrangler.py`, `data_wrangler.py`,
  `data_manager.py`, `compiler.py`, `registry.py`, `injector.py`, `activation.py`,
  `utils.py`, the `nb-wrangler` bash script, and `pyproject.toml`.
- **Any change to a shared-surface file requires the full combined suite to pass
  and a review note on nbw impact *and* hubenv impact.**  `hubenv`-only modules
  (`nb_wrangler/hubenv/**`, `tests/hubenv/**`) do not, on their own, require this.
- **Do not duplicate nbw functionality in hubenv.**  Follow the existing pattern:
  `hubenv data`/`verify` are thin wrappers over nbw's flag-driven steps.  New hubenv
  verbs must wrap rather than re-implement download/symlink/compile logic.
- **No new hard dependencies for hubenv-only features.**  Lazy-import them or ship
  them as a `pyproject.toml` optional extra (see the `hubenv` extra for `tabulate`).
- **One spec schema for both apps.**  `spec_validator.py` is shared; any new spec
  field must be additive and gated by the validator plus `docs/specs/` (see
  `docs/spec-format` notes).  Both apps must stamp and validate `spec_sha256` via the
  single canonical routine `nb_wrangler.spec_manager.canonical_spec_sha256`.
- **Version cadence:** `nbw`-significant changes bump the minor version; hubenv-only
  changes may ride along but must be listed under a `hubenv:` note in `CHANGES.md` so
  the dormant/active split stays legible in release notes.
- **`hubenv` stays inert to `nbw` users** unless they opt in; no top-level `nbw`
  module may import `nb_wrangler.hubenv` (the only coupling is the `nb-wrangler`
  bash `act`/`setenv`/`deact` delegation, which now routes through the `nbw` CLI).

## Documentation
- README.md
- documentation under docs/
