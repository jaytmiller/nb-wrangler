# Plan: hubenv shadow spec as a conforming nbw wrangler spec

**Status:** proposed — post-clarification revision. No implementation yet.
**Scope:** `nb_wrangler/hubenv/` + docs + tests. **No changes to `nbw`**
(`wrangler.py`, `spec_manager.py`, `spec_validator.py`, curation).

## 0. Corrected goal

- **One format.** The hubenv **shadow spec** conforms to nbw's *existing*
  wrangler-spec format — it is not a hubenv-specific format. nbw's format already
  supports an *optional* inline mamba spec as a 2nd YAML document
  (`inline_mamba_spec`; `spec_manager.py:571-584` / `:545-549`).
- **Two-doc format == sometimes.** Doc 2 is **not** always present. The common case
  is a *simple* wrangler spec (header + `extra_mamba_packages` /
  `extra_pip_packages` lists); a 2nd YAML doc only appears when an explicit mamba
  seed was supplied.
- **Relockable.** `hubenv relock` re-curates the pip list and keeps the spec valid.
- **CLI dominates.** No precedence flip: **CLI > wrangler (header) > inline mamba
  (doc 2)**. A CLI override is recorded where the value *actually* lives: the
  wrangler header (doc 1) in the simple form; the seed's own `name` and `python`
  dep in the inline form. When the seed is modified we (a) issue **descriptive log
  messages** (via the shared nbw logger) naming what changes and that it comes
  from the CLI, and (b) **clear Python-version-dependent aspects** of the seed
  (the stale `python=…` pin) so the seed never carries a contradictory python
  constraint. The mamba **recipe** (channels / other dependencies) is **not**
  rewritten by a CLI override.
- **Self-consistency (invariant).** The seed produced/modified must **never be
  self-inconsistent**. A **compiled/locked pip list** in the seed is python-version-
  specific: if the resolved python differs from the seed's original python, that lock
  is stale and must be **cleared** (with a descriptive log line) so the seed never
  carries a python-inconsistent lock. Plain (uncompiled) package names are
  python-independent and preserved.
- **Hash:** always write a **valid** `spec_sha256` in doc 1 (`system`). No lenient
  "skip on missing hash." An uncurated shadow spec with no valid hash is legacy.
- **Reproducible via nbw:** the shadow spec is a valid wrangler spec, so the user's
  path is the standard `nbw --curate` (→ populates `out`) then `nbw --reinstall`.
  **`nbw --reinstall` stays a hard error when `out` is empty** (locked-envs only);
  we do **not** relax or special-case it. **No nbw changes.**

## 1. The two valid forms (from `spec_validator.py`)

nbw enforces **exactly one** environment-definition method; they are mutually
exclusive. The shadow spec takes the form matching its source:

| Form | When | Doc 1 (header) | Doc 2 |
|---|---|---|---|
| **Simple** | source has no inline mamba seed (the common case: basic Python env + package lists) | `kernel_name` **required**, `python_version` **required**, `extra_mamba_packages`, `extra_pip_packages`, `environment_vars` | **absent** |
| **Inline** | source carries an explicit mamba seed (2nd YAML doc) | header must **NOT** contain `kernel_name` / `python_version`; name & python live in doc 2; `extra_pip_packages`/`extra_mamba_packages` may still be present | present, must have `name`; **mamba-clean** (no `environment_vars`) |

Both are valid wrangler specs, so both work under nbw's `--curate`/`--reinstall`.
Simple is the default and the one where "CLI → header" applies directly.

## 2. Precedence (CLI > wrangler > inline mamba)

**Name:**
- Simple: CLI `--name` > header `kernel_name`.
- Inline: CLI `--name` > doc 2 `name` (header has no name slot — nbw forbids it).

**Python:**
- Simple: CLI `--python` > header `python_version`.
- Inline: CLI `--python` > doc 2 `python=…` dep.

**Packages:** header `extra_mamba_packages` / `extra_pip_packages` are the
authoritative additions — they layer on top of (and override same-name) doc 2 deps
in the inline form.

**Recording CLI overrides:**
- **Simple form:** CLI value replaces the corresponding header field
  (`kernel_name`, `python_version`). No doc 2.
- **Inline form:** the name/python physically live in doc 2, so a CLI override is
  recorded there: set `doc 2["name"]` (if CLI `--name`) and replace the
  `python=…` dep (if CLI `--python`), with descriptive logging and the stale python
  pin cleared; doc 2's **recipe** (channels / other dependencies) is never
  rewritten by a CLI override.

