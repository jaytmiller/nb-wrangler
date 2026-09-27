# Phase 10 — `ppe export` + `ppe status` + `ppe doctor`

> Deliverable: `ppe export NAME [--to-mamba-spec|--to-requirements|--to-wrangler-spec]
> [-o FILE|-]`, `ppe status`, `ppe doctor`. Depends on Phases 1, 4.

## Goal

Make the implicit wrangler spec portable/exportable, give users a single
onboarding answer ("what do I have and what's active?"), and a self-test that
replaces the most common support questions.

## Scope

**In:**
- `ppe export NAME --to-mamba-spec|--to-requirements|--to-wrangler-spec [-o FILE|-]`
  - Extract the implicit wrangler spec (or a derived format) for `NAME`.
  - `-` writes to stdout.
  - Derived `--to-requirements`/`--to-mamba-spec` are generated from the locked
    spec while the env is available.
- `ppe status`
  - Active env (if any), active pantry path, live vs archived state, kernel
    registration state, and r/w status of each pantry.
- `ppe doctor`
  - Self-test: micromamba/mamba availability, `NBW_PANTRY` writability, EFS
    mount status, kernel-JSON sanity.

**Out:**
- A full GUI/labextension kernel picker (the "Jupyter labextension environment
  management" exotic direction in `plan-b-reqs.md`) — not in scope here.

## Design notes

- **`export`:** mirror the root doc's richer multi-format export. Reuse wrangler's
  spec-to-requirements/mamba conversion (`compiler.py`) rather than reimplementing.
- **`status`:** aggregate from `NBW_ROOT`, `NBW_PANTRY_DIRS`, Jupyter
  `kernelspec list`. Keep output concise (table or json).
- **`doctor`:** a sequence of checks, each printing PASS/FAIL + a hint. Use
  `shutil.which`, `os.access`, a mount check (`os.stat` st_dev or `/proc/mounts`
  parsing for EFS), and a kernelspec sanity read.
- **Format:** `status`/`doctor` default to a human table; `--format json` for
  tooling.

## Prerequisites / dependencies

- Phase 1 (pantry/env state, r/o detection).
- Phase 4 (`list_shelves`/`list_live_envs`).
- `nb_wrangler/registry.py` (kernelspec list/sanity).
- `nb_wrangler/compiler.py` (spec → requirements/mamba).

## Files to create / modify

- **Modify** `nb_wrangler/ppe/cli.py` — replace `export`/`status`/`doctor` stubs.
- **Create** `tests/ppe/test_export_status_doctor.py` — fakes for export formats,
  status aggregation, doctor checks.

## Tasks

- [ ] `export`: pick format flag; load implicit spec for `NAME`; convert; write
      to `-o FILE|`-.
- [ ] `status`: aggregate active env, pantry path, live/archived, kernel state,
      r/w per pantry; table/json.
- [ ] `doctor`: checks for mamba/micromamba, pantry writability, EFS mount,
      kernelspec sanity; `--format json` option.
- [ ] Tests: each export format parses; status fields present; doctor reports
      pass/fail per check (fakes).

## Testing / validation

```sh
make unit-test
make lint/flake8 && make lint/black && make lint/mypy
ppe export demo --to-requirements -
ppe export demo --to-wrangler-spec -o demo-spec.yaml
ppe status
ppe status --format json
ppe doctor
```

## Acceptance criteria

- `ppe export demo --to-requirements -` prints a valid requirements list to stdout.
- `--to-wrangler-spec` writes a loadable spec YAML to the given file/`-`.
- `ppe status` shows active env, pantry path, live/archived, kernel state, r/w.
- `ppe doctor` runs each check and reports PASS/FAIL with a hint for failures.