# Plan: Flatten `hubenv env …` → `hubenv …`

**Scope 1 (chosen):** Promote the `env` sub-sub-commands to the top level of the
`hubenv` CLI, dropping the now-redundant `env` group. Keep the `var` and `data`
groups as-is. This is the only group we flatten because it is the tool's *primary*
resource (environments) — its verbs read naturally without a leading noun.

## Context

`hubenv` was renamed from `ppe` (see
`docs/plan-b/phases/REFACTOR_PLAN_ppe_to_hubenv.md`). The old subcommand tree kept a
`env` group:

```
hubenv env create | save | restore | ls | info | install | uninstall | relock
         rm | ensure | register | unregister | activate | deactivate
hubenv var  ls | add | rm
hubenv data ls | download | unpack | pack | clean
hubenv export | status | doctor | completions <shell>
```

After the rename, `hubenv env create` is awkward: the tool name already says
"environment", so the leading `env` group is redundant. The goal is to read the
primary-resource verbs directly under the tool name:

```
hubenv create      →  create an environment
hubenv ls          →  list live envs and pantry shelves
hubenv var ls      →  (unchanged)
hubenv data clean  →  (unchanged)
```

### Why flatten `env` but keep `var`/`data`

- **`env` is the primary resource.** Its verbs are unambiguous on their own
  (`hubenv save` = save *an environment*). Dropping the noun matches the well-known
  `kubectl` pattern where the dominant resource's verbs sit at the top level
  (`kubectl get pods` … vs. a scoped sub-namespace).
- **`var`/`data` would collide if flattened.** `hubenv ls`, `hubenv var ls`, and
  `hubenv data ls` all mean `ls`; same for `rm`. Flattening all three either
  collides or forces ugly renames (`env-ls`, `var-ls`, `data-ls`). Keeping `var`
  and `data` as scope words is the clean `kubectl` shape: primary noun dropped,
  secondary nouns scoped.
- This keeps the change small and the new surface unambiguous.

### Tradeoff to acknowledge

`micromamba env create` / `conda env create` are phrases these users already type,
so the old `hubenv env …` mirrored the ecosystem. Flattening makes *hubenv's* own
surface cleaner but breaks that specific muscle-memory parallel. We accept this —
the redundancy of `env env` under the tool's own name outweighs it.

## Decision (already approved)

- **Flatten the `env` group → 14 top-level verbs.**
- **Keep `var` and `data` as subgroups.**
- No name collisions result (env verbs don't overlap `var`, `data`, `export`,
  `status`, `doctor`, `completions`).
- This is a **public CLI surface change** — scripts that call `hubenv env …` must be
  migrated. Handle via CHANGELOG, not a compat shim (shim would double the parser
  surface for a tool in active development).

## New command tree (target)

```
hubenv create | save | restore | ls | info | install | uninstall | relock
       rm | ensure | register | unregister | activate | deactivate
hubenv var  ls | add | rm                        (unchanged)
hubenv data ls | download | unpack | pack | clean (unchanged)
hubenv export | status | doctor | completions <shell> (unchanged)
```

## Affected code inventory

The change is mechanical and low-risk: command modules read only their own flags
(`args.name`, `args.pantry`, …) which do not change. Only these areas see edits.

| Area | Files | Count / Notes |
|------|-------|---------------|
| Parser     | `nb_wrangler/hubenv/parser.py`        | Rebuild env group as top-level subparsers |
| Dispatch   | `nb_wrangler/hubenv/cli.py`           | Collapse `_ENV_DISPATCH` into top dispatch |
| Completions| `nb_wrangler/hubenv/completions.py`   | Flatten env entries in the command tree |
| In-code strings | 15 `hubenv/*.py` modules        | ~35 `hubenv env …` docstring/help/hint refs |
| Tests      | 9 `tests/hubenv/*.py` files           | 127 argv `["env", …]` lists + parser-assertion fixes + 1 help test |
| Live spec  | `specs/hubenv-env-create.md`, `docs/specs/hubenv-env-create.md` (identical copies) | `hubenv env create` → `hubenv create` |
| Historical | `docs/plan-b/**`                    | Migration note only (not rewritten) |
| CHANGELOG  | `docs/CHANGES.md`                    | Note the breaking surface change |

Confirmed: `config.hubenv_command` is **not consumed anywhere** (only set in
`cli.py`; read by no command module and no logger path). So its *value format*
(`"env.create"` vs `"create"`) has no functional impact — updating it is cosmetic.

## Phase 1 — Parser (`parser.py`)

Goal: emit flat top-level subparsers for the 14 env verbs; remove the `env` group
and its `env_command` dest.

1. In `build_parser()`, replace the `_add_env_subcommands(subparsers)` call so the
   env verbs are added directly to the **top-level** `subparsers` (not a nested
   `env_parser`).