`--from-mamba-spec` (seed from a raw mamba file) is **unchanged** — CLI `--name`
still overrides there.

## 3. Changes (hubenv only)

### 3.1 `nb_wrangler/hubenv/env_spec.py`
- `load_hubenv_spec` (161-175): read with `yaml.load_all`; doc 1 → `wrangler_to_mamba`
  (unchanged); detect doc 2 presence so the form is known for relock/save.
- `save_hubenv_spec` (178-188) — restructure via small helpers (≤ ~15 lines each):
  - `_write_two_docs(path, doc1, doc2_or_None)`: if doc2 is None → single doc 1;
    else doc 1 + `"\n---\n"` + doc 2 (match `SpecManager.to_string()`
    `spec_manager.py:545-549` byte-for-byte, incl. trailing-newline convention).
  - `_compute_spec_sha256(doc1, doc2_or_None)`: blank the field, serialize (doc 1
    + `---` + doc 2), `sha256_str` (shared `nb_wrangler.utils.sha256_str`, same
    utility `SpecManager.add_sha256` uses), restore.
  - `doc1 = mamba_to_wrangler(name, view)` (unchanged).
  - `doc2` (inline form only) = the pristine seed (channels/dependencies, no env vars);
    its name/python reflect the resolved values per §2.
  - `doc1["system"]["date_updated"] = now`; valid `spec_sha256`.
  - Write single-doc (simple) or two-doc (inline).

### 3.2 `nb_wrangler/hubenv/seeds.py` — `seed_from_wrangler_spec` (131-166)
- Read with `yaml.load_all`; detect form (doc 2 present?).
- Resolve name/python per §2 (CLI > header > doc 2; python errors if absent from
  all sources in the simple form).
- Seed:
  - **Simple:** derive from header (`_base_spec` + `extra_mamba_packages` +
    `extra_pip_packages` + `_ensure_target_packages`); no doc 2.
  - **Inline:** seed = doc 2 base with header extras merged (header wins on same
    name). If CLI `--name`/`--python` were given, override `seed["name"]` and the
    `python=…` dep to the resolved values via a small helper (≤ ~15 lines) that
    (1) logs descriptively (e.g. "Overriding seed name from 'foo' to 'bar' (CLI
    --name)") and (2) clears the stale python pin (any `python`/`python3.x`
    constraint) before inserting the new one; recipe (channels / other deps) stays
    intact.
- **Self-consistency — clear stale pip lock:** if the resolved python differs from
  the seed's original `python` dep (or the seed lacks a `python` dep) and the seed
  carries a compiled/locked `pip:` list, remove those lock entries and log
  descriptively (e.g. "Cleared stale pip lock compiled for python 3.11; seed now
  targets python 3.12"). Plain (uncompiled) package names are preserved. No-op when
  the seed carries no lock (the common `hubenv create` path); fires when building the
  inline seed from a pre-existing locked mamba export.

### 3.3 `nb_wrangler/hubenv/env_relock.py` (47-64)
- No extra code: `apply_relock` re-pins the view's pip → `save_hubenv_spec` rewrites
  doc 1 (`extra_pip_packages`) and — inline form — doc 2's pip deps, and refreshes
  `date_updated` + a valid `spec_sha256`. Keeps the existing
  "No pip packages to relock" early exit.

### 3.4 `nb_wrangler/hubenv/export.py` — `format_export` (30-42)
- `--to-wrangler-spec` emits the same form as the shelf (simple or inline), reusing
  the `_write_two_docs` serialization, so exports are nbw-conforming.

### 3.5 No `nbw` changes
- `wrangler.py` `_run_reinstall_spec_workflow` (388-408) **stays** a hard error when
  `out` is empty; `validate_sha256` (788-802) stays strict (no skip-on-missing).
  Document the nbw path: `nbw <spec> --curate` → `nbw <spec> --reinstall`.

## 4. Decision — resolved: override the seed (option 1)

In the **inline form** the header *cannot* hold `kernel_name`/`python_version`
(nbw validator), so a CLI name/python override is recorded **in doc 2** (not the
header):

- Set `doc 2["name"]` = resolved name.
- Replace the `python=…` dependency in `doc 2["dependencies"]` with the resolved
  python version — i.e., **clear the stale pin** and insert the new one, so the
  seed never carries a contradictory python constraint.
- **Descriptive logging** (shared nbw logger) when the seed is modified, e.g.
  "Overriding seed name from 'foo' to 'bar' (CLI --name)" and
  "Overriding seed python from '3.11' to '3.12' (CLI --python); cleared stale
  python pin."
- **Recipe untouched:** channels and the other (non-python) dependencies are
  left byte-identical.

This makes "CLI dominates" hold and persist in a *valid* wrangler spec while the
seed's environment recipe remains intact.

## 5. Round-trip

```
hubenv create --from-wrangler-spec FILE
  -> detect form (doc 2?); resolve name/python (CLI > header > doc 2)
  -> seed = header-derived (simple) | doc 2 + header extras (inline)
  -> install_environment(args.name, seed)
  -> save_hubenv_spec: doc 1 (valid header) [ + doc 2, recipe intact ] ;
       date_updated=now ; valid spec_sha256 ; single-doc or two-doc

hubenv relock NAME
  -> load view -> compile pip -> mutate view -> save_hubenv_spec
       -> doc 1 extra_pip re-pinned; (inline) doc 2 pip re-pinned;
          date_updated + spec_sha256 refreshed

# nbw side (user's job; nbw unchanged):
nbw <shelves>/<name>/nbw-wrangler-spec.yaml --curate      # populates out (locked)
nbw <shelves>/<name>/nbw-wrangler-spec.yaml --reinstall   # reproduces the locked env
```

## 6. Test plan (focused, hubenv-side)

- **Form detection / writing:** `save_hubenv_spec` emits a single doc when no seed
  (simple) and two docs when an inline seed is present; doc 1 validates under
  `SpecManager.load_and_validate` for **both** forms; stored `spec_sha256` validates
  (hash round-trip via `to_string()`); doc 2 is mamba-clean (no `environment_vars`).
- **Precedence (per form):** CLI wins; without CLI, header (simple) / doc 2
  (inline) wins; python errors when absent from all sources (simple form).
- **CLI → header recorded:** after a CLI override, doc 1 header fields reflect it
  (simple); recipe (channels/deps) unchanged.
- **Inline override:** CLI `--name`/`--python` rewrite doc 2's `name`/`python` dep;
  the stale python pin is cleared (no leftover old `python=…`); channels/other
  deps byte-identical; descriptive log lines are emitted (capture/assert).
- **Self-consistency / stale pip lock:** inline seed built from a mamba spec
  carrying a compiled/locked `pip:` list, then an overriding `--python`, clears the
  lock and emits the log; plain (uncompiled) package names are preserved; when the
  seed carries no lock the operation is a no-op (nothing changed, no log).
- **Relock:** doc 1 `extra_pip_packages` re-pinned; (inline) doc 2 pip re-pinned;
  hash stays valid; dry-run writes nothing.
- **No nbw tests added** (nbw unchanged).

## 7. Documentation updates
- **`docs/spec-format.md`**: document the two mutually-exclusive forms (simple vs
  inline), the inline 2nd YAML doc, and the "header must not hold
  `kernel_name`/`python_version` when an inline spec is present" rule.
- **`docs/specs/hubenv.md`**: §3.2 layout (two forms), §4.8 / §6.1 (shadow spec is
  a conforming nbw spec, not hubenv-specific; relock refreshes both docs + hash),
  §7 rough-edge list.
- **`docs/specs/hubenv-env-create.md`**: §4.4 `seed_from_wrangler_spec` (two forms,
  CLI > header > inline; python errors), §5 (writes single/two doc + valid metadata).
- **`docs/hubenv-howto.md`**: add the nbw reproduction recipe (`--curate` →
  `--reinstall`) and note `--reinstall` needs `out`.

## 8. Compliance (AGENTS.md)
- **No nbw changes** (smallest hubenv-only change).
- **No duplicated logic:** hash reuses the shared `nb_wrangler.utils.sha256_str`.
- **Function size:** extract `_write_two_docs` / `_compute_spec_sha256` so
  `save_hubenv_spec` / `seed_from_wrangler_spec` stay ≤ ~20 lines.
- **Focused tests** for the behavior changes.
- **No commit.**

## 9. Backward compatibility / risks
- **Old single-doc shelf specs:** `load_all` on a one-doc file → one-element list →
  `load_hubenv_spec` behaves as today. They keep working until rewritten.
- **`nbw --reinstall` on an uncurated shadow spec still errors** (by design, `out`
  missing) — unchanged.
- **Hash byte-exactness:** if hubenv's two-doc serialization diverges from
  `SpecManager.to_string()` (trailing newline), the stored hash won't validate.
  Verify the separator convention at implementation.
- **mamba tolerance of doc 2:** doc 2 is mamba-clean, matching what was already
  written to the temp file at create time — no new `mamba create` risk.
- **`--ephemeral`** skips the shelf write → no new doc 2 for throwaway envs (unchanged).
