# Releasing the REST API Docker image

The REST API is published as a public Docker Hub image:
`docker.io/ericfg82/google-find-my-device-rest-api`. This document covers how to cut a
new version and get it running on the NAS.

**GitHub Actions is the only way this image gets published** - there is no local
build/push script. This guarantees every published image (including `:latest`)
traces back to a real commit in the repo, not to whatever happened to be on
someone's laptop at the time.

## Overview

```
git tag vX.Y.Z  ──push──>  GitHub Action  ──build & push──>  Docker Hub (public)
                                                                     │
                                                        Portainer "Pull and redeploy"
                                                                     ▼
                                                              NAS (Synology)
```

- `secrets.json` is **never** in the image: it's git-ignored, so it simply doesn't
  exist in the CI checkout the workflow builds from. The running container always
  gets it via a volume/file mount instead - see
  [`docker-compose.portainer.yml`](docker-compose.portainer.yml) and
  [`AUTHENTICATION.md`](AUTHENTICATION.md).
- The build disables buildx's provenance/SBOM attestations (`provenance: false`,
  `sbom: false` in the workflow). Without this, buildx wraps the image in an OCI
  index with an extra "attestation manifest" that Synology's Container Manager
  fails to parse when checking for updates - it silently never shows "update
  available".
- The image's reported version (`/` and `/docs`) comes from the `APP_VERSION`
  build-arg the workflow passes in (derived from the git tag), not a hardcoded
  string - see the `Determine image tags and app version` step in the workflow.

## One-time setup

Already done as of `v1.1.0` - listed here in case it ever needs redoing (e.g. the
token expires).

In GitHub → repo → **Settings → Secrets and variables → Actions**, add:
- `DOCKERHUB_USERNAME` = `ericfg82`
- `DOCKERHUB_TOKEN` = a Docker Hub **Access Token** (Docker Hub → Account
  Settings → Security → New Access Token), Read & Write scope.

## Cutting a release

```bash
# 1. Add an entry to CHANGELOG.md describing what changed.
# 2. Commit it.
git add CHANGELOG.md
git commit -m "chore: Release vX.Y.Z"

# 3. Tag the commit and push both.
git tag vX.Y.Z
git push origin main --tags
```

Pushing the tag triggers [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml),
which builds the image from this repo and pushes both `ericfg82/google-find-my-device-rest-api:vX.Y.Z`
and `:latest`. Watch it under the repo's **Actions** tab.

To publish `:latest` without cutting a tagged version (e.g. to smoke-test a change
on the NAS before committing to a version number), trigger the workflow manually
from the **Actions** tab (`workflow_dispatch`) - it publishes `:latest` only.

## Deploying a new version to the NAS

`docker-compose.portainer.yml` pins a specific version tag (currently
`v1.2.1`) rather than `:latest`, so redeploys are deliberate:

1. Bump the `image:` tag in `docker-compose.portainer.yml` to the new version and
   commit it.
2. In Portainer → **Stacks → your stack → Editor**, paste the updated compose file
   (or pull the change if the stack is git-linked), check **"Re-pull image"**, and
   **Update the stack**.
3. Confirm: `docker inspect google-find-my-device-rest-api --format '{{.Image}}'` should match
   the digest Docker Hub shows for that tag.

Don't rely on Synology Container Manager's "check for update" badge - it doesn't
reliably track images that weren't pulled through its own UI (e.g. images managed
via Portainer). Re-pulling explicitly through Portainer (or `docker pull` +
`docker compose up -d --force-recreate` over SSH) always works regardless.