2. Drop the `env_parser = subparsers.add_parser("env", …)` and
   `env_sub = env_parser.add_subparsers(dest="env_command")` lines. The 14 `env_sub.add_parser(...)`
   calls become `subparsers.add_parser(...)`.
3. **Global flags (real gotcha):** today `_add_global_flags` is added to the `env`
   *group* parser (line 100) so `hubenv env --create --quiet` works but
   **`hubenv --quiet env create` is not** (flags only exist pre-`env`). After
   flattening, the flags must be reachable on the leaf commands:
   - Keep `_add_global_flags(parser)` on the top-level parser (already line 80), and
     - **add `_add_global_flags(<verb_parser>)` to each of the 14 promoted verb
       parsers** so `hubenv create --quiet` and `hubenv --quiet create` both parse.
   - `var` and `data` groups already add global flags — leave them.
   - `export`/`status`/`doctor` do **not** currently add global flags; leave them in
     scope only if trivial (optional, low priority).
4. Leave `_add_var_subcommands`, `_add_data_subcommands`,
   `_add_export_status_doctor_subcommands`, `_add_completions_subcommands` unchanged.
5. Optional: update the `env` group `"Environment management"` help string — it is
   gone; the per-verb `help=` texts carry the meaning (already descriptive).

## Phase 2 — Dispatch (`cli.py`)

Goal: collapse env dispatch into the top-level table.

1. `import` block (lines 14–20) already pulls in all `cmd_env_*` handlers — keep.
2. `_resolve_command_path(args)` (lines 100–110):
   - The `args.command == "env"` branch is removed — the env verbs are now the
     `command`. Simplify to: if `command in _ENV_VERBS: return args.command`
     (i.e. `"create"`, `"ls"`, …). Keep the `var.*` and `data.*` branches.
   - Since `hubenv_command` is not consumed, this is cosmetic; keep the field so we
     don't touch `WranglerConfig` (public config) needlessly.
3. `_main` dispatch table (lines 128–136): merge the `_ENV_DISPATCH` entries into
   the top `dispatch` dict, keyed by the bare verb names (`"create"`, `"save"`, …).
   - Keep `"var"`, `"data"` mapping to their group dispatchers, and
     `"export"`, `"status"`, `"doctor"`, `"completions"` unchanged.
4. Remove `_dispatch_env` (lines 190–200) and fold its "sub-command required"
   behavior away: at the top level there is no bare `env` token anymore, so the
   not-implemented / empty-group path for env is gone. Keep the equivalent for
   `var`/`data` (`_dispatch_var`, `_dispatch_data`).
   - `_cmd_not_implemented` stays (still reachable for unknown `var`/`data` leaves
     if any are stubbed).
5. Update the docstring at `cli.py:1` (fine as-is) and the `_env` module docstring
   strings (see Phase 3).

## Phase 3 — Completions (`completions.py`)

Goal: move env verbs from a group into the top-level completion set.

1. `_HUBENV_COMMAND_TREE`: promote the `"env": [...]` list so those 14 verbs are
   offered at position 2 only when appropriate. Since they are now **top-level**
   commands, the cleanest model is:
   - Add the 14 env verbs to `_TOP_LEVEL_ONLY` **or** keep a flat top-level command
     list. Simplest: extend `_TOP_LEVEL_ONLY` with the 14 verbs (`["export","status","doctor", …env verbs…]`),
     and remove the `"env"` key from `_HUBENV_COMMAND_TREE`.
   - Keep `"var"` and `"data"` in the tree (they still take a sub-command).
   - `"completions"` keeps its `[bash,zsh,fish]`.
2. `_all_groups()`: still returns tree keys + `_TOP_LEVEL_ONLY` — with env verbs now
   in `_TOP_LEVEL_ONLY` they appear in the top-level completion list correctly.
3. `_gen_bash`: loops over `_HUBENV_COMMAND_TREE` groups to build `*_cmds` lists;
   env verbs move to the top completion word set (`$top`). Verify the `cword -eq 1`
   branch (top level) now completes the env verbs, and `cword -eq 2` completes the
   `var`/`data` sub-commands.
4. `_gen_zsh`: `_zsh_desc(cmd)` resolves descriptions from `_FISH_DESCRIPTIONS` and
   `_FISH_SUBCODESCRIPTIONS`. Move the 14 env-verb descriptions into
   `_FISH_DESCRIPTIONS` (top-level) so they get a description string in the
   top-level `_describe` block; remove the `"env"` nested table from
   `_FISH_SUBCODESCRIPTIONS` (or leave for `var`/`data`).
