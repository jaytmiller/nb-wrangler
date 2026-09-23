# Plan D

Plan D is a hybrid concept which relies on automatically curating or re-installing spec'd
environments on the platform, potentially by offering them on the spawner in addition
to the image selection. In a nutshell it replaces the GitHub pipelines and ECR for mission
environments with on-platform mini-pipelines based no wrangler curation or archive
unpacking.

Among the benefits proposed here is moving all of the complexity of running nb-wrangler outside the scope
of notebook testers eliminating training and tooling issues. This is an identical win to the GitHub curation
pipeline but simpler and more localized pipeline.  The scheme drops all complexity associated with
the GitHub pipeline, GHCR, image scanning, ECR, and inlined perpetually failing notebook tests. It improves
or maintains spawn times by replacing copies of huge images with runtime environment curation or unpacking.
It replaces ~1 hour pipelined test image builds with ~5-10 min re-spawns and dynamic env installation.

Potentially this frees Octarine from mid-to-late-game image builds where notebook curators need to iterate
with small environment changes rapidly but when environments are nevertheless fairly stable and almost always
build successfully even if they cannot yet support all notebooks.

Loose ends:
a. How does a curator choose a wrangler spec. Ans: spawner image selection replaced/augmented by spec selection.
   Latest spec scraped from GitHib repo which tracks specs for each build on dedicated branches.
b. What happens when a spec curation fails? (Need solid solution for reporting build log)
c. How do curators iterate? 1. modify spec on GitHub branch.  2. select spec and re-spawn.
d. How do finalized curated specs get uploaded to GitHub for permanant reference + re-installs?
e. How do we manage prod vs. test specs?   Maintain prod branch on GitHub.
f. How many GitHub repos do we need for all missions?  One. Use either deployment branches or directories
   for each notebook_repo we're supporting. Each site chooses portions of GitHub it wants to publish.
