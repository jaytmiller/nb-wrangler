# Phase 8 — `ppe var` (env vars)

> Deliverable: `ppe var add/rm/ls NAME [VAR=VALUE|GLOB...] [--export]
> [--format table|json]`. Depends on Phase 1.

## Goal

Manage the environment variables a PPE environment defines for notebooks and
terminals — stored in the implicit wrangler spec and injected at kernel
registration time, *not* by managing users' shell dotfiles.

## Scope

**In:**
- `ppe var ls NAME [GLOB...] [--export] [--format table|json]`
  - Lists env vars the spec defines for `NAME` (a limited, curated subset,
    *not* all of `printenv`).
  - Default: two-column table (VAR, VALUE).
  - `--export`: print `export VAR=VALUE` lines suitable for `eval`.
  - `--format table|json`.
- `ppe var add NAME VAR=VALUE...`
  - Adds/updates env vars in the implicit spec *and* the kernel definition
    (so notebooks see them).
- `ppe var rm NAME GLOB...`
  - Removes vars (by glob) from the implicit spec + kernel definition only.

**Out:**
- Managing vars via arbitrary shell dotfiles ("var exports rc") — explicitly
  *not* done; users `eval "$(ppe var ls NAME --export)"` if they want them in
  a terminal.

## Design notes

- **Source of truth = the implicit spec.** Vars live in the spec
  (`environment_vars` section analog) and are re-applied during
  `ppe env register`/restore (Phase 3/7). `add`/`rm` edit the spec and refresh
  the kernel JSON.
- **No dotfile management:** this avoids the "three places to edit" leak from
  the original plan (spec, kernel, rc). Two places only: spec + kernel, both
  wrangler-owned.
- **`ls` scope:** only vars the *spec* declares (data paths, etc.), not every
  process env var — matches the consolidated spec's "very limited subset."

## Prerequisites / dependencies

- Phase 1 (implicit spec for `NAME`).
- Phase 7 (`register` refreshes the kernel JSON after spec edits).

## Files to create / modify

- **Modify** `nb_wrangler/ppe/cli.py` — replace `var` stub subcommands.
- **Create** `tests/ppe/test_var.py` — fake spec edits; `--export` lines; glob
  rm (fakes for spec + kernel JSON).

## Tasks

- [ ] `var ls`: read vars from the implicit spec; table/default; `--export`;
      `--format json`; `GLOB...` filter.
- [ ] `var add`: update spec var dict + refresh kernel JSON for `NAME`.
- [ ] `var rm`: remove glob-matched vars from spec + refresh kernel JSON.
- [ ] Tests: ls table vs export vs json; add then ls; rm glob; kernel refresh
      called.

## Testing / validation

```sh
make unit-test
make lint/flake8 && make lint/black && make lint/mypy
ppe var ls demo
ppe var ls demo --export | head
ppe var add demo DEBUG=1 API_KEY=secret
ppe var rm demo API_*
```

## Acceptance criteria

- `ppe var ls demo` lists the spec-declared vars (table by default).
- `--export` prints `export VAR=VALUE` lines.
- `add` updates the spec and the live kernel definition.
- `rm GLOB` removes matching vars from both spec and kernel.
- No users' shell dotfiles are modified.