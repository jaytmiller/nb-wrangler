# Persistent Platform Environments CLI (`hubenv`)

## Scope

This describes the proposed CLI for users and admins managing PPEs (Persistent
Platform Environments). It is a **thin, user-friendly wrapper over nb-wrangler**
that maintains an implicit wrangler spec in the background while exposing an
interface in terms people already know.

### Features

- Automatic kernel registration / cleanup (including dead-kernel scanning).
- Automatic shell environment handling for notebooks + terminals.
- `NBW_PANTRY` for User, Team, and Mission/image level PPE pantries
  (colon-separated, PATH-like lookup).
- `NBW_ROOT` for live environments, wrangler, and caches (container storage).
- Optionally: notebook handling — consolidate requirements, clone/update repos,
  automatic version pinning, headless notebook testing.
- Optionally: data management — consolidate data assets, easy downloads,
  automatic version pinning.

## Design principles

1. **Reuse, never reimplement.** `hubenv` delegates to the existing modules in
   `nb_wrangler/` (`pantry.py`, `environment.py`, `registry.py`, `cli.py`).
2. **Hide the implicit wrangler spec, don't leak it.** Costs that trigger
   re-curation/re-locking must be explicit, never a side effect of `install`.
3. **Be safe by default at platform scale.** Multi-pantry lookups must make
   shadowing visible; destructive ops must be confirmation-safe.
4. **Mirror familiar tools' vocabulary** (`mamba`/`conda`/`uv`) so the learning
   curve is shallow, but do not duplicate what `mamba activate` already does.
5. **Make the common case obvious via subcommands** (`hubenv env ...`, `hubenv var ...`,
   `hubenv data ...`) so `--help` is navigable.

## Storage model

### Live storage — `NBW_ROOT`

`NBW_ROOT` defines the location of live wrangler environments, caches, and
wrangler itself. This defaults to container storage on the platform. Keep live
environments on fast, typically ephemeral storage.

### Archive storage — `NBW_PANTRY`

`NBW_PANTRY` defines a colon-separated list of wrangler `pantry` directories
used to archive persistent environments (analogous to `PATH`). Each pantry stores
multiple environments; each environment gets its own `shelf` (spec + inputs +
code + data) and a `can` for each code archive. These are nominally located on
persistent EFS.

Lookups mirror OS `PATH` semantics: the first matching `shelf` wins, and new
shelves are created in the first (primary) writable pantry.

```sh
# Personal, team, and system level pantries
export NBW_PANTRY=$HOME/.nbw-pantry:/teams/team-1/nbw-pantry:/teams/admin/nbw-pantry

# Shared-image-data default
export NBW_PANTRY=/teams/admin/nbw-pantry
```

Unpacker data and data archives also live in environment archive shelves.

### Read-only detection

`hubenv` classifies each pantry as read/write or read-only at startup. Commands
that write (e.g. `hubenv env save`, `hubenv env rm`) refuse to write into read-only
pantries with a clear message and suggest `--pantry <writable>`. `hubenv env ls`
reports the r/w status of each pantry.

## Command structure

`hubenv` uses subcommand groups (in the style of `conda`/`mamba`/`uv`):

```
hubenv env  (create|install|uninstall|ls|info|restore|save|rm|relock|ensure|register|unregister)
hubenv var  (add|rm|ls)
hubenv data (ls|download|unpack|pack|clean)
hubenv export NAME  [--to-mamba-spec|--to-requirements|--to-wrangler-spec] [-o FILE|-]
hubenv status
hubenv doctor
hubenv completions (bash|zsh|fish)
```

Per-command syntax is summarized below. `<NAME>` is a single environment name;
where a glob is accepted it is noted explicitly.

## Detailed commands

### `hubenv env` — Environment management

#### `hubenv env create`

Seed the implicit wrangler spec from familiar inputs:

```sh
hubenv env create --from-empty                              [--python 3.11] [--name N] [--display-name D]
hubenv env create --from-requirements <requirements.txt...> [--python 3.11] [--name N] [--display-name D]
hubenv env create --from-mamba-spec   <mamba-spec.yaml>     [--python 3.11] [--name N] [--display-name D]
hubenv env create --from-wrangler-spec <wrangler-spec.yaml> [--name N] [--display-name D]
hubenv env create --from-notebooks    <http(s)-ipynb | local-ipynb...> [--name N] [--display-name D]
hubenv env create --from-existing-env <ENV_NAME>            [--name N] [--display-name D] [--pantry P]
```

- `--name` / `--display-name` / `--python` are the global identifiers; prefer
  flags over positional names to keep syntax uniform across groups.
- `--dry-run` is accepted to preview the seeded spec without installing.
- `--from-existing-env <ENV_NAME>` imports an already-installed mamba/micromamba
  environment into the PPE lifecycle. It exports the env's package set via
  `mamba env export --no-builds` (conda) and `pip freeze` (pip), writes the
  shadow `.hubenv-spec.yaml`, registers the Jupyter kernel, and writes a shelf
  `nbw-wrangler-spec.yaml` so `hubenv env save`/`restore`/`ls` work immediately —
  all **without** re-creating the environment. `--name` becomes the PPE
  lifecycle name; `--pantry` selects the target pantry directory (defaults to
  the first writable pantry).

