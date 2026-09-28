# Phase 8b — `ppe var add` / `ppe var rm` (mutate env vars)

> Deliverable: `ppe var add NAME VAR=VALUE...` and `ppe var rm NAME GLOB...`.
> Depends on Phase 8a (shared `var` group + spec helpers) and Phase 7
> (`register` to refresh the kernel JSON after spec edits).

## Goal

Mutate the environment variables a PPE environment declares. Edits go to the
implicit wrangler spec (the source of truth) and are then re-applied to the
live Jupyter kernel so notebooks see them. Users' shell dotfiles are never
touched — they opt in with `eval "$(ppe var ls NAME --export)"` if they want
the vars in a terminal.

## Scope

**In:**
- `ppe var add NAME VAR=VALUE...`
  - Adds/updates env vars in the implicit spec's `environment_vars` dict.
  - Parsing splits on the *first* `=` so values may themselves contain `=`.
  - On success: persist the spec, then refresh the kernel for `NAME` via
    `EnvironmentManager.register_environment(NAME, NAME, env_vars)` so the
    kernel JSON carries the new vars.
  - Invalid assignment (no `=`) → error to stderr, exit 1, **no** spec write.
- `ppe var rm NAME GLOB...`
  - Removes glob-matched vars from the implicit spec + refreshes the kernel.
  - No matches → print `No matching variables ...` and exit 0 (no-op, no
    save, no refresh).
- Kernel refresh is best-effort: the spec is already persisted; a failed
  refresh is reported on stderr as a warning rather than reverting the spec.

**Out:**
- Managing vars via shell dotfiles ("var exports rc") — explicitly *not* done.
- `--at-boot` snippeting — already handled in Phase 3's restore.

## Design notes

- **Two places only:** spec + kernel (both wrangler-owned). This avoids the
  "three places to edit" leak (spec, kernel, rc) from the original plan.
- **`add`/`rm` reuse** the spec helpers (`_load_ppe_spec`/`_save_ppe_spec`)
  and the `register_environment` call pattern already used by Phase 7's
  `register`. No hand-rolled Jupyter dirs.
- **Idempotent-ish:** `add` upserts; `rm` of an absent name is a no-op.

## Prerequisites / dependencies

- Phase 1 (implicit spec for `NAME`).
- Phase 8a (`var ls` exists; shared subcommands + test scaffolding).
- Phase 7 (`register` refreshes the kernel JSON; reuse the same call).

## Files to create / modify

- **Modify** `nb_wrangler/ppe/cli.py`:
  - Extend `_add_var_subcommands` so `add`/`rm` parse `name` +
    `assignments`/`globs`.
  - Extend `_dispatch_var` routing `add` → `_cmd_var_add`, `rm` → `_cmd_var_rm`.
  - Add `_cmd_var_add`, `_parse_var_assignments`, `_print_var_add_result`,
    `_cmd_var_rm`, `_remove_vars_by_glob`, `_print_var_rm_result`,
    `_refresh_kernel_vars` (calls `em.register_environment(name, name, vars)`).
- **Extend** `tests/ppe/test_var.py` (add subset):
  - Reuse `_write_spec`/`_read_spec` and the `NBW_ROOT` patch.
  - Patch `EnvironmentManager.register_environment` (returns bool).
  - Tests: add single (spec updated + register called with env vars); add
    multiple; value containing `=`; invalid assignment returns 1, no save;
    add when no `environment_vars` section exists; rm glob removes from spec
    + kernel; rm no-match is a no-op (no save, no register); rm exact name.

## Tasks

- [x] `var add`: parse `VAR=VALUE` (first-`=` split); validate; upsert into
      spec; persist; refresh kernel.
- [x] `var rm`: remove glob-matched vars from spec; refresh kernel; no-op on
      no match.
- [x] `_refresh_kernel_vars`: `register_environment(name, name, env_vars)`;
      warn on stderr if it fails (spec still saved).
- [x] Tests for all of the above (fakes for spec + kernel).

## Testing / validation

```sh
make unit-test TESTS=tests/ppe/test_var.py
make lint/flake8 && make lint/black && make lint/mypy
ppe var add demo DEBUG=1 API_KEY=secret
ppe var ls demo
ppe var rm demo API_*
ppe var ls demo
```

## Acceptance criteria

- `ppe var add demo DEBUG=1` updates the spec and refreshes the live kernel.
- `ppe var add` accepts multiple `VAR=VALUE` and values containing `=`.
- `ppe var add demo DEBUG` (no `=`) errors and leaves the spec unchanged.
- `ppe var rm demo API_*` removes matching vars from both spec and kernel.
- `ppe var rm demo NONEXISTENT_*` is a no-op (no save, no refresh).
- No user shell dotfiles are modified.