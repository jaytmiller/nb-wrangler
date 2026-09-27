# `ppe` Implementation Phases — Index

> Sequential implementation plans for the Persistent Platform Environments CLI.
> Based on `docs/plan-b/plan-b-cli.md`. Execute top-to-bottom; each phase builds
> on the prior ones. Each file is a self-contained, executable plan.

## Phase order & rationale

The first **three** phases deliver the top-priority MVP: a working `ppe` that can
**create**, **save** (archive), and **restore** (unarchive) environments.
Remaining phases are ordered by platform-user value and implementation
dependency, most important first.

| # | Plan | Summary |
|---|------|---------|
| 1 | [01-ppe-foundation-and-create](01-ppe-foundation-and-create.md) | CLI scaffold, config/env handling, r/o pantry detection, `ppe env create` (full). |
| 2 | [02-ppe-env-save](02-ppe-env-save.md) | `ppe env save` — pack a live env into a pantry "can". |
| 3 | [03-ppe-env-restore](03-ppe-env-restore.md) | `ppe env restore` — unpack a "can", register kernel, eval-able exports, idempotency. |
| 4 | [04-ppe-env-ls-and-info](04-ppe-env-ls-and-info.md) | `ppe env ls` + `info` + shadowing disambiguation. |
| 5 | [05-ppe-env-install-uninstall-and-relock](05-ppe-env-install-uninstall-and-relock.md) | `ppe env install/uninstall` + `ppe env relock` (explicit re-curate). |
| 6 | [06-ppe-env-rm](06-ppe-env-rm.md) | `ppe env rm` (interactive / `--yes`). |
| 7 | [07-ppe-env-ensure-register-unregister](07-ppe-env-ensure-register-unregister.md) | `ppe env ensure` + `register/unregister`. |
| 8 | [08-ppe-var](08-ppe-var.md) | `ppe var add/rm/ls`. |
| 9 | [09-ppe-data](09-ppe-data.md) | `ppe data ls/download/unpack/pack/clean`. |
| 10 | [10-ppe-export-status-doctor](10-ppe-export-status-doctor.md) | `ppe export` + `status` + `doctor`. |
| 11 | [11-shell-completions-and-polish](11-shell-completions-and-polish.md) | bash/zsh/fish completions, end-to-end tests, docs wiring. |

## Common scaffolding conventions

All phases follow these conventions (established in Phase 1 and reused):

- **Entry point:** add `ppe = "nb_wrangler.ppe.cli:main"` to
  `[project.scripts]` in `pyproject.toml`.
- **Package:** new `nb_wrangler/ppe/` with `__init__.py` and `cli.py`.
- **Reuse, don't reimplement:** build on `nb_wrangler/constants.py`
  (`NBW_ROOT`, `NBW_PANTRY_DIRS`, `NBW_MAMBA_CMD`, `NBW_PIP_CMD`),
  `nb_wrangler/pantry.py` (`NbwPantry`/`NbwPantrySet`),
  `nb_wrangler/environment.py` (`WranglerEnvable`, pack/unpack),
  `nb_wrangler/registry.py` (kernel JSON), and `nb_wrangler/logger.py`.
- **Logging/subprocess:** use the wrangler logger module and its subprocess
  execution routines (per AGENTS.md), not bare `subprocess`/`print`.
- **Style/typing:** pass `make lint/flake8`, `make lint/black`, `make lint/mypy`;
  keep functions in the 5–20 SLOC range (per AGENTS.md).
- **Tests:** `make unit-test` with fakes; no external services by default.

## Executing a phase

For each phase:
1. Read the plan file.
2. Implement the "Tasks" checklist.
3. Run `make unit-test` and the listed validation commands.
4. Verify acceptance criteria before moving to the next phase.