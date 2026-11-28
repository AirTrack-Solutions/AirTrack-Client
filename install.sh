#!/bin/bash
# AirTrack Linux Client — Installer
# https://airtracksolutions.com

set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

COMPOSE_FILE="docker-compose.client.yml"
IMAGE="ghcr.io/airtrack-solutions/airtrack-client:latest"

echo ""
echo "  ✈  AirTrack Linux Client — Installer"
echo "  ======================================="
echo ""

# ── Checks ────────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "  ✗  Docker is not installed."
    echo "     Install it from: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker compose version &>/dev/null 2>&1; then
    echo "  ✗  Docker Compose plugin not found."
    echo "     Install it from: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "  ✓  Docker found: $(docker --version)"

# ── Directory structure ────────────────────────────────────────────────────────
mkdir -p data logs keys
echo "  ✓  Created data/, logs/, keys/ directories"

# ── .env setup ────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    (umask 077; cp .env.example .env)

    DB_PASS=$(od -An -N24 -tx1 /dev/urandom | tr -d '[:space:]')
    ROOT_PASS=$(od -An -N24 -tx1 /dev/urandom | tr -d '[:space:]')
    SESSION_KEY=$(od -An -N32 -tx1 /dev/urandom | tr -d '[:space:]')

    sed -i "s/CHANGE_ME_ROOT/${ROOT_PASS}/g; s/CHANGE_ME/${DB_PASS}/g" .env
    printf '\nSECRET_KEY=%s\n' "$SESSION_KEY" >> .env

    echo "  ✓  .env created with a random database password"
else
    echo "  ✓  .env already exists — skipping"
fi

# ── License ───────────────────────────────────────────────────────────────────
if [ -f keys/license.lic ]; then
    echo "  ✓  License file found — licensed edition will be used"
else
    echo "  ℹ  No license file found in keys/ — running as Lite edition"
    echo "     To upgrade, place your license.lic in the keys/ directory and restart."
fi

# Load the image supplied with the distribution. Source-only installs use GHCR.
case "$(uname -m)" in
    x86_64) local_arch=amd64 ;;
    aarch64|arm64) local_arch=arm64 ;;
    *) echo "AirTrack requires a 64-bit AMD64 or ARM64 system." >&2; exit 1 ;;
esac

if [ -f airtrack-client-image.tar.gz ] || [ -f image-tag ] || [ -f image-arch ]; then
    if [ ! -f airtrack-client-image.tar.gz ] || [ ! -f image-tag ] || [ ! -f image-arch ]; then
        echo "The AirTrack image bundle is incomplete. Extract the entire archive." >&2
        exit 1
    fi
    if [ "$(cat image-arch)" != "$local_arch" ]; then
        echo "This bundle is for $(cat image-arch). This computer needs $local_arch." >&2
        exit 1
    fi
    IMAGE=$(cat image-tag)
    [[ "$IMAGE" =~ ^airtrack:client-[a-zA-Z0-9._-]+$ ]] || {
        echo "Invalid bundled AirTrack image tag." >&2
        exit 1
    }
    docker load -i airtrack-client-image.tar.gz
else
    docker pull "$IMAGE"
fi
if [ "$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$IMAGE")" != "linux/$local_arch" ]; then
    echo "The Docker image does not match this machine." >&2
    exit 1
fi
docker tag "$IMAGE" airtrack:client

echo "  Starting AirTrack…"
docker compose -f "$COMPOSE_FILE" up -d --no-build --wait --wait-timeout 180

endpoint=$(docker compose -f "$COMPOSE_FILE" port airtrack 5000)
echo "  AirTrack is running at http://localhost:${endpoint##*:}"
echo ""
echo "  Useful commands:"
echo "    View logs:  docker compose -f $COMPOSE_FILE logs -f"
echo "    Stop:       docker compose -f $COMPOSE_FILE down"
echo "    Restart:    docker compose -f $COMPOSE_FILE restart"
echo ""
