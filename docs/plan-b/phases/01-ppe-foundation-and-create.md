# Phase 1 — `ppe` CLI foundation + `ppe env create`

> Deliverable: a `ppe` command on PATH with a subcommand-group CLI scaffold.
> `ppe env create` is fully implemented; other env subcommands exist but print
> "not yet implemented" (implemented in later phases). This is the foundation
> all later phases build on.

## Goal

Stand up the `ppe` tool so that `ppe env create --from-requirements ...` works
end-to-end, backed by wrangler's existing environment install machinery, and so
that the CLI structure (subcommand groups + r/o pantry detection) is reusable.

## Scope

**In:**
- `ppe` console entry point + `nb_wrangler/ppe/` package skeleton.
- Argparse CLI with subcommand groups: `env`, `var`, `data`, `export`,
  `status`, `doctor`.
- `env` group: `create` (implemented) + `ls/info/restore/save/rm/install/
  uninstall/relock/ensure/register/unregister` (stubs returning a clear
  "not yet implemented" error, exit code 2).
- Configuration/env handling: load `NBW_ROOT`/`NBW_PANTRY_DIRS` from
  `nb_wrangler/constants.py`; classify pantries as r/w vs r/o at startup.
- `ppe env create` supporting all seed sources from the spec:
  `--from-empty`, `--from-requirements <FILE...>`, `--from-mamba-spec <FILE>`,
  `--from-wrangler-spec <FILE>`, `--from-notebooks <URL|PATH...>`, with
  `--name`, `--display-name`, `--python`, `--dry-run`.
- Logging wired to the wrangler logger.

**Out:**
- `save`/`restore`/`ls`/`rm`/etc. behavior (later phases).
- `var`/`data`/`export`/`status`/`doctor` behavior (later phases) — only
  stubbed here.

## Design notes

- **Subcommand groups via nested argparse subparsers:** top-level subparsers
  for `env`/`var`/`data`/`export`/`status`/`doctor`; under `env`, subparsers
  per action. `ppe env create` reuses the in-progress `cli.py` patterns as a
  reference for argparse style, but is otherwise independent.
- **Create delegates to wrangler, doesn't duplicate it:** `create` seeds the
  implicit wrangler spec (a small in-memory spec dict or a temp spec.yaml)
  from the chosen source, then invokes wrangler's environment-install path
  (see `nb_wrangler/environment.py` `WranglerEnvable` and the `--env-init`/
  `--curate` flow in `cli.py`). `--dry-run` builds and prints the seeded spec
  without installing.
- **r/o detection:** `os.access(pantry, os.W_OK)` per `NBW_PANTRY_DIRS` entry;
  store a flag per pantry. Exposed (read-only here) for Phases 2/4/5/6.
- **`--name` over positional:** uniform flag-based naming across all commands
  (per the consolidated spec). Keep an optional positional `NAME` as a
  back-compat alias only if trivial; prefer flags.

## Prerequisites / dependencies

- None (this is the first phase). Reads `nb_wrangler/pantry.py`,
  `nb_wrangler/environment.py`, `nb_wrangler/constants.py`,
  `nb_wrangler/logger.py` for reuse.

## Files to create / modify

- **Create** `nb_wrangler/ppe/__init__.py`
- **Create** `nb_wrangler/ppe/cli.py` — main entry, argparse scaffold,
  `ppe env create`.
- **Create** `nb_wrangler/ppe/config.py` — pantry config + r/o classification
  (thin wrapper over `constants.NBW_PANTRY_DIRS`).
- **Modify** `pyproject.toml` — add
  `ppe = "nb_wrangler.ppe.cli:main"` under `[project.scripts]`.
- **Create** `tests/ppe/test_create.py` — unit tests (fakes for install, as
  instructed in AGENTS.md).

## Tasks

- [ ] `ppe` package skeleton + `main()` entry returning a clean exit code.
- [ ] Top-level argparse: `env`/`var`/`data`/`export`/`status`/`doctor`
      subparsers, each with `--help` and a default "not yet implemented" for
      everything except `env create`.
- [ ] `env` subparsers: `create`/`ls`/`info`/`restore`/`save`/`rm`/`install`/
      `uninstall`/`relock`/`ensure`/`register`/`unregister`; all non-`create`
      return exit code 2 + message.
- [ ] `ppe/config.py`: load pantries, classify r/w vs r/o, expose
      `writable_pantries()` / `is_writable(pantry)`.
- [ ] `ppe env create`: parse seed sources + flags; build seeded spec;
      `--dry-run` prints spec to stdout and exits; non-dry-run installs via
      wrangler env machinery; registers nothing in Jupyter yet (that's restore).
- [ ] Logging via `nb_wrangler/logger.py`.
- [ ] `pyproject.toml` script entry.
- [ ] Unit tests: CLI parse of each `--from-*`, r/o detection, `create
      --dry-run` output, "not implemented" stubs.

## Testing / validation

```sh
make unit-test            # adds tests/ppe/
make lint/flake8 && make lint/black && make lint/mypy
ppe env create --help
ppe env create --from-empty --name demo --python 3.11 --dry-run
ppe var ls --help         # should say "not yet implemented"
```

## Acceptance criteria

- `ppe env create --from-requirements requirements.txt --name X --python 3.11`
  installs a live environment usable by `mamba activate X`.
- `ppe env create --dry-run` prints the seeded spec and exits 0 without
  installing.
- `ppe env save` (and the other unimplemented subcommands) returns a clear
  "not yet implemented" error, not a traceback.
- `make lint/flake8`, `make lint/black`, `make lint/mypy` pass on new code.
- r/o pantries are detected and reported (visible via a hidden `--debug` or
  unit test even though no command uses it yet).