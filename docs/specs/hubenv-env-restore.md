# `hubenv restore` — Behavior Specification

> Reverse-engineered spec. Derived from the implementation in
> `nb_wrangler/hubenv/env_restore.py`, `nb_wrangler/hubenv/env_ensure.py`
> (the `EnsureArgs` delegation), `nb_wrangler/pantry.py`, and
> `nb_wrangler/environment.py`.
>
> Verified against `tests/hubenv/test_restore.py`, `test_ensure_register.py`
> (delegated path), and `test_e2e.py` (Phase 3).

---

## 1. Purpose

`hubenv restore` unpacks a saved can into the live envs root and (re)registers
the Jupyter kernel, making a previously archived environment usable again.
It is the core of portability: the same `save`d can can be unpacked on a fresh
machine (after a fresh mamba install of the right root) and re-registered as
a kernel.

Idempotency is driven by two hashes (see
[`hubenv-common.md`](hubenv-common.md) §9): the shelf's save hash
(`archives/last-save.sha256`) and a restore hash kept under
`$NBW_ROOT/.hubenv-restore/<name>.sha256`. When they match, restore is a no-op
that prints eval-able exports. `--force` bypasses the check.

---

## 2. Command synopsis

```
hubenv restore NAME [--pantry PATH] [--force] [--at-boot]
```

`hubenv ensure` also invokes this same handler (with `force=False`,
`at_boot=False`, and a threaded-through `display_name`) — see
[`hubenv-env-ensure.md`](hubenv-env-ensure.md).

---

## 3. Arguments

| Argument | Required / Default | Description |
|---|---|---|
| `NAME` | required, positional | Name of the environment to restore. |
| `--pantry` | optional, `None` | *Source* pantry directory. When set, that single pantry is checked for the shelf (no fallback to the chain). When omitted, all pantries in `NBW_PANTRY` are searched; a multi-match is **refused** (see §4.2). |
| `--force` | optional, `False` | Skip the idempotent-hash check and re-unpack (re-extract the can over the live env dir). |
| `--at-boot` | optional, `False` | Write a guarded startup snippet (see §4.5) in addition to restoring. |
| global flags | — | see [`hubenv-common.md`](hubenv-common.md) §3. |

(Note: unlike `ensure`, the `restore` parser has no `--display-name`; the
display name is taken from the shelf spec.)

---

## 4. Execution paths

### 4.1 Shelf lookup (`find_restore_shelf`)

1. `--pantry PATH` set → check `PATH/shelves/NAME`:
   - exists → match found;
   - absent → stderr `"No shelf 'NAME' found in pantry <PATH>."` → **return 1**.
2. Chain search → `find_shelves(NAME)` (all matches across pantries):
   - more than one → stderr `"NAME' found in multiple pantries:"` + one INFO
     line per matching shelf path + `"Use --pantry to select a specific one."`
     → **return 1** (no guessing; shadowing contract).
   - zero → caller logs `"No shelf 'NAME' found in any pantry."` → **return 1**.
   - one → proceed with `(pantry_path, shelf_path)`.

### 4.2 Can existence check (the "spec-only" guard)

`can_path = shelf.env_archive_path(NAME, ".tar")`. If the can is **missing**:

- stderr: `"Environment 'NAME' has a shelf spec at <shelf path> but no archive (can) at <can path>."`
- INFO: `"Run: hubenv save NAME   to create the restoreable can."`
- → **return 1**.

This is the canonical, distinctly-named message for the `spec-only` state
(§12 of [`hubenv-common.md`](hubenv-common.md)).

### 4.3 Idempotent skip (unless `--force`)

- `save_hash` ← `<shelf>/archives/last-save.sha256` (`.strip()`);
  `restore_hash` ← `$NBW_ROOT/.hubenv-restore/<name>.sha256` (`.strip()`).
