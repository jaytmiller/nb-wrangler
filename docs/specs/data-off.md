# Per-repository `data: on|off` — Behavior Specification

> Spec for the optional `data` field on each `repositories:` entry, added in
> `nbw` v0.11.0. Derived from the implementation in
> `nb_wrangler/constants.py` (`data_flag_enabled`),
> `nb_wrangler/spec_manager.py` (`repo_data_enabled` and friends),
> `nb_wrangler/spec_validator.py` (value check), and
> `nb_wrangler/data_wrangler.py` (guards + empty declarations).
>
> Verified against `tests/test_data_flag_spec.py` and
> `tests/test_data_off_pipeline.py`.

---

## 1. Purpose

Allow curators to **opt individual repositories out of data handling** while
keeping their notebooks and package requirements fully curated. A repository
with `data: off`:

- contributes **no** `refdata_dependencies.yaml` to the data definition built
  by `DataWrangler.collect()` (treated as an empty data declaration);
- is **skipped** by every data step — `download`, `validate`, `update`,
  `unpack`, `pack`, `list`, `delete`, `symlink`, `clean-symlinks` — on both
  the workflow paths (`--data-curate` / `--data-reinstall`) and the isolated
  flag paths (`--data-download`, `--data-unpack`, …) that `hubenv data …`
  delegates to;
- is logged as an `INFO` line naming the repo and the reason, and the skipped
  step **returns success** (never aborts the workflow).

## 2. Spec format

Additive, optional key under each repository entry (`url` remains the only
required key):

```yaml
repositories:
  my_repo:
    url: https://github.com/organization/my_repo
    ref: main
    data: off            # exclude this repo from data curation / reinstallation
```

| Accepted (case-insensitive) | Meaning |
|---|---|
| `on`, `yes`, `true` | data enabled (same as omitting the key) |
| `off`, `no`, `false` | data **disabled** for this repository |

- Default when omitted: **on** — behavior identical to pre-v0.11.0.
- Anything else is a **validation error** at spec validate time
  (`Invalid 'data' value '…' in repository '…'; expected an on/off form …`).
- Dev overrides compose through the existing per-repo merge, so
  `dev_overrides.repositories.<name>.data: off` is a dev-only opt-out (the
  production spec is unaffected when running `--prod`).

## 3. Semantics

### 3.1 All-on (default)

No `data` keys (or all `on`) — **byte-for-byte the pre-v0.11.0 behavior**:
every repository's `refdata_dependencies.yaml` participates in curation and
reinstallation.

### 3.2 Mixed (some `off`)

Only enabled repositories' data is curated/installed. `out.data.spec_inputs`
contains an entry per enabled repository (and the image-wide `nbw-spec`
entry, see §4); disabled repositories are absent, and their saved entries —
from a curation that predates the opt-out — are filtered out at read time, so
`download`/`unpack`/etc. only act on the enabled repositories.

### 3.3 All off (pipeline no-op)

When **every** declared repository is `data: off` **and** there is no
top-level `refdata_dependencies:` section:

- `--data-curate` and `--data-reinstall` run to green end-to-end;
- `collect()` defines **empty, well-formed** declarations:
  ```yaml
  out:
    data:
      spec_inputs: {}
      spec_exports: {}
      pantry_exports: {}
  ```
  with `nbw-spec-exports.sh` / `nbw-pantry-exports.sh` written but containing
  no `export` lines, and the environment registered with an empty env-var set;
- every data step is a logged success no-op (`<step> skipped: no enabled data
  declarations (data: off).`) **without** any download/unpack/network attempt.

## 4. Edge: image-wide `refdata_dependencies`

The top-level `refdata_dependencies:` section is **image-wide, not tied to any
repository**, so `data: off` on all repositories does **not** suppress it:

- To make a spec fully data-off, set `data: off` on every data-bearing
  repository **and** omit/empty the top-level `refdata_dependencies:`.
- If all repositories are `data: off` but a top-level
  `refdata_dependencies:` with data is declared, that image-wide data is
  still curated/installed as before (the steps run, they just have no
  per-repo entries).

There is deliberately **no** global data-off toggle; `data` stays strictly
per-repository.

## 5. Consequences

- The `data` key is part of the hashed spec: adding/toggling it changes
  `spec_sha256`. Specs that adopt the field must be re-stamped
  (`nbw --spec-update` / `hubenv relock`) — same as any content change.
- `WRANGLER_SPEC_VERSION` stays at **2.3**: the field is purely additive for
  the v0.11.0 validator, and a spec *without* the key behaves exactly as
  before on v0.11.0 (full backward compatibility for existing specs).
  The reverse direction is not compatible — a pre-v0.11.0 validator rejects
  the key as an unknown repository keyword — so adopt the field only on
  v0.11.0+ toolchains.

## 6. hubenv impact

**Zero behavioral change by default** (the key is additive and absent in
existing specs ⇒ `on` ⇒ current behavior). `hubenv data download/unpack/
pack/clean` remain thin wrappers over the same flag-driven nbw path and
inherit the no-op automatically: a shelf spec that is fully data-off makes
`hubenv data <verb> NAME` exit **0** with a logged skip and **no** network or
archive activity — the same contract as `nbw --data-*` flags.

## 7. Tests

- `tests/test_data_flag_spec.py` — normalization helper, validator value
  check (valid/invalid/empty), accessor behavior (all-on / all-off / mixed /
  single-repo), dev-override on/off in `--dev` vs `--prod`.
- `tests/test_data_off_pipeline.py` — functional, faked repo trees with real
  `refdata_dependencies.yaml` files: empty declarations + no
  `export` lines (all off), every step no-ops without pantry/network touch,
  mixed specs (only enabled repos curated/downloaded), read-time filtering
  after curation, image-wide `refdata_dependencies` still curated,
  regression (no `data` keys ⇒ both repos curated), `spec_sha256` stability
  (hash changes with the flag), and the hubenv thin-wrapper flag mapping.

## 8. See also

- [`../spec-format.md`](../spec-format.md) — `repositories`,
  `dev_overrides`, `refdata_dependencies` sections.
- [`hubenv-data.md`](hubenv-data.md) — `hubenv data` behavior spec (inherits
  the no-op via delegation).
- `docs/plans/data-off-field.md` — the design / implementation plan.
