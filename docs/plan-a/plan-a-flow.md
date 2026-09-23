The current image building workflow is typically based on local development of
wrangler specs followed by running GitHub workflows to create an image
in GHCR and generally has the following steps and/or looping logic:

- Define image specification basic image properties like names and Python version.
- Define notebook repos and notebook selections, extra or special packages, mission specific file assets.
- Curate notebook and packages using the `nbw` tool adding notebook and package locks in the spec.
- If curation fails, loop back to spec definition to resolve issues, redo all subsequent steps.
- If curation succeeds, optionally build an image from the spec locally, test imports, test notebooks.
  Images are built by injecting wrangler spec requirements into original science-platform-image framework
  which is now generic but still relatively complex.
  This ensures end-to-end image framework works vs. local mamba install.
- Commit and push spec to spacetelescope/nb-wrangler-images.
- Run curation or re-installation pipeline on GitHub to build image, test imports, test notebooks, scan-image.
- If GitHub pipeline fails,  loop back to spec definition to resolve issues, redo subsequent steps.
- Use dynamic ECR to spawn with new test image in test
- Verify image on platform, test imports, test notebooks, run notebooks, loop back to spec definition on
  failure to resolve issues, redo all subsequent steps.
- Download vetted image from GHCR and push to ECR. (Missing automation / ECR pull through)
- Tag image for OPS and update OPS profile, PR and merge profile update. (Missing automation)