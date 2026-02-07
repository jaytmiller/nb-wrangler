# Plan C

## Automatic curation

Add curator GitHub Action workflow to automatically curate a spec:
    Motivations
        - Run curation for curators instead of training them until they see benefit to running it themselves
        - Other gains below
    Strategy
        - Trigger action based on all/TBD changes to a repo, nominally a notebook repo
        - Upload fully populated spec to ghcr.io as a trivial / non-executable Docker image
        - Add a "spec image download" and extract/cat switch to nb-wrangler to retrieve named curated specs on ghcr.io as plain text.
        - Build/install ghcr.io based spec anywhere, including Docker images or end-user local environments.
    Gains deployed anywhere,  centrally or per repo:
        - Pushing curated spec to ghcr.io means low-risk per-repo managed GITHUB_TOKEN is sufficient
        - No security risk associated with exposing a "high powered" personal access token (PAT) anywhere
        - No need to set up bot account to own PAT
        - No merge of PR to notebook repo or science-platform-image repo
        - No need to perform main branch protection overrides for admin users violating STScI GitHub usage requirements
        - Elimination of git issues due to PR'ing specs to the science-platform-image repo as an archive

## Centralization if preferred
   - Custom or standard remote repo triggers can be connected to a central SP curation
   - Cost is per-repo access token to SP curator/builder;  WAY better than per-curator tokens
   - Need to line up our own heavy-duty worker nodes

## Automatic image building
   - Add simplified build GitHub Action workflow triggered by spec curation workflow
   - No additional perms required,  just generic workflow

## Centralized core Action logic for generic distributed triggers

   Separate processing into "custom trigger workflow" and "Action-time wrangler clone Action bash scripts" with simple call
   By isolating processing logic to wrangler-repo configured scripts we check out,  multiple repos triggering on
       whatever notebooks or conditions curators wish can use cloned scripts to perform the latest wrangler curation or image building
   Since trigger customization,  if any, would be the primary per-repo mods,  "distributed" standard pipelines are
       feasible with centralized maintenance.
   Scripted Action testing may also be more testable prior to GitHub multi-repo deployment.
   These can even be customized per-repo at setup to simplify centralized per-repo custom maintenance later.
   Check into repos self-identifying for custom script processing by generic workflow

## Central vs. Distributed Curation and Image Building

Who runs the GitHub Actions?  science-platform-images,  or each independent notebook repo,  or both?

With distributed we gain:
   Potentially custom self-controlled curation and image build triggering for each differing notebook effort
   Automatic access to enhanced GitHub action worker nodes now REQUIRED for full image building and scanning.
   Automatic user permission management governed by each repo for itself.
   Distributed image and spec management on ghcr.io vs. one central container repo
   Notebook repos can manage their own containers on ghcr.io, ECR pull through will lock in platform persistence

With distributed we lose:
   Specs stored in ghcr.io are not trivially browseable, need to be fetched and extracted from spec Docker image kludge
   Need "push to public ghcr.io STSCI approval" for every STSCI repo that does this;  but one time cost per-repo, not per-curator
   No single repo for all SP images and specs;  Could be unifiable via guided scraping

## Reductive view of nb-wrangler

   Portable CI/CD pipeline executable anywhere:  GitHub Actions, Locally for curators, Directly on platform, or by end users
   Automatically constructs unified notebook environments and images
   Automatically distributes and performs env-var setup / notebook registration for data or other settings
   In principle,  version locks environments and data
   Supports multiple concurrent environments modulo non-reentrant curator asks like $HOME/refdata which can only point to one environment
