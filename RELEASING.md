# Releasing the REST API Docker image

The REST API is published as a **private** Docker Hub image:
`docker.io/ericfg82/google-findmy-api`. This document covers how to cut a
new version and get it running on the NAS.

## Overview

```
git tag vX.Y.Z  ──push──>  GitHub Action  ──build & push──>  Docker Hub (private)
                                                                     │
                                                        Portainer "Pull and redeploy"
                                                                     ▼
                                                              NAS (Synology)
```

- `secrets.json` is **never** baked into the image, on either path (local script or
  CI) - it's git-ignored, so it doesn't exist in a CI checkout at all, and the local
  script temporarily moves it out of the build context before building. The running
  container always gets it via a volume/file mount instead - see
  [`docker-compose.portainer.yml`](docker-compose.portainer.yml) and
  [`AUTHENTICATION.md`](../AUTHENTICATION.md).
- Builds disable buildx's provenance/SBOM attestations (`--provenance=false
  --sbom=false`). Without this, buildx wraps the image in an OCI index with an
  extra "attestation manifest" that Synology's Container Manager fails to parse
  when checking for updates - it silently never shows "update available".

## Option A: Automatic (GitHub Actions)

**One-time setup** (already done as of `v1.1.0`, skip if it's still configured):

1. In GitHub → repo → **Settings → Secrets and variables → Actions**, add:
   - `DOCKERHUB_USERNAME` = `ericfg82`
   - `DOCKERHUB_TOKEN` = a Docker Hub **Access Token** (Docker Hub → Account
     Settings → Security → New Access Token). Use a dedicated token for CI,
     with Read & Write scope, separate from the one used for local `docker login`.

**Cutting a release:**

```bash
# 1. Add an entry to CHANGELOG.md describing what changed.
# 2. Commit it.
git add CHANGELOG.md
git commit -m "chore: Release vX.Y.Z"

# 3. Tag the commit and push both.
git tag vX.Y.Z
git push origin main --tags
```

Pushing the tag triggers [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml),
which builds the image from `rest-api/` and pushes both `ericfg82/google-findmy-api:vX.Y.Z`
and `:latest`. Watch it under the repo's **Actions** tab. It can also be triggered
manually from there (`workflow_dispatch`) without pushing a tag - that only
publishes `:latest`.

## Option B: Manual (local)

Useful while iterating on a fix, before you're ready to cut a versioned release.

```bash
cd rest-api
docker login -u ericfg82           # once per machine/session
./build-and-push.sh                # no tag arg + HEAD has no git tag -> publishes :latest only
./build-and-push.sh                # no tag arg + HEAD IS tagged (e.g. v1.1.0) -> publishes :v1.1.0 and :latest
./build-and-push.sh v1.2.3         # explicit tag -> publishes :v1.2.3 and :latest, regardless of git tags
```

The script builds for `linux/amd64` by default (matches the NAS). Override with
`PLATFORMS=linux/amd64,linux/arm64 ./build-and-push.sh` if you ever need to also
target an ARM NAS.

## Deploying a new version to the NAS

`rest-api/docker-compose.portainer.yml` pins a specific version tag (currently
`v1.1.0`) rather than `:latest`, so redeploys are deliberate:

1. Bump the `image:` tag in `docker-compose.portainer.yml` to the new version and
   commit it.
2. In Portainer → **Stacks → your stack → Editor**, paste the updated compose file
   (or pull the change if the stack is git-linked), check **"Re-pull image"**, and
   **Update the stack**.
3. Confirm: `docker inspect google-findmy-api --format '{{.Image}}'` should match
   the digest Docker Hub shows for that tag.

Don't rely on Synology Container Manager's "check for update" badge - it doesn't
reliably track images that weren't pulled through its own UI (e.g. images managed
via Portainer). Re-pulling explicitly through Portainer (or `docker pull` +
`docker compose up -d --force-recreate` over SSH) always works regardless.