5. `_gen_fish`: env verbs become `-n "__fish_use_subcommand"` top-level completions
   instead of `-n "__fish_seen_subcommand_from env"`. Adjust the generator loop
   accordingly; `var`/`data`/`completions` stay on the seen-subcommand path.
6. Update the module docstring examples (lines 10–27) that say `hubenv completions …` —
   unchanged, but confirm no `hubenv env …` examples there.
7. **Pre-existing gap (optional, low priority):** the completions tree currently
   omits `activate` and `deactivate` (present in `_ENV_DISPATCH` and the parser,
   absent from `_HUBENV_COMMAND_TREE["env"]` and `_FISH_SUBCODESCRIPTIONS["env"]`).
   Flattening won't make this worse, but since we're already editing these
   structures, add `activate`/`deactivate` to the top-level env-verb set so all
   14 verbs complete. Confirm with the maintainer whether they were dropped
   intentionally.

## Phase 4 — In-code string updates

Rewrite `hubenv env …` user-facing/docstring references to `hubenv …`. ~65
occurrences across (non-exhaustive list from the audit):

- `env_create.py` (5), `env_ensure.py` (4, incl. hint "Run `hubenv env ensure …`")
- `env_restore.py` (5, incl. `--at-boot` generated snippet lines 142–145)
- `env_pkg.py` (3, incl. "Run `hubenv env relock …`")
- `env_info.py` (2, incl. "run: hubenv env save …")
- `doctor.py` (5, several hint strings)
- `env_rm.py`, `env_save.py`, `env_ls.py`, `env_relock.py`, `env_activate.py`,
  `var.py`, `data.py`, `seeds.py`, `env_spec.py`, `_common.py`, `cli.py` (a few)

Rules:
- Only rewrite the leading `hubenv env X` → `hubenv X` where it refers to this
  command. Do **not** touch `hubenv var …` / `hubenv data …`.
- The exact `hubenv env …` reference count in `nb_wrangler/` is ~35 sites across
  15 modules (env_create, env_ensure, env_restore, env_pkg, env_info, doctor,
  env_rm, env_save, env_ls, env_relock, env_activate, var, data, seeds, env_spec,
  _common, cli, parser). A trailing `…` or prose "env" (the *resource*) stays.
- **Preserve the `--at-boot` generated shell snippet** (`env_restore.py:142-145`) —
  it emits a real command users will source; it must match the new form exactly
  (`hubenv ensure NAME 2>/dev/null || true`).
- Keep `env`/`var`/`data` in prose where they describe the *resource* (e.g.
  "list live envs") — only the command-path prefix changes.

## Phase 5 — Tests

1. **Strip the `"env",` token** from the ~127 `main(["env", …])` argv lists, which
   live in exactly 9 `tests/hubenv/` files: `test_create.py`, `test_install_relock.py`,
   `test_ensure_register.py`, `test_rm.py`, `test_restore.py`, `test_save.py`,
   `test_ls_info.py`, `test_dry_run.py`, `test_e2e.py`.
   - `main(["var", …])` and `main(["data", …])` argv lists stay unchanged.
   - `test_var.py`, `test_data.py`, `test_export_status_doctor.py`, and
     `tests/test_activation.py` contain no `main(["env", …])` list — do **not**
     change their argv (they may carry a `hubenv env …` docstring, which is a
     Phase 4 string edit, not an argv edit).
2. **Parser-structure assertions to fix:**
   - `test_install_relock.py:664/676/686` — `assert args.env_command == "…"` →
     `assert args.command == "…"` (install/uninstall/relock are now top-level).
   - `test_create.py:77-78` — `assert args.command == "env"` **removed**;
     `assert args.env_command == "create"` → `assert args.command == "create"`.
   - `test_export_status_doctor.py:103/120/128` — these assert `args.command ==
     "export"/"status"/"doctor"` and remain correct (unchanged).
3. **`test_create.py:166 test_env_no_subcommand_prints_help`** — calls
   `main(["env"])` and expects `rc == 0` (help). After flattening, `env` is no
   longer a valid command → argparse `SystemExit(2)`. **This test must be removed
   or repurposed.** Recommendation: replace with a top-level `main([])` prints-help
   test (already covered by `test_main_no_command_prints_help`).
4. **`test_create.py:57 test_main_no_command_prints_help`** — asserts `"env"`,
   `"var"`, `"data"` are substrings of the `main([])` help output. After flattening
   the bare word `env` may not appear as its own token, though it appears inside
   "environment". **Update assertions** to check the actual new top-level command
   tokens (`create`, `ls`, `var`, `data`, `export`, `status`, `doctor`) rather than
   relying on the substring `env`.
5. **Add a flat-invocation smoke test:**
   - `main(["create", "--from-empty", "--name", "demo", "--dry-run"])` returns 0
     (mirrors the old `["env","create",…]` path) — proves the promoted verb runs.
   - A `build_parser()` parse of `["ls"]`, `["save", "demo"]` sets
     `args.command == "save"` etc.
