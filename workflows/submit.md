# Submitting a Wrangler spec to build an image

## Setup for submission

Before you can submit a wrangler spec to trigger an image build you must have
or acquire a few things:

1. Collaboration privileges with the GitHub science-platform-images repo doing the build.
A spacetelescope/science-platform-images admin on GitHub needs to set this up,  contact dmd_octariner@stsci.edu

2. An auth token for yourself to use with the `gh` tool proving who you are to the GitHub project.

3. The gh tool itself for e.g. pushing a branch and creating PR.

4. The nb-wrangler tool for doing spec development and submission to the build pipeline.

5. Environment variable setup for `nb-wrangler`.

## Setting up gh

Fortunately you only have to do this once and then occasionally renew your personal access token.

### Install gh tool

gh can be installed using brew on os-x:

```bash
$ brew install gh
```

or with apt-get on Ubuntu/Debian-based systems:


```bash
$ sudo apt-get install gh
```

### Create your auth token on GitGub

Your auth token will let anyone possessing it perform actions which are ascribed to you. 

To create a token, log into GitHub and navigate to https://github.com/settings/tokens.

Open up the `Personal Access Tokens` menu item and click `Token(classic)`.

The possible actions permitted by the token are limited by "scopes" and for nb-wrangler 
you should give your token the following scopes:  `'read:org', 'repo', 'workflow'`.

These permissions enable the possessor to `push a branch`, `create a PR`, and `trigger an image build.`

### Add an auth token to GH

Before you can perform submissions,  you need to login to gh by navigating a set of choices as follows:

```bash
$ gh auth login
? What account do you want to log into? GitHub.com
? What is your preferred protocol for Git operations on this host? HTTPS
? How would you like to authenticate GitHub CLI? Paste an authentication token
Tip: you can generate a Personal Access Token here https://github.com/settings/tokens
The minimum required scopes are 'repo', 'read:org', 'workflow'.
? Paste your authentication token: 
```

At the last prompt paste in your personal auth token generated previously.

On my Mac Laptop and Ubuntu the token is cached and persists across sessions.


### Checking your gh status

Check your auth status as follows:

```bash
$ gh auth status
github.com
  ✓ Logged in to github.com account homer-curator (keyring)
  - Active account: false
  - Git operations protocol: https
  - Token: ghp_************************************
  - Token scopes: 'read:org', 'repo', 'workflow'
```

At the moment,  the auth token you obtain from GitHub should
have only the above privileges.

To enable pipeline automation,  users with admin permissions are
permitted to bypass the merge restrictions on main and push directly
to it.  Barring exceptional conditions,  even admins should always
do PR's rather than pushing directly to main.

If you have more than one personal access token,  you can also
`gh auth switch` to toggle between them,  if only two tokens are
cached it will toggle between them.

## Doing a submission

Submitting a completed spec to the system is generally easy once auth
is set up.

After bootstrapping, I do:

```bash
$ source nb-wrangler activate nbwrangler
$ nb-wrangler tike-2025.07-beta.yaml --submit-for-build
INFO: 00:00:00.000 Loading and validating spec /home/ai/nb-wrangler/fnc-test-spec.yaml
INFO: 00:00:00.034 Running submit-for-build workflow
INFO: 00:00:00.041 Setting up repository clones.
INFO: 00:00:00.000 Cloning  repository https://github.com/jaytmiller/science-platform-images.git to references/science-platform-images.
INFO: 00:00:01.563 Successfully cloned repository to references/science-platform-images.
INFO: 00:00:00.000 Using existing local clone at references/mast_notebooks
INFO: 00:00:00.000 Using existing local clone at references/tike_content
INFO: 00:00:00.003 Found 8 notebooks in all notebook repositories.
INFO: 00:00:00.000 Processing 8 unique notebooks for imports.
INFO: 00:00:00.001 Extracted 7 package imports from 8 notebooks.
INFO: 00:00:00.000 Revising spec file /home/ai/nb-wrangler/fnc-test-spec.yaml.
INFO: 00:00:00.000 Saving spec file to /home/ai/.nbw-live/temps/fnc-test-spec.yaml.
INFO: 00:00:00.057 Adding spec nbw-68f15f95-TIKE-2025-07-beta-b49d1c.yaml to ingest directory nbw-spec-archive on branch nbw-68f15f95-TIKE-2025-07-beta-b49d1c.
INFO: 00:00:00.017 Checked out repo science-platform-images existing branch origin/main.
INFO: 00:00:00.002 Created new branch nbw-68f15f95-TIKE-2025-07-beta-b49d1c of repo science-platform-images.
INFO: 00:00:00.008 Added nbw-spec-archive/nbw-68f15f95-TIKE-2025-07-beta-b49d1c.yaml to science-platform-images.
INFO: 00:00:00.012 Commited science-platform-images.
INFO: 00:00:00.000 Pushing submission branch nbw-68f15f95-TIKE-2025-07-beta-b49d1c....
INFO: 00:00:00.627 Pushed repo science-platform-images branch nbw-68f15f95-TIKE-2025-07-beta-b49d1c.
INFO: 00:00:00.000 Creating PR...
INFO: 00:00:01.448 Created PR Wrangler spec for build nbw-68f15f95-TIKE-2025-07-beta-b49d1c.yaml. to origin/main for science-platform-images.
INFO: 00:00:00.000 Spec submission complete.
INFO: 00:00:00.000 Workflow submit-for-build completed.
INFO: 00:00:00.000 Running explicitly selected steps, if any.
INFO: 00:00:00.000 Exceptions: 0
INFO: 00:00:00.000 Errors: 0
INFO: 00:00:00.000 Warnings: 0
INFO: 00:00:00.000 Elapsed: 00:00:03
```

**NOTE**: It is not necessary for a spec to be locally installed in order to submit it; however,
the spec should already be fully curated and should pass both input and notebook tests in order
to build and test and image. The spec's sha256 hash also needs to be up-to-date so if you edit the
spec you either need to re-run the curation workflow using `nb-wrangler --curate --test` or you need
to manually update the hash using `nb-wrangler --update-spec-hash`.  While the spec and PR are
validated in a number of ways on GitHub, there are still many basic conditions which can preclude
getting a successful image build.