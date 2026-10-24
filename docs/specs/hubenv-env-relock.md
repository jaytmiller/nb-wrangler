# `hubenv relock` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/env_relock.py`, `nb_wrangler/hubenv/env_spec.py`,
> `nb_wrangler/compiler.py`, `nb_wrangler/environment.py`, and
> `nb_wrangler/pantry.py`.
>
> Verified against `tests/hubenv/test_install_relock.py`.

---

## 1. Purpose

`hubenv relock NAME` **re-cures (version-pins) the pip section** of the env's
implicit shelf spec and persists it, so the spec's `{"pip": […]}` list matches
the versions actually resolvable by `RequirementsCompiler`.

It is the second half of the install/uninstall workflow:
`hubenv install NAME pkg` records *which* packages (base names), then
`hubenv relock NAME` records *which versions* are currently valid. Conda
dependencies are **not** touched here — they are maintained by
`install`/`uninstall --using mamba`.

The command is also the canonical **acceptance test** for the RE-14 shadow
spec: a valid shelf spec must round-trip through relock (compile → rewrite)
without losing its wrangler-spec form or `spec_sha256` validity.

---

## 2. Command synopsis

```
hubenv relock NAME [--dry-run]
```

---

## 3. Arguments

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Name of the **live** mamba environment. |
| `--dry-run` | optional, `False` | Print the resolved package list; write nothing. |
| global flags | — | `-q/--quiet`, `--verbose`, `--debug`, `--color`, `--log-times`,
  `--reset-log` (see [`hubenv-common.md`](hubenv-common.md) §3). |

---

## 4. Execution paths

1. **Live-env precheck** — `EnvironmentManager.environment_exists(NAME)`.
   Missing → `Live environment '<name>' not found.` (stderr) → exit **1**.
   (Same gate as install/uninstall.)
2. **Load the implicit spec** — `load_hubenv_spec(store, NAME)`. If no shelf
   spec exists, the `seed_from_empty(name, None)` fallback (`{"dependencies":
   ["pip"]}`) is used, so the *pip list* is empty — see step 3.
3. **Extract the pip section** — `get_or_create_pip_section(spec["dependencies"])`
   returns the `{"pip": […]}` sub-list (creating an empty one if absent).
   - Empty list → print
     `No pip packages to relock in '<name>'.`
     → exit **0** (no-op; nothing written).
4. **Compile** — `RequirementsCompiler(spec_manager=None,
   repo_manager=None).compile_packages_for_env(packages, em.nbw_temp_dir)`
   resolves each base name to a pinned requirement string (e.g.
   `numpy` → `numpy==1.26.4`). Compilation failure (network / unsolvable) →
   exit **1** — the failure is logged by the compiler; the spec is **untouched**.
5. **`--dry-run`** →
   ```
   Dry-run: would re-curate <N> packages for '<name>':
     <pkg name="=pin">
     …
   ```
   → exit **0**.
6. **Apply** — replace the pip section in place (`pip_section[:] = compiled`)
   and `save_hubenv_spec` — unconditional overwrite, source form preserved
   (simple 1-doc vs. inline 2-doc), fresh `spec_sha256` stamped (RE-14).
   Print `Relocked <N> packages for '<name>'.` → exit **0**.

---

## 5. Exit codes

| Condition | Code |
|---|---|
| `--dry-run` (after a successful compile) | 0 |
| Empty pip section (no packages to relock) | 0 |
| Live env not found | 1 |
| Compilation failed (unsolvable / network) | 1 (spec untouched) |
| Apply succeeded | 0 |

---

## 6. Side-effect summary by flag combination

| Combination | Shelf spec | Live env |
|---|---|---|
| `relock NAME` (success) | rewritten (pip section replaced with resolved pins, `date_updated` stamped) | untouched |
| `relock NAME --dry-run` (compile OK) | nothing | untouched |
| Empty pip section | nothing | untouched |
| Live env missing | nothing | n/a (error before load) |
| Compile failure | nothing | untouched |

---

## 7. Edge cases

- **Only pip is relocked** — conda-string dependencies survive a relock
  verbatim (the spec section is swapped for the pip sub-list only). A spec
  whose `dependencies` contain no pip packages is a documented no-op.
- **Compile failure is silent on *which* package** — the error message names
  the environment, not necessarily the offending package (top-spec rough
  edge).
- **Idempotent on stable envs** — re-running against an unchanged env
  re-writes the same pins; `save_hubenv_spec` is unconditional, so
  `date_updated` is re-stamped every run even when nothing changed.
- **RE-14 round-trip** — relock is the acceptance path that proves the
  shadow spec "saves/relocks without drift": the file must still pass
  `SpecManager.load_and_validate` + `validate_sha256` after every rewrite
  (`docs/spec-format.md` two-form rule: inline seed stays two-doc, otherwise
  single-doc).
- **No `--using` argument** — relock is pip-only by construction; there is
  no conda re-cure flag.

---

## 8. Pantry interaction

- **No `--pantry`.** The default `NBW_PANTRY` chain is used to locate the
  shelf spec (read + write). This command is live-env bound (step 1 requires
  a live env) and the RE-12 resolution leaves it off the `--pantry` list.
- Read: shelf spec via `load_hubenv_spec`.
- Write: shelf spec via `save_hubenv_spec` (unconditional overwrite,
  [`hubenv-common.md`](hubenv-common.md) §8).

---

## 9. Output (stdout) examples

### 9.1 Success

```
$ hubenv relock demo
Relocked 2 packages for 'demo'.
```

### 9.2 `--dry-run`

```
$ hubenv relock demo --dry-run
Dry-run: would re-curate 2 packages for 'demo':
  numpy==1.26.4
  pandas==2.2.0
```

### 9.3 Empty pip section

```
$ hubenv relock demo
No pip packages to relock in 'demo'.
```

### 9.4 Live env missing

(stderr; stdout empty:)

```
ERROR: Live environment 'ghost' not found.
```

---

## 10. What is NOT done (out of scope for the current implementation)

- No **conda re-cure** — only the pip section is version-pinned.
- No **relock suggestion** from install/uninstall is *automatic* — the user
  must run it (or accept a stale lock).
- No **partial failure** handling: either all packages compile or the command
  fails whole; there is no "lock what you can".
- No **`--pantry`** scoping (RE-12 partial).
- No **confirmation / dry-run default** — `--dry-run` is opt-in; the write is
  unconditional once the compile succeeds.

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§4.3 stdout contract, §4.4 exit
  codes, §5.2 `relock` stub, §7 RE-14 note).
- [`hubenv-common.md`](hubenv-common.md) — shared contracts (§3 global flags,
  §8 implicit spec model — `save_hubenv_spec` form-preservation and
  `spec_sha256`, §10 output discipline, §11 exit codes).
- [`hubenv-env-install-uninstall.md`](hubenv-env-install-uninstall.md) — the
  commands that record the package list this command pins.
