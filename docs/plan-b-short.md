# Persistent Platform Environments CLI (net)

## Scope

This describes the proposed CLI for users and admins managing PPE's.

### Features

- Automatic kernel registration / cleanup
- Automatic shell environment handling (notebook + terminal)
- NBW_PATH for User, Team, and Mission/image level PPE pantries
- NBW_ROOT / NBW_LIVE for live environments + wrangler + caches

- Optional notebook handling:
  1. Consolidation of package requirements for multiple repos/notebooks
  2. Easy repo cloning and updates
  3. Automatic version pinning
  4. Easy import and headless notebook testing

- Optional data management:
  1. Consolidation of data assets from multiple repos and systems
  2. Easy data downloads for personal or shared use
  3. Automatic version pinning

#### Configure archive and live storage

`NBW_ROOT` defines the location of live Wrangler environments. This defaults
to container storage on the platform.

`NBW_PANTRY` defines a lcolon seperated ist of Wrangler `pantry` directories used to archive persistent environments.  Each pantry can store multiple environments, each environment gets its own `shelf`.  These are nominally located on persistent EFS.

`NBW_PANTRY` lookups are similar to `PATH` program lookups used by modern OSes.

`NBW_PANTRY` accepts a colon delimited list of `pantry` directories each of which has a `shelf` for each environment (spec + inputs + code + data) and a `can` for each code archive.

e.g. for personal, team, and system level pantries do:

```/bin/sh
export NBW_PANTRY=$HOME/.nbw-pantry:/teams/team-1/nbw-pantry:/teams/admin/nbw-pantry
```

Currently the configuration supporting shared data on the platform is just:

```/bin/sh
export NBW_PANTRY=/teams/admin/nbw-pantry
```

Unpacked data and data archives also live in environment archive `shelves`.

### Commands

To provide a simple intuitive CLI dedicated to PPE management, we add a new tool `net` which works in familiar terms while maintaining an implicit wrangler spec in the background.  This tool should have a simplified and intuitive command set.

For each individual command below, the full syntax is e.g.:

```/bin/sh
net create --from-requirements requirements.txt
```

or more abstractly

```/bin/bash
net <verb> [<adverbs>] [<parameters...>] <--switches and parameters>
```

#### Create from Specs (create)

Seed implicit wrangler spec using familiar spec formats:

```/bin/sh
net create --from-empty
net create --from-requirements <requirements.txt...>
net create --from-mamba-spec <mamba-spec.yaml>
net create --from-wrangler-spec <wrangler-spec.yaml>
net create --from-notebooks <http-ipynb's or local-ipynb's...>

global switches: [--python-version p] [--env-name e] [--display-name d]
```

#### Update Environment (no net command)

Use normal mamba, pip, or uv installs and uninstalls then `net save`.
This is a goal not a certainty since it makes implicit spec maintenance trickier.

#### Archive environment

Creates an archive file (`can`) of the specified environment defaulting to the first pantry in `NBW_PATH` or the pantry specified by `NBW_SAVE`.

```/bin/sh
net save [unique-e-glob]
```

`unique-e-glob` is a pantry/environment glob that resolves to a single environment.
`e-glob` is a pantry/environment glob that resolves to a list of pantry:environment pairs.
The default env is current environment.

#### Restore environment

Thaws out an archived environment so it can be used. Registers with Jupyter.

```/bin/sh
net restore [unique-e-glob]
```

- Restores from the first pantry with a matching environment.
- Idempotent if pantry last-save-hash matches live last-restore-hash
- To "auto-restore e.g. team env" add to .bashrc

#### Delete environments

Deletes an environment, either from live storage, archive storage, or both.

```/bin/sh
net rm [e-glob] [--live | --archived | --both] [--yes]
```

Delete matching environments interactively unless `--yes`

#### List available environments

List environments found in any pantry and/or live under NBW_ROOT.

```/bin/sh
net ls [e-glob]
```

Identifies pantry/environment pairs found anywhere on the NBW_PANTRY path mathing e-glob.
Identifies live environments with *

#### Add env vars

Adds an environment variable to for terminals and notebooks when this net env is active.

```/bin/bash
net evar-add [unique-e-glob] [VAR=VALUE...]`)
```

#### Remove env vars

Removes from evars from implicit wrangler spec and kernel definition.

```/bin/bash
net evar-rm [unique-e-glob] [VAR=VALUE...]`)
```

#### List env vars

Lists the environment variables that this environment defines for the jupyter kernel.

```/bin/bash
net evar-ls [unique-e-glob] [VAR=VALUE...]`)
```

#### Export (export)

Extracts the specified information and format from the implicit wrangler spec.
A destination file of `-` specifies stdout.

```/bin/bash
net export --to-mamba-spec [mamba-spec.yaml | -]
net export --to-requirements-list [requirements.txt | -]
net export --to-wrangler-spec [wrangler-spec.yaml | -]
```