6. **Completions test:** if any test asserts the tree shape
   (`completions._HUBENV_COMMAND_TREE`), update to the flattened form. (Grep for
   `_HUBENV_COMMAND_TREE` in tests.)

## Phase 6 — Documentation

1. **Live behavior spec** — `specs/hubenv-env-create.md` and its identical
   `docs/specs/hubenv-env-create.md` copy: update the title, signature block, and
   all `hubenv env create` references to `hubenv create`. Keep the two files
   byte-identical (they currently `diff` as identical).
2. **Historical plan docs** — `docs/plan-b/**` reference `hubenv env …` heavily.
   Recommendation: **do not rewrite history**; add a single note to
   `docs/plan-b/plan-b-cli.md` (and optionally `00-index.md`) such as:
   > *Note: the `env` group has since been flattened — `hubenv env X` is now
   > `hubenv X` (see `docs/plans/hubenv-flatten-plan.md`).`
   Ask the user if they'd prefer a full rewrite of `docs/plan-b/**`.
3. `hubenv` is **not** in `README.md` (audit returned zero) and not in the `Makefile`
   or `nbw`/`nb-wrangler` shell scripts — no changes needed there.
4. `docs/plans/hubenv-conventions-plan.md` mentions `hubenv env create` as the CLI
   shape; add a forward-reference to this plan (low priority).

## Phase 7 — CHANGELOG

Add an entry to `docs/CHANGES.md` (most-recent release section):

> **CLI surface change (breaking):** the `hubenv env …` command group has been
> flattened to top-level verbs — `hubenv env create` is now `hubenv create`,
> `hubenv env save` → `hubenv save`, etc. (all 14 env verbs). `hubenv var …` and
> `hubenv data …` are unchanged. Scripts and shell snippets using `hubenv env …`
> must be updated.

## Verification

Run (per AGENTS.md, using `make` targets, plain `python` not `.venv`):

```bash
make unit-test            # hubenv unit tests incl. new flat-verb tests
make lint/flake8
make lint/black
make lint/mypy
make lint/radon           # verify complexity stays in range after dispatch merge
```

Plus manual CLI spot-checks:

```bash
python -m nb_wrangler.hubenv --help                 # lists create|save|… at top level
python -m nb_wrangler.hubenv create --help          # verb help + --quiet reachable
python -m nb_wrangler.hubenv --quiet create --from-empty --name demo --dry-run
python -m nb_wrangler.hubenv var --help             # unchanged
python -m nb_wrangler.hubenv data --help            # unchanged
python -m nb_wrangler.hubenv completions bash | head  # bash script lists flat verbs
```

## Risk Assessment

- **Behavioral risk: low.** No command logic changes; only argv shape, parser
  topology, completions tree, and string references. Verified that command modules
  read only their own flags, never `args.command`/`args.env_command`.
- **Global-flag placement** (Phase 1, step 3) is the one genuine correctness trap —
  missing it silently breaks `hubenv <verb> --quiet`. Mitigate with the
  `test_create`/flag tests.
- **`main(["env"])` test now invalid** (Phase 5, step 3) — must be removed/changed
  or it will `SystemExit(2)`.
- **Completions tree is hand-rolled** (bash/zsh/fish) — the flattened top-level set
  is easy to get subtly wrong for the *position* of env verbs. The manual
  `completions bash` check catches it.
- **Public API: no changes to `WranglerConfig`** — the unused `hubenv_command`
  field is kept (its value format updates are cosmetic), so no external import is
  broken.
- **Out of scope:** flattening `var`/`data`; renaming `ls`/`rm` across groups;
  adding a `hubenv env …` compatibility shim. If any are desired, they are follow-up
  plans.
- **Docs split brain:** `specs/hubenv-env-create.md` vs `docs/specs/hubenv-env-create.md`
  must stay identical — update both together.

## Execution Order

| Order | Phase | Priority | Description |
|-------|-------|----------|-------------|
| 1     | Phase 1 (parser) | High | Establish the flat tree; everything else keys off it |
| 2     | Phase 2 (dispatch) | High | Wire handlers to the flat verbs |
| 3     | Phase 5 (tests) | High | Update argv lists + assertions so the suite reflects the new surface |
| 4     | Phase 3 (completions) | Medium | Match shell completions to the flat tree |
| 5     | Phase 4 (in-code strings) | Medium | Docstring/help/hint rewrites |
| 6     | Phase 6 (docs) | Medium | Live spec + historical note |
| 7     | Phase 7 (changelog) | Low | Record the breaking change |
| 8     | Verify   | High | `make unit-test` + lint suite + manual CLI checks |