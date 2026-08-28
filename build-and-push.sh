#!/usr/bin/env bash
# Builds the google-findmy-api image and pushes it to a private Docker Hub repo.
#
# secrets.json is NEVER baked into the pushed image: this script temporarily
# moves rest-api/auth_data/secrets.json out of the build context (if present)
# before building, and restores it afterwards. Runtime configuration is done
# entirely via the docker-compose volume/file mount (see docker-compose.portainer.yml).
#
# Usage:
#   ./build-and-push.sh [tag]
#
# Env overrides:
#   DOCKER_USER   Docker Hub username (default: ericfg82)
#   IMAGE_NAME    Repository name     (default: google-findmy-api)
#   PLATFORMS     Target platform(s)  (default: linux/amd64)

set -euo pipefail

DOCKER_USER="${DOCKER_USER:-ericfg82}"
IMAGE_NAME="${IMAGE_NAME:-google-findmy-api}"
PLATFORMS="${PLATFORMS:-linux/amd64}"
TAG="${1:-latest}"
FULL_IMAGE="docker.io/${DOCKER_USER}/${IMAGE_NAME}"

cd "$(dirname "$0")"

SECRETS_FILE="auth_data/secrets.json"
SECRETS_BACKUP=""

cleanup() {
    if [ -n "$SECRETS_BACKUP" ] && [ -f "$SECRETS_BACKUP" ]; then
        mv "$SECRETS_BACKUP" "$SECRETS_FILE"
        echo "Restored ${SECRETS_FILE}"
    fi
}
trap cleanup EXIT

if [ -f "$SECRETS_FILE" ]; then
    SECRETS_BACKUP="$(mktemp)"
    mv "$SECRETS_FILE" "$SECRETS_BACKUP"
    echo "secrets.json set aside for this build - it will NOT be included in the pushed image."
fi

echo "Building and pushing ${FULL_IMAGE}:${TAG} (${PLATFORMS})..."

BUILD_TAGS=(-t "${FULL_IMAGE}:${TAG}")
if [ "$TAG" != "latest" ]; then
    BUILD_TAGS+=(-t "${FULL_IMAGE}:latest")
fi

docker buildx build \
    --platform "$PLATFORMS" \
    --provenance=false \
    --sbom=false \
    "${BUILD_TAGS[@]}" \
    --push \
    .

echo ""
echo "Done: ${FULL_IMAGE}:${TAG}"
echo "Make sure the repo is set to Private at https://hub.docker.com/r/${DOCKER_USER}/${IMAGE_NAME}/settings"
