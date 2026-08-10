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
```
Use these commands instead of inlining the related utility directly with python,
e.g. prefer "make link/black" over "python -m black ..." because the latter requires
confirmation but the former wll not.  Although uv is used internally and to install
nb-wrangler, the test environment does not include a .venv;  hence when needed use
"python" instead of ".venv/bin/python" or any other reference to ".venv".

## Architecture
- `nb_wrangler/` and sub-packages contains application packages
- `tests/` uses fakes; integration tests must not call external services by default.
- sample-specs contains sample nb-wrangler specs (e.g. `specs/samples/RomanNexus-2026.2.yaml`)
- the nbw alias script supports running nb_wrangler.main
- the nb-wrangler script optionally supports bootstrapping an nb-wrangler environment
- the nb-wrangler script optionally supports configuring the shell environment for nb-wrangler

## Change requirements
- Make the smallest change that solves the requested problem.
- Keep functions and methods simple and target SLOC within the 5-20 line range.
- In general use wrangler's logger module and subprocess execution routines.
- Add or update focused tests for behavior changes.
- Run relevant linting and tests; report commands not run and why.
- Ask before changing public APIs, spec format.

## Documentation
- README.md
- documentation under docs/
