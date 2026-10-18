# Plan: Resolve `hubenv` rough edges RE-01 … RE-13

**Scope (chosen, all decisions user-confirmed):** Implement a fix for *every* rough
edge item in `docs/specs/hubenv.md` §7 (RE-01 … RE-13), in code **and** docs under
`/workspace/nb-wrangler`. No new commands, no renames, no compat shims.

## Decisions (approved)

| ID | Decision |
|---|---|
| RE-01 | **Reject strictly** — `cli._main` switches `parse_known_args` → `parse_args`; unknown flags/positionals are argparse errors (exit 2). |
| RE-02 | **Adopt `HubenvError`** — move class `cli.py` → `_common.py` (keep a back-compat alias in `cli` to avoid a circular import); raise it from the `cmd_env_create` seed-failure path so `main()`'s handler is actually exercised. |
| RE-03 | **Probe ordering + clean errors** — `cmd_env_create` runs the `environment_exists()` probe *first* (even under `--dry-run`), before seed/mamba/pip probes; seed-build failures (`ValueError`/`OSError`) become `HubenvError` → clean stderr + exit 1, no traceback. |
| RE-04 | **Snippet + instructions** — `--at-boot` writes only `~/.hubenv/env-<name>.sh` and prints a `source` instruction; **no dotfile auto-edit**. `hubenv rm` deletes the snippet per deleted name. |
| RE-05 | **Remove the doctor EFS check entirely** (user's custom choice) — delete `check_efs_mount`/`detect_efs_mount`/`read_proc_mounts`; doctor = 4 checks. |
| RE-06 | **Regenerate completions to the flattened surface** — env verbs become top-level in all three shells; `activate`/`deactivate` added (they were missing); fix stale `_FISH_*` dicts. |
| RE-07 | **Honor `--display-name` in `ensure`** — thread through `EnsureArgs` → `cmd_env_restore`; register kernel as `display_name or env name`. |
| RE-08 | `var ls --export --format json` (both given) is a **usage error, exit 1**. |
| RE-09 | Bare `hubenv var` / `hubenv data` (no sub-command) → **exit 1** (was 0). |
| RE-10 | `export --to-requirements` with no pip packages → **clear warning, exit 0** (still "success"). |
| RE-11 | `var add` with no shelf spec → **error, exit 1**, hint `hubenv create`; `var ls`/`var rm` keep their empty-view fallback. |
| RE-12 | **Spec consumers (recommended)** — add `--pantry` to `export`, `var ls`, `var add`, `var rm`. `status`/`doctor`/`data *`/`register`/`unregister`/`activate`/`deactivate` unchanged (`data *` delegates to `data_manager`, which takes no pantry param — a deeper refactor, out of scope). |
| RE-13 | `rm` confirmation prompt goes to **stderr** (flushed); `stdin` read unchanged; **stdout stays machine-readable**. |

## Per-RE implementation

### RE-01 — strict parsing (`cli.py`)

- `cli.py:_main` (L117): `parser.parse_known_args(argv)` → `parser.parse_args(argv)`.
- Behavior: `hubenv create --nam …` → argparse prints `unrecognized arguments: --nam`
  to stderr, raises `SystemExit(2)`. Existing behavior for invalid subcommands
  (`hubenv env`, `completions powershell`) is unchanged (argparse already exits 2).
- **Test:** new test in `tests/hubenv/test_create.py` — `main(["create", "--from-empty",
  "--name", "demo", "--bogus-flag"])` raises `SystemExit` with code 2
  (same shape as `test_legacy_env_group_rejected`, L163 — keep that test green;
  it exercises the *subcommand* rejection path, RE-01 exercises the *flag* path).
- **Doc:** spec §4.1 L157-158 — rewrite the `parse_known_args` / "silently
  ignored" bullet: parsing is strict; unknown flags are an argparse usage error (exit 2).

### RE-02 — make `HubenvError` real (`cli.py`, `_common.py`)

- Move `class HubenvError` from `cli.py` (L41-48) into `_common.py`.
- `cli.py`: `from nb_wrangler.hubenv._common import HubenvError` (module-level
  name preserved → the name stays importable from `cli`; nothing else in the
  package or tests imports it, verified).
- No other handler changes in this RE; RE-03 is the first raiser.
- **Test:** covered by the RE-03 test (assert exit 1 + message, no traceback).

### RE-03 — `create` probe ordering + clean seed errors (`env_create.py`, `seeds.py`)

`cmd_env_create` today builds the seed (running `mamba env export` / `pip freeze`
for `--from-existing-env`) *before* checking whether the target env already
exists, and even under `--dry-run`; a probe failure raises `ValueError` →
traceback.

- In `cmd_env_create`:
  1. Run the existence probe (`EnvironmentManager().environment_exists(args.name)`)
     **first** — including under `--dry-run` — before any seed building.
  2. Wrap seed construction `build_seed_dict(args)` → `seed_from_existing_env` etc.
     in `except (ValueError, OSError) as exc:` → raise
     `HubenvError(f"Failed to seed spec for '{args.name}': {exc}", exit_code=1)`.
- `main()` then logs the message to stderr and returns 1 (this actually exercises
  the RE-02 mechanism for the first time).
- Keep `--dry-run` semantics: it prints the plan and returns 0; it just no longer
  runs slow/failing probes before the exists-check.
- **Test** (add to `tests/hubenv/test_create.py`):
  - `--from-existing-env` with the underlying probe patched to raise
    `ValueError` → `main(...)` returns **1**, stderr contains the clean message,
    and `"Traceback" not in err`.
  - Ordering: patch `environment_exists` and a seed builder with call recording;
    assert the exists-check ran **before** the seed build.
- **Doc:** spec §5.1 create "Rough edges" bullet → resolved;
  `hubenv-env-create.md` (both copies, keep byte-identical) §6/§8 notes about
  uncaught `ValueError` and probe ordering → rewrite to the new order + the
  `--save`/no-`--force` note unchanged.

### RE-04 — `--at-boot`: snippet + instructions, no bashrc edit (`env_restore.py`, `env_rm.py`)

- `env_restore.py:write_at_boot_snippet` (L135-157):
  - Keep: guarded, idempotent snippet write to `~/.hubenv/env-<name>.sh`.
  - **Delete** the `~/.bashrc` append block (L150-156).
  - Add: print the source instruction to stdout, e.g.
    ```
    At-boot snippet written to /home/u/.hubenv/env-NAME.sh
    To use it at shell startup, add this line to your rc file:
        source /home/u/.hubenv/env-NAME.sh
    ```
    (absolute path, so it is shell- and location-agnostic — no more bash-only
    assumption, and no silent `2>/dev/null || true` user-facing behavior change
    inside the snippet, which stays as-is).
- `env_rm.py:do_rm` (L153+): after successful deletion of each target, call a new
  `remove_at_boot_snippet(name)` (defined next to `write_at_boot_snippet` in
  `env_restore.py`, imported once — no circular import; `env_rm` already imports
  nothing from `env_restore`, and `env_restore` imports nothing from `env_rm`).
  The helper unlinks `~/.hubenv/env-<name>.sh` if present and prints one line
  to stderr (`get_logger().info`).
- **Test:**
  - `tests/hubenv/test_restore.py` L308-375 (`TestRestoreAtBoot`): `test_at_boot_writes_snippet`
    stays (add an assertion that the source instruction is on stdout);
    `test_at_boot_appends_to_bashrc` → **rewrite** as `test_at_boot_does_not_touch_bashrc`:
    pre-create `~/.bashrc`, run restore `--at-boot`, assert file content unchanged;
    `test_at_boot_idempotent_no_duplicate` → rewrite as "rewrite is idempotent /
    no duplicate snippet files".
  - `tests/hubenv/test_rm.py`: new test — snippet file pre-created, `main(["rm", "demo", "--yes"])`,
    assert `~/.hubenv/env-demo.sh` no longer exists.
- **Doc:** spec §5.1 restore (L346-352) → snippet-only behavior + source
  instruction; `docs/hubenv-howto.md` at-boot recipe → replace the "bashrc auto-
  edited" wording with the manual `source` step.

### RE-05 — remove the doctor EFS check (`doctor.py`)

- Delete `check_efs_mount` (L96), `detect_efs_mount` (L109), `read_proc_mounts`
  (L122); drop the `check_efs_mount(config)` line from `run_doctor_checks` (L28).
  Doctor now runs 4 checks: mamba, pantry-writability, kernel-JSON sanity,
  spec-only shelves.
- Remove the now-dead `os`/`Path` imports if unused (flake8 will tell us).
- **Test** (`tests/hubenv/test_export_status_doctor.py`):
  - `_all_checks_context` (L46-65): delete the `("…doctor.check_efs_mount", "efs")`
    patch entry (L57).
  - Any assertion counting "5 checks" or asserting the `"efs"` row → update to 4 /
    drop the row (`test_parses_doctor` L123 and friends).
- **Doc:** spec §5.4 doctor check list (L545-553) → remove item 3 (EFS), renumber;
  spec §7 RE-05 → resolved; `docs/hubenv-howto.md` + `README.md`: grep for "EFS"
  and delete/replace the doctor row reference.

### RE-06 — completions match the flattened surface (`completions.py`)

Data-only changes (the bash/zsh/fish generators are driven by these two structures
and need no logic change):

- `_HUBENV_COMMAND_TREE` (L36-54): **remove** the `"env"` key; keep
  `{"var": [ls, add, rm], "data": [ls, download, unpack, pack, clean],
  "completions": [bash, zsh, fish]}`.
- `_TOP_LEVEL_ONLY` (L56): extend to the **14 env verbs** (parser order from
  `_add_env_subcommands` L116-155: `create save restore ls info install
  uninstall relock rm ensure register unregister activate deactivate`) **plus**
  `export status doctor`.
- `_FISH_DESCRIPTIONS` (L197-205): remove `"env"`, add a description for each of
  the 14 verbs (reuse the parser help strings, e.g. `"activate": "Print a shell
  snippet that activates an environment by path"`), keep `var/data/export/
  status/doctor/completions`.
- `_FISH_SUBCODESCRIPTIONS` (L207-239): delete the `"env"` sub-dict; keep
  `var`/`data`/`completions`.
- Result: `hubenv <TAB>` offers all 19 top-level commands; `hubenv var <TAB>`
  offers `ls add rm`; fish no longer emits `__fish_seen_subcommand_from env`;
  `activate`/`deactivate` (previously missing) now complete.
- **Test** (`tests/hubenv/test_e2e.py` `TestCompletions`):
  - `test_bash_completion_script` L449: drop `assert "env" in out`; assert the
    top-level verb set instead (`"create save restore …"` in the `top=…` line).
  - `test_zsh_completion_script` L460, `test_fish_completion_script` L470: same.
  - `test_fish_sees_subcommand_for_env` L481: rename/rewrite to assert
    `"__fish_seen_subcommand_from var" in out` (and no `…_from env`).
  - `test_completions_invalid_shell_errors` stays green.
- **Doc:** spec §5.7 tools/completions section (mentions the stale tree if any)
  + §7 RE-06 resolved.

### RE-07 — `ensure --display-name` honored (`env_ensure.py`, `env_restore.py`)

- `env_ensure.py:EnsureArgs.__init__` (L14): add
  `display_name: Optional[str] = None`; `cmd_env_ensure` passes
  `display_name=args.display_name` when building `EnsureArgs`.
- `env_restore.py:47`: `em.register_environment(args.name, args.name, {})` →
  `em.register_environment(args.name, getattr(args, "display_name", None) or args.name, {})`.
  (`getattr` guard: `hubenv restore` has no `--display-name` flag; `ensure` does.
  If it appears later on `restore`, the same line picks it up for free.)
- **Test** (`tests/hubenv/test_ensure_register.py`): new test — `ensure NAME
  --display-name "My Env"` with `register_environment` patched → assert it was
  called with `("NAME", "My Env", …)`; and the no-flag path still passes `("NAME", "NAME", …)`.
- **Doc:** spec §5.1 (RE-07 rough-edge notes L346, L371) → resolved.

### RE-08 — `var ls` conflict is a usage error (`var.py`)

- `cmd_var_ls` (L12-24): at the top,
  `if args.export and args.format == "json":` → `get_logger().error("…
  --export and --format json are mutually exclusive; choose one.")`; return **1**.
- `--format table --export` remains valid (table is also an "export-ish" output
  but the current code treats `--export` as the "print VAR=VALUE lines" mode and
  `--format` as `table|json` — keep that; only the json+export combo is rejected).
- **Test** (`tests/hubenv/test_var.py`): new test — `main(["var", "ls", "demo",
  "--export", "--format", "json"])` → rc **1**, clear message on stderr; existing
  `test_ls_export` (L132) and `test_ls_json` (L144) must stay green.
- **Doc:** spec §5.5 `var ls` synop/behavior (~L583-592) + §7 RE-08 noted resolved.

### RE-09 — bare `var`/`data` exits 1 (`cli.py`)

- `cli.py:_dispatch_var` / `_dispatch_data` (L192-216): the "no sub-command"
  branch currently `get_logger().error(...); return 0` → change to `return 1`.
- **Test:** new test (either `test_var.py` or `test_e2e.py`) — `main(["var"])`
  and `main(["data"])` → rc **1** (assert the error message on stderr).
- **Doc:** spec §4.1 L163-164 (the `(pre-existing rough edge, RE-09)` clause) →
  "…logs an error and exits **1**".

### RE-10 — `export --to-requirements` empty → warn, exit 0 (`export.py`)

- In `format_export` (or `cmd_export`) the `--to-requirements` branch: when
  `extract_pip_packages(spec)` yields an empty list → `get_logger().warning("spec
  for 'NAME' has no pip packages; empty requirements output")` and continue.
  Exit code stays **0**; nothing else changes.
- **Test** (`tests/hubenv/test_export_status_doctor.py`): new test — spec without
  pip deps + `--to-requirements` → rc **0** and (empty stdout, or `-o` file empty);
  keep `test_export_to_requirements` (L182) green.
- **Doc:** spec §5.5 export "Rough edges" (L579) → resolved (warning behavior);
  §7 RE-10 resolved.

### RE-11 — `var add` requires an existing shelf (`var.py`)

- `cmd_var_add`: before updating, check `config.shelf_spec_path(args.name).exists()`;
  if the shelf/spec is absent → `get_logger().error(f"No spec found for env
  '{args.name}'. Create it first: hubenv create {name} --from-empty …")`;
  return **1** — and do **not** create the shelf (drop the accidental
  `seed_from_empty` fallback on the add path only).
- `cmd_var_ls` / `cmd_var_rm` keep today's behavior (missing spec → empty view /
  no-op, exit 0) — their tests (`test_ls_missing_spec_no_error` L180,
  `test_rm_no_match_is_noop` L290) must stay green.
- **Test** (`tests/hubenv/test_var.py`): new test — `main(["var", "add",
  "ghost", "A=1"])` with no shelf → rc **1** and no `shelves/ghost` dir created;
  existing `TestVarAdd` tests (all pre-create the spec) stay green.
- **Doc:** spec §5.5 `var add` (~L604, the "command **creates** the shelf on
  first use" line) → rewrite to the new required-shelf behavior; §7 RE-11
  resolved.

### RE-12 — `--pantry` on spec readers (`parser.py`, `export.py`, `var.py`, `_common.py`)

- `_common.py`: add
  ```python
  def store_for(args) -> PantryStore:
      """Return PantryStore scoped to args.pantry if present, else default chain."""
      if getattr(args, "pantry", None):
          return PantryStore(paths=[Path(args.pantry)])
      return PantryStore()
  ```
- `parser.py`: add a `--pantry` flag to `_add_export_args` (L567+),
  `_add_var_ls_args`, `_add_var_add_args`, `_add_var_rm_args` — same pattern as
  the existing ones (L587-589 style), help text: "Restrict shelf search to a
  single pantry directory".
- `export.py:cmd_export` (L20) and `var.py:cmd_var_ls` (L14) / `cmd_var_add` /
  `cmd_var_rm` (wherever they build `PantryStore()`) → `config = store_for(args)`.
- **Not in scope (recorded in spec):** `status`, `doctor`, `data *`,
  `register`/`unregister`/`activate`/`deactivate` (kernel-side or
  `data_manager`-bound, which take no pantry param).
- **Test** (`tests/hubenv/test_var.py` + `test_export_status_doctor.py`):
  - `var ls demo --pantry EMPTY_PANTRY` → empty view (rc 0); `--pantry REAL_PANTRY`
    → vars listed.
  - `export demo --pantry EMPTY_PANTRY` → "No spec found" (rc 1); `--pantry
    REAL_PANTRY` → spec export (rc 0).
- **Doc:** spec §4.5 pantry resolution + §7 RE-12 → "export, var ls/add/rm
  accept `--pantry`; the rest intentionally do not (see note)".

### RE-13 — `rm` prompt on stderr (`env_rm.py`)

- `prompt_rm_confirmation` (L144-150): replace `input("Proceed? (y/N): ")` with
  `sys.stderr` output + bare `input()`:
  ```python
  print("Proceed? (y/N): ", end="", file=sys.stderr, flush=True)
  response = input().strip().lower()
  ```
  (keep the `EOFError` → abort path; `sys` import already present or add it).
- `confirm_and_rm` L59-62 and `do_rm` plan prints stay on stdout.
- **Test** (`tests/hubenv/test_rm.py`):
  - L369 `assert "y/N" in mock_input.call_args[0][0]` → `input()` is now called
    with **no args**: assert `mock_input.call_args[0] == ()` and that "y/N"
    appears on **stderr** (`capsys.readouterr().err`).
  - L198 (`--yes` path, "Proceed?" not in out) stays green.
  - `tests/hubenv/test_e2e.py` L263-269 (input patched "n"/"y") unaffected.
- **Doc:** spec §4.3 output discipline + §7 RE-13 → resolved.

## Spec/doc updates (cross-RE)

- `docs/specs/hubenv.md`:
  - §4.1 — strict parsing (RE-01); bare `var`/`data` exit 1 (RE-09).
  - §4.4 — exit-code table: note `argparse usage errors → 2` unchanged, plus the
    new explicit returns (RE-08/09/11 → 1; RE-10 stays 0).
  - §5.1 — create ordering/clean errors (RE-02/03), restore at-boot (RE-04),
    ensure display-name (RE-07).
  - §5.4 — doctor = 4 checks (RE-05).
  - §5.5 — export warning + `--pantry` (RE-10/12), `var ls/add/rm` behavior
    (RE-08/11/12).
  - §7 — mark **all 13 REs resolved** (add a Status column or per-row note with a
    pointer back to this plan).
- `docs/specs/hubenv-env-create.md` (+ keep `specs/hubenv-env-create.md` copy
  byte-identical if the repo still carries it): RE-02/RE-03 rough-edge notes →
  resolved behavior.
- `docs/hubenv-howto.md`: at-boot recipe → snippet + manual `source` (RE-04);
  remove/adjust EFS doctor row (RE-05); scrub any stale `hubenv env …` or EFS
  mentions.
- `docs/CHANGES.md`: one entry summarizing the user-visible changes:
  stricter flag parsing (typos now fail), bare `var`/`data` → exit 1, `var add`
  no longer auto-creates a shelf, `var ls --export --format json` rejected,
  `--at-boot` no longer edits `~/.bashrc` (snippet + `source` line; `rm` cleans
  up snippets), `doctor` no longer checks EFS, new `--pantry` on
  `export`/`var *`, `ensure --display-name` honored, `rm` prompt on stderr, and
  shell completions now match the flattened command tree.
  (Behavioral changes are breaking for scripts that relied on the old quirks —
  the flatten-plan precedent was to record these in the changelog rather than
  ship shim compatibility.)

## Verification

Per AGENTS.md, `make` targets only (plain `python`, no `.venv` references):

```bash
make unit-test          # full suite incl. the new focused tests
make lint/flake8
make lint/black
make lint/radon         # watch SLOC/complexity after cli.py changes
make lint/mypy
```

Manual CLI spot-checks (with a scratch `NBW_PANTRY_DIRS` under `/tmp/opencode`):

```bash
python -m nb_wrangler.hubenv create --from-empty --name demo --nam   # exit 2 (RE-01)
python -m nb_wrangler.hubenv create --from-existing-env missing --name demo --dry-run   # clean msg, exit 1 (RE-03)
python -m nb_wrangler.hubenv var                                     # exit 1 (RE-09)
python -m nb_wrangler.hubenv var ls ghost --export --format json     # exit 1 (RE-08)
python -m nb_wrangler.hubenv var add ghost A=1                       # exit 1 + create hint (RE-11)
python -m nb_wrangler.hubenv export ghost --to-requirements          # warning, exit 0 (RE-10)
python -m nb_wrangler.hubenv doctor --format json                    # 4 checks, no efs (RE-05)
python -m nb_wrangler.hubenv completions fish | grep -c "from env"   # 0 (RE-06)
python -m nb_wrangler.hubenv rm demo <<< n                            # prompt on stderr (RE-13)
```

## Risk assessment

- **RE-01 is the only genuinely user-visible parsing change**: scripts that
  relied on typo'd flags being silently dropped will now fail (exit 2). Accepted
  (user decision). The existing `test_create.py:163` subcommand-rejection test is
  orthogonal and stays green.
- **Circular-import trap (RE-02):** `cli.py` imports command modules; moving
  `HubenvError` into `_common.py` (imported by all of them) is the safe
  direction; `cli` re-imports it so `from nb_wrangler.hubenv.cli import
  HubenvError` keeps working.
- **`getattr(args, "display_name", None)` (RE-07):** `restore` args have no such
  attribute today — guard prevents `AttributeError`; if `restore` gains
  `--display-name` later, the behavior extends automatically.
- **Radon/SLOC (RE-03/09/11):** keep new handlers ≤ ~20 SLOC (AGENTS.md); the
  `except (ValueError, OSError)` block and the spec-presence check are 3-6 lines
  each — no problem, but verify with `make lint/radon`.
- **EFS tests (RE-05):** `test_export_status_doctor.py` patches 5 functions via
  `_all_checks_context`; removing one patch line is mandatory else `AttributeError`
  at import of the patched target.
- **Completions (RE-06):** data-only edit, generator logic untouched — lowest-risk
  item; the bash `top=` line and the fish `__fish_seen_subcommand_from` greps are
  the spot checks.
- **Docs split-brain:** `specs/hubenv-env-create.md` vs `docs/specs/` copy — edit
  **both** in the same pass and `diff` to confirm identity (or the plan note
  "whichever copy exists in the tree").
- **Out of scope / not planned:** adding `--pantry` to `data *`/`status`/`doctor`
  (would require `data_manager`/`EnvironmentManager` signature changes); a compat
  shim for `hubenv env …`; a dotfile manager for at-boot activation (users manage
  their own rc files per the RE-04 decision).

## Execution order

| Order | Items | Why this order |
|-------|-------|----------------|
| 1 | RE-01, RE-02, RE-09 (`cli.py`, `_common.py`) + tests | Parser/dispatch foundation; RE-02 gives RE-03 its error vehicle |
| 2 | RE-03 (`env_create.py`) + tests | First `HubenvError` raiser; exercises RE-02 in `main()` |
| 3 | RE-07 (`env_ensure.py`, `env_restore.py`) + tests | Small, isolated |
| 4 | RE-04 (`env_restore.py`, `env_rm.py`) + tests | Touches restore + rm; tests rewrite `TestRestoreAtBoot` |
| 5 | RE-08, RE-11, RE-12 (`var.py`, `_common.py`, `parser.py`) + tests | Same two files; do together |
| 6 | RE-10, RE-12 (`export.py`) + tests | One handler, two REs |
| 7 | RE-13 (`env_rm.py`) + tests | Prompt move + test assertion updates |
| 8 | RE-05 (`doctor.py`) + tests | Dead-code removal + test patch cleanup |
| 9 | RE-06 (`completions.py`) + tests | Data-only; independent |
| 10 | Docs: `hubenv.md` §4/§5/§7, `hubenv-env-create.md`, `hubenv-howto.md`, `CHANGES.md` | After all behavior is settled |
| 11 | `make unit-test` + all four linters; manual CLI spot-checks | Final gate |
