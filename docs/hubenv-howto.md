# hubenv: Creating Environments (HOWTO)

`hubenv` is the nb-wrangler CLI for managing persistent Jupyter environments.
It builds **live environments** with mamba, tracks them with a **shelf spec**
in the pantry, and can package them as restorable **archives ("cans")** so
they travel with you across machines and sessions.

## Concepts

| Term  | What it is                                                            |
| :---- | :-------------------------------------------------------------------- |
| Live env | A mamba environment under `$NBW_ROOT/mm/envs`. This is what you run.  |
| Shelf    | The pantry record for an env: a spec at `<pantry>/shelves/<name>/nbw-wrangler-spec.yaml`. |
| Can      | A packed archive of the live env. A shelf is only *restorable* once a can exists. |
| Kernel   | The registered Jupyter kernel (display name defaults to the env name). |

Relevant environment variables (defaults):

| Variable     | Default              | Purpose                          |
| :----------- | :------------------- | :------------------------------- |
| `NBW_ROOT`   | `$HOME/.nbw-live`    | Fast, ephemeral live storage     |
| `NBW_PANTRY` | `$HOME/.nbw-pantry`  | Persistent, shareable pantry     |

## Prerequisites

- A mamba-compatible manager on `PATH` (hubenv shells out to it).
- A writable pantry (default `$HOME/.nbw-pantry`, or pass `--pantry`).
- Basic connectivity to `conda-forge` when building new environments.

Check everything with:

```bash
hubenv doctor
```

## Creating a new environment

`hubenv create` requires exactly **one** seed source. `--name` is required
only for `--from-empty` / `--from-requirements`; for the other three sources
the name is derived (see the "Name default" column below):

```bash
hubenv create \
  --name my-env \
  --from-requirements requirements.txt requirements-internal.txt
```

Seed source options (mutually exclusive):

| Flag                | Uses what                                      | Name default (no `--name`) |
| :------------------ | :--------------------------------------------- | :-------------------------- |
| `--from-empty`      | Nothing — an empty env (`pip` + optional Python) | *required* |
| `--from-requirements FILE…` | One or more pip requirements files   | *required* |
| `--from-mamba-spec FILE`   | An existing mamba/conda spec YAML    | spec's `name`, else file stem |
| `--from-wrangler-spec FILE`| A complete nb-wrangler spec YAML     | header `kernel_name`, else `image_name`, else file stem |
| `--from-existing-env ENV_NAME` | Imports an env already present in mamba | imported env's own name |

Useful flags:

| Flag             | Effect                                                              |
| :--------------- | :------------------------------------------------------------------ |
| `--python 3.11`  | Pin the Python version                                               |
| `--display-name` | Jupyter kernel display name (default: the env name)                 |
| `--pantry DIR`   | Target pantry (default: first writable pantry)                      |
| `--dry-run`      | Print the seeded spec to stdout; install nothing                    |
| `--ephemeral`    | Build only the live env — no shelf spec, no kernel (scratch/CI use) |
| `--save`         | Also pack the archive (can) immediately                              |

### What `create` does

1. Resolves the seed source into a mamba spec (channel: `conda-forge`) and
   runs `mamba create` — for `--from-existing-env` it verifies the source env
   exists instead.
2. Persists the essentials: writes the shelf spec to the pantry and registers
   the Jupyter kernel.
3. Prints eval-able exports (`NBW_ACTIVE_ENV`, `NBW_ENV_ROOT`) and a hint to
   run `hubenv save <name>`.

Note that step 2 is *not* archiving: a shelf with a spec but no can shows as
**spec-only** in `hubenv ls`/`status` and is **not** restorable on another
machine until you save it.

### Examples

```bash
# Preview the spec first
hubenv create --name sci --from-requirements reqs.txt --dry-run

# Plain notebook env, Python 3.11
hubenv create --name sci --from-requirements reqs.txt --python 3.11

# Import an env you already built by hand (keeps its own name)
hubenv create --from-existing-env sci-raw

# Build + archive in one shot (restorable)
hubenv create --name sci --from-requirements reqs.txt --save

# Throwaway env for a CI job (no pantry writes, no kernel)
hubenv create --name ci-env --from-requirements reqs.txt --ephemeral
```

## Making an environment restorable

After a plain `create`, package the live env into a pantry can:

```bash
hubenv save my-env            # or: hubenv create … --save
```

- `--pantry DIR` — specific pantry; `--force` — overwrite an existing can;
  `--dry-run` — show planned paths.

On any other machine (or a fresh container with the same pantry) bring it back:

```bash
hubenv ensure my-env     # idempotent: no-op if live, restore can if missing
# or explicitly:
hubenv restore my-env
```

## Using the environment

Activate a shell with the exported snippet (output is safe for `eval`):

```bash
eval "$(hubenv activate my-env)"
```

Or pick the registered kernel (display name) in JupyterLab — the registered
kernel spec already carries the environment's variables.

Manage packages:

```bash
hubenv install my-env "pandas>=2"        # hubenv suggests `relock` after this
hubenv uninstall my-env pandas
hubenv relock my-env                     # re-curate pip locks / refresh the spec
```

Inspect state:

```bash
hubenv ls                 # live envs + pantry shelves
hubenv info my-env        # detail for one env
hubenv status             # whole-system summary (pantries, kernels, active env)
hubenv doctor             # self-test: mamba, pantry, kernel, spec-only shelves
```

## Removing environments

```bash
hubenv rm my-env              # remove live + archived (default: both)
hubenv rm --live team-* -y    # live only, glob, no prompt
```

## Quick recipe

```bash
hubenv create --name v2  --from-requirements reqs.txt --python 3.11
hubenv save   --name v2                # now restorable
eval "$(hubenv activate v2)"           # use it
hubenv ls                              # confirm
```

If creation fails midway, `hubenv rm --dry-run my-env` to see what would be
removed, then `hubenv create --name my-env …` again — `create` is additive,
and partial shelves are shown as spec-only until saved.
