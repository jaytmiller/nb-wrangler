# Persistent Platform Environments CLI (ppe)

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

#### Configure Storage

##### Live

`NBW_ROOT` defines the location of live Wrangler environments. This defaults to container storage on the platform.  Using container storage makes installing or running

##### Archive

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

To provide a simple intuitive CLI dedicated to PPE management, we add a new tool `ppe` which works in familiar terms while maintaining an implicit wrangler spec in the background.  This tool should have a simplified and intuitive command set.

For each individual command below, the full syntax is e.g.:

```/bin/sh
ppe create --from-requirements requirements.txt
```

or more abstractly

```/bin/bash
ppe <verb> <--switches and parameters>
```

#### Create Environment

Seed implicit wrangler spec using familiar spec formats:

```/bin/sh
ppe create [env-name] --from-empty
ppe create [env-name] --from-requirements <requirements.txt...>
ppe create [env-name] --from-mamba-spec <mamba-spec.yaml>
ppe create [env-name] --from-wrangler-spec <wrangler-spec.yaml>
ppe create [env-name] --from-notebooks <http-ipynb's or local-ipynb's...>

global switches: [--python-version p] [--env-name e] [--display-name d]
```

#### Activate Environment

In a terminal, to switch to an environment, do:

```/bin/sh
source ppe activate [env-name]
```

This results in the output from `mamba activate env-name`, PPE env vars, etc.
Mamba activate also works(?) but does not include PPE env vars.

#### Deactivate Environment

In a terminal, to deactivate the current environment, do:

```/bin/sh
source ppe deactivate
```

This is here for symmetry with `ppe activate` to avoid the surprise and confusion
for some folks that `ppe deactivate` does not work and some undefined equivalent
must be used instead.

`mamba deactivate` should work equally well since this is independent of
uninstalling the environment from live storage or removing the environment
variables defined by the current environment.

#### Update Environment

Trivial wrappers `ppe install` and `ppe uninstall` can be added targeting the current environment and qualified by:

```/bin/sh
ppe install --using-mamba packages...
ppe install --using-pip packages...
ppe install --using-uv packages...
```

The key reason for these is to automatically update the implied wrangler spec and re-curate
to resolve dependencies and update the lock files.

Being active implies that the current pantry@environment pair already exists in either live or archived forms. In the case of archived environments, the default is the first found version of
pantry@environment. If no pantry shelf exists for a particular pantry@environment, one is created.

#### Archive environment

Creates an archive of the specified environment defaulting to the first pantry in `NBW_PATH`.

```/bin/sh
ppe save [env-name]
```

`unique-e-glob` is a pantry@environment glob that resolves to a single environment.
The default pantry@environment is current pantry@environment.

#### Restore environment

Thaws out an archived environment so it can be used. Registers with Jupyter.

```/bin/sh
ppe restore [env-name]
```

- Restores from the first pantry with a matching environment.
- Idempotent if pantry last-save-hash matches live last-restore-hash
- To "auto-restore e.g. team env" add to .bashrc

#### Delete environments

Deletes matching environments, either from live storage, archive storage, or both.

```/bin/sh
ppe rm [env-names...] [--live | --archived | --both] [--yes]
```

`env-names...` is a pantry@environment glob that resolves to a list of pantry@environment pairs.
Delete matching environments interactively unless `--yes`.

#### List environments

List environments found in any pantry and/or live under NBW_ROOT.

```/bin/sh
ppe ls [env-names...]
```

Identifies pantry@environment pairs found anywhere on the NBW_PANTRY path mathing and of `env-names...`
Identify live environments.
Identify r/w vs. r/o pantries.

#### Add env vars

Adds an environment variable to for terminals and notebooks when this ppe env is active.

```/bin/bash
ppe var --add [VAR=VALUE...]`)
```

#### Remove env vars

Removes vars from implicit wrangler spec, kernel definition, var exports rc.

```/bin/bash
ppe var --rm [var-globs...]`)
```

#### List env vars

Lists the environment variables that this environment defines for the terminal or jupyter kernel (making them available in notebooks). This is a very limited subset of the variabled reported by `printenv`.

```/bin/bash
ppe var --ls [var-globs...]

--as-exports    prints env vars as shell export commands
--tabular       prints env vars in two columnd tabular form
```

#### Export spec (export)

Extracts the implicit wrangler spec for this PPE.
A destination file of `-` specifies stdout.

```/bin/bash
ppe export [nbw-wrangler-spec.yaml|-]
```

Mamba and pip specs can be generated normally using mamba or pip while the environment is activated.