- Both present **and equal** → stdout
  `"Environment 'NAME' already restored (idempotent skip). Use --force to re-unpack."`
  + `print_exports(NAME)` → **return 0**. No unpack, no kernel registration,
  no further writes.

### 4.4 Unpack

`shelf.unpack_environment(NAME, NAME, ".tar")` →
`tar -amxf <can>` into `NBW_MM/envs/<NAME>` (timeout `ARCHIVE_TIMEOUT`,
`MAMBA_ROOT_PREFIX` pinned):

- success → INFO `"Unpacked <can> into <live env dir>"`;
- failure → ERROR `"Failed to unpack <can> into <live env dir>:"` + output → **return 1**.

After a successful unpack:

- `save_hash = read_save_hash(shelf) or ""`;
- write it to `$NBW_ROOT/.hubenv-restore/<NAME>.sha256`
  (`record_restore_hash`; parent dir created).
- Determine `display_name` = `spec_display_name(shelf.spec_path)`
  (`image_spec_header.display_name` of the shelf spec) or `NAME` if unset.
- `em.register_environment(NAME, display_name, {})` — runs
  `mamba run -n <NAME> python -m ipykernel install --user --name '<NAME>'
  --display-name '<display_name>'` in the env.
  (A failed registration logs ERROR but is **not** a failure exit — the
  unpacked env stands.)
- stdout: `print_exports(NAME)` →
  ```
  export NBW_ACTIVE_ENV=NAME
  export NBW_ENV_ROOT=<live envs root>/NAME
  ```
- **return 0**.

### 4.5 `--at-boot` (after a successful restore)

`write_at_boot_snippet(NAME)` creates (overwriting)
`~/.hubenv/env-<NAME>.sh`:

```sh
# hubenv ensure <NAME> - idempotent restore at boot
if [ -z "${NBW_ACTIVE_ENV+set}" ]; then
    export NBW_ACTIVE_ENV="<NAME>"
    hubenv ensure <NAME> 2>/dev/null || true
fi
```

and prints to stdout:

```
At-boot snippet written to <snippet path>
To use it at shell startup, add this line to your rc file:
    source <snippet path>
```

It **never** edits the shell rc file (the user decides where to source from)
— RE-04 resolved. The snippet is removed by `hubenv rm` via
`remove_at_boot_snippet` (INFO `"Removed at-boot snippet <path> (if present)."`
on stderr).

---

## 5. Exit codes

| Condition | Exit code |
|---|---|
| Unpack + register + (snippet) success | `0` |
| Idempotent skip (hashes match, no `--force`) | `0` |
| No shelf (any pantry, or forced `--pantry` miss) | `1` |
| No can (spec-only) | `1` |
| Multiple matching shelves (multi-pantry, no `--pantry`) | `1` |
| Unpack failure | `1` |
| (Kernel registration failure) | `0` — unpacked env stands; error on stderr |
| Argparse usage error / interrupt | `2` / `130` |

---

## 6. Side-effect summary by flag combination

| | default | `--force` | `--at-boot` (with restore) |
|---|---|---|---|
| live env dir (unpack) | written unless skip | written (overwritten) | written unless skip |
| restore hash (`$NBW_ROOT/.hubenv-restore/<name>.sha256`) | written (unless skip) | written | written (unless skip) |
| kernelspec | (re)registered | (re)registered | (re)registered |
| `~/.hubenv/env-<name>.sh` | untouched | untouched | written (guarded, overwritable) |
| can / save hash | untouched | untouched | untouched |

---

## 7. Edge cases

- **Multi-match refuse**: with shelves in two pantries and no `--pantry`,
  restore refuses (exit 1) rather than picking the first — the user must pass
  `--pantry`. `ls`/`info` instead collapse and warn.
- **spec-only state**: a shelf with a spec but no can → clear `"Run: hubenv
  save NAME"` hint, exit 1.
- **Hash mismatch** (e.g. re-saved after the first restore) → full re-unpack
  (treated as a new restore); matching → skip.
- **`--force`** re-unpacks even when hashes match — it re-extracts the same
  can and re-registers the kernel.
- **Kernel registration failure** after a successful unpack: the command still
  returns 0 and prints exports; the failed `ipykernel install` is logged.
- **`--at-boot`** does not edit `~/.bashrc`/`~/.zshrc`/`~/.config/fish`; the
  user sources the printed instruction. (RE-04: bash-only auto-edit removed.)
- A failed unpack leaves the live env dir as it was (tar failure is
  best-effort; partial extraction is the tar's problem, not hubenv's).

---

## 8. Pantry interaction

- **Read-only**: restore never writes to any pantry. It reads the can from
  exactly one shelf.
- **`--pantry`** = *source* selection (validated, no fallback).
- **Chain** = full search; multi-match is refused (per §4.2).
- **Writes** go to the *live store*: `NBW_MM/envs/<name>` (unpack target) and
  `$NBW_ROOT/.hubenv-restore/<name>.sha256` (restore hash), plus
  `~/.local/share/jupyter/kernels/<name>/` (kernelspec) and optionally
  `~/.hubenv/env-<name>.sh`.

---

## 9. Output (stdout) examples

### 9.1 Full restore (fresh machine)

```
export NBW_ACTIVE_ENV=demo
export NBW_ENV_ROOT=/home/u/.nbw-live/mm/envs/demo
```
(stderr: INFO `"Unpacked <can> into /home/u/.nbw-live/mm/envs/demo"`, INFO
`"Registered environment demo as a jupyter kernel making it visible to
JupyterLab as 'demo'."`.)

### 9.2 Idempotent skip

```
Environment 'demo' already restored (idempotent skip). Use --force to re-unpack.
export NBW_ACTIVE_ENV=demo
export NBW_ENV_ROOT=/home/u/.nbw-live/mm/envs/demo
```

### 9.3 `--at-boot` (appended to the success output)

```
At-boot snippet written to /home/u/.hubenv/env-demo.sh
To use it at shell startup, add this line to your rc file:
    source /home/u/.hubenv/env-demo.sh
```

### 9.4 Failures (stderr)

```
No shelf 'demo' found in any pantry.
No shelf 'demo' found in pantry /opt/alt-pantry.
'demo' has a shelf spec at /home/u/.nbw-pantry/shelves/demo but no archive (can) at /home/u/.nbw-pantry/shelves/demo/archives/env-demo.tar.
Run: hubenv save demo   to create the restoreable can.
'demo' found in multiple pantries:
  /home/u/.nbw-pantry/shelves/demo
  /home/u/alt-pantry/shelves/demo
Use --pantry to select a specific one.
```

---

## 10. What is NOT done (out of scope for the current implementation)

- No `--display-name` (kernel display name comes from the shelf spec's
  `image_spec_header.display_name`, else env name).
- No data-archive handling — `hubenv data download/unpack` is separate and
  must run after restore (see [`hubenv-data.md`](hubenv-data.md)).
- No mamba re-build of the env (restore *unpacks*, it does not re-create via
  mamba).
- No nbw curation or image build.

---

## 11. See also

- [`hubenv.md`](hubenv.md) — top-level spec (§2.1 state matrix, §4.7
  idempotency, §5.1 restore stub).
- [`hubenv-common.md`](hubenv-common.md) — §5 layout, §6 `find_shelves`/
  `restore_hash_path`, §9 idempotency tokens, §12 state model.
- [`hubenv-env-save.md`](hubenv-env-save.md) — producer of the save hash;
  [`hubenv-env-ensure.md`](hubenv-env-ensure.md) — delegates to this handler;
  [`hubenv-env-create.md`](hubenv-env-create.md) — builds the env that will be
  saved; [`hubenv-env-rm.md`](hubenv-env-rm.md) — removes the can + restore
  hash + at-boot snippet.