#### `hubenv env install` / `hubenv env uninstall`

Update the package set of a live environment (covers *Update Environment*):

```sh
hubenv env install   NAME PACKAGE... [--using=mamba|pip|uv] [--no-relock] [--dry-run]
hubenv env uninstall NAME PACKAGE... [--using=mamba|pip|uv] [--no-relock] [--dry-run]
```

- Delegates to the chosen installer on the live env and records the new package
  list in the implicit wrangler spec.
- **Does not auto-trigger re-curation/re-locking** (which can take minutes and
  fail, requiring a loop). Instead it marks the spec dirty and prints
  *"Run `hubenv env relock NAME` to re-curate locks and validate."* Use
  `--no-relock` to suppress even that suggestion.
- `--using` defaults to the platform/uv convention; pick explicitly per command.
- `--dry-run` previews the install plan without changing anything.

This mirrors the existing `--packages-install`/`--packages-uninstall` flags in
`nb_wrangler/cli.py` while making the expensive lock step explicit and separate.

#### `hubenv env ls`

```sh
hubenv env ls [NAME-or-glob...] [--all] [--pantry PATH] [--format table|json]
```

- Lists pantry@`NAME` pairs found anywhere on `NBW_PANTRY`, plus live envs under
  `NBW_ROOT` (marked with `*`).
- `--all` disables "first match wins" collapsing and lists every match.
- `--pantry PATH` restricts the search to one pantry.
- Reports r/w vs r/o per pantry and per shelf.

#### `hubenv env info NAME`

```sh
hubenv env info NAME [--pantry PATH]
```

Disambiguates a name: shows which pantry each match lives in, the live/restore
hash pairing, kernel registration state, and the source spec used to seed it.

#### `hubenv env restore NAME`

```sh
hubenv env restore NAME [--pantry PATH] [--force] [--at-boot]
```

Thaws an archived environment so it can be used; registers it as a Jupyter
kernel. Restores from the first pantry with a matching shelf; idempotent when the
pantry save-hash matches the live restore-hash (use `--force` to override).

- Prints `eval`-able shell exports so users can `eval "$(hubenv env restore NAME)"`
  (mirrors the existing `nb-wrangler setenv` hook).
- `--pantry PATH` forces a source pantry.
- `--at-boot` registers a non-interactive, idempotent restore for startup
  (`.bashrc`/spawn hook) without prompting — replaces the "edit your dotfiles"
  workaround.

#### `hubenv env save`

```sh
hubenv env save NAME [--pantry PATH] [--dry-run]
```

Creates an archive `can` of the named live environment, defaulting to the first
writable pantry in `NBW_PANTRY` (or `--pantry`).

#### `hubenv env rm`

```sh
hubenv env rm NAME... [--live | --archived | --both] [--yes] [--dry-run]
```

Deletes matching environments from live storage, archive storage, or both.

- **Interactive by default** (a package-installer `apt`-like model): confirm
  before deleting, because a glob can match many shared envs. Pass `--yes`/`-y`
  to skip confirmation (scripts/automation).
- `--dry-run` previews the deletion.

#### `hubenv env relock`

```sh
hubenv env relock NAME [--dry-run]
```

Explicitly re-curates the implicit wrangler spec to resolve dependencies and
update lock files. This is **not** an automatic side effect of `install` — making
it explicit avoids the surprise of multi-minute re-lock loops hiding behind a
fast-looking command.

#### `hubenv env ensure NAME`

```sh
hubenv env ensure NAME [--pantry PATH]
```

Idempotent restore-or-create: if a live env exists, no-op; if an archive exists,
restore it; otherwise report so the caller can create it. Safe to call from
`.bashrc`/spawn hooks without prompting.

#### `hubenv env register` / `hubenv env unregister`

```sh
hubenv env register NAME
hubenv env unregister NAME
```

(Re)register or remove the Jupyter kernel for `NAME`. `hubenv env restore` calls
`register` automatically; these expose it for cases where the kernel JSON is
stale but the env is fine.

### Activation model (no `source hubenv activate/deactivate`)

`hubenv` **does not** provide `source hubenv activate`/`deactivate`. Reasons:

- The terminal's active environment is already solved by `mamba activate`/`conda
  activate`; duplicating it invites "which one is right?" confusion (the
  original plan itself hedged that `mamba activate` *"works(?)"*).
- `deactivate`-for-"symmetry" is an anti-pattern: a phantom command that exists
  only for name symmetry is a frequent source of user surprise.

`hubenv` instead owns the things mamba does *not* do:

- **Kernel registration/cleanup**, so notebooks can select the env as a kernel.
- **Environment-variable injection**, surfaced as an explicit, opt-in export
  (`hubenv var ls --export` or `hubenv env restore`'s `eval`-able output).

Users who want PPE env vars in their shell can:
```sh
eval "$(hubenv var ls NAME --export)"
# or, after restore:
eval "$(hubenv env restore NAME)"
```

### `hubenv var` — Environment variables

Variables are stored in the implicit wrangler spec and injected at kernel
registration time (so notebooks see them) and via an explicit export for shells.
`hubenv` does **not** manage users' shell dotfiles ("var exports rc").

```sh
hubenv var add   NAME VAR=VALUE...   [--dry-run]
hubenv var rm    NAME GLOB...        [--dry-run]
hubenv var ls    NAME [GLOB...]      [--export] [--format table|json]
```

- `add` updates the implicit spec + kernel definition for notebooks.
- `ls --export` prints `export VAR=VALUE` lines suitable for `eval`; without it,
  a two-column table.
- `rm` removes from the implicit spec + kernel definition only.

### `hubenv data` — Data management

Data is a first-class concern on the science platform, so it gets its own group
(mirroring the existing `--data-*` flags in `nb_wrangler/cli.py`):

```sh
hubenv data ls       NAME [--format table|json]
hubenv data download NAME [--select REGEX] [--no-validate]
hubenv data unpack   NAME [--no-unpack-existing] [--symlinks|--no-symlinks]
hubenv data pack     NAME
hubenv data clean    NAME [archived|unpacked|both]
```

### `hubenv export`

```sh
hubenv export NAME --to-mamba-spec     [-o FILE|-]
hubenv export NAME --to-requirements   [-o FILE|-]
hubenv export NAME --to-wrangler-spec  [-o FILE|-]
```

Extracts the implicit wrangler spec (or a derived format) for `NAME`. A
destination of `-` writes to stdout. `--to-requirements` and `--to-mamba-spec`
are generated from the locked spec while the environment is available.

### `hubenv status`

Shows the active environment (if any), active pantry path, live vs. archived
state, kernel registration state, and r/w status of each pantry. Single-command
onboarding answer to "what have I got and what's active?"

### `hubenv doctor`

Self-test: mamba/micromamba availability, `NBW_PANTRY` writability, EFS mount
status, and kernel-JSON sanity. Designed to replace the most common support
questions.

## Shell integration

- Bash/zsh/fish completions shipped out of the box; use
  `hubenv completions bash|zsh|fish` to print the static completion script
  (no `argcomplete`/runtime dependency required).  Install with:

  ```sh
  # bash (user)
  eval "$(hubenv completions bash)" >> ~/.bashrc
  # zsh (user)
  echo 'eval "$(hubenv completions zsh)"' >> ~/.zshrc
  # fish (user)
  hubenv completions fish > ~/.config/fish/completions/hubenv.fish
  ```

- `hubenv env restore NAME` (and `hubenv var ls --export`) print `eval`-able output,
  mirroring the existing `nb-wrangler setenv` hook pattern (hook mamba, then
  `eval` exports, then activate the target env).

## Pantry disambiguation rules

To avoid silent "first match wins" shadowing at platform scale:

- `NAME` resolves to a single env. If it matches in multiple pantries, `hubenv`
  **lists all matches and asks** (interactive) or errors (non-tty), unless
  `--pantry PATH` is given.
- `--all` disables collapsing and lists every `pantry@NAME` match.
- Shadowing (one name present in a higher-priority pantry) is warned about in
  `hubenv env ls` / `hubenv env info`.

## Environment lifecycle (summary)

1. **Define:** `hubenv env create --from-requirements requirements.txt --name astro-py --python 3.11`
2. **(Optional) lock:** `hubenv env relock astro-py`
3. **Use:** select the `astro-py` kernel in Jupyter, or `mamba activate astro-py`
   in a terminal; pull PPE env vars via `eval "$(hubenv var ls astro-py --export)"`.
4. **Archive:** `hubenv env save astro-py`
5. **Restore later:** `hubenv env restore astro-py`, then pick the kernel.

**Importing an existing env (no re-creation):**

2. **Onboard:** `hubenv env create --from-existing-env astro-py --name astro-py`
   — writes the shadow spec, registers the kernel, and creates a shelf spec so
   `hubenv env save`/`restore` work immediately. The env is not reinstalled.
2. **(Optional) archive:** `hubenv env save astro-py` (now backed by the shelf spec).

## Relationship to existing modules

`hubenv` is a wrapper. Build on these existing modules rather than reimplementing:

- `nb_wrangler/pantry.py` — `NbwPantry` / `NbwPantrySet`, `NBW_PANTRY` handling
  and shelf/can layout.
- `nb_wrangler/environment.py` — `WranglerEnvable`, environment install/pack/unpack.
- `nb_wrangler/registry.py` — kernel registration and JSON management.
- `nb_wrangler/cli.py` — existing `--env-*`, `--data-*`, `--packages-*` flags are
  the substrate `hubenv env`/`hubenv data`/`hubenv var` wrap.

## Validation

Once implemented, validate with the project's existing tooling:

```sh
make unit-test                 # focused tests for hubenv command parsing/behaviour
make lint/flake8 && make lint/black && make lint/mypy   # style + typing
make test-functional
# smoke:
hubenv completions bash            # print bash completion script
```