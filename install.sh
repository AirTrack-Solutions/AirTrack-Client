#!/bin/bash
# AirTrack Linux Client — Installer
# https://airtracksolutions.com

set -e

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
    cp .env.example .env

    # Generate a random database password
    if command -v openssl &>/dev/null; then
        DB_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 28)
    else
        DB_PASS=$(cat /proc/sys/kernel/random/uuid | tr -dc 'a-zA-Z0-9' | head -c 28)
    fi

    sed -i "s/CHANGE_ME_ROOT/${DB_PASS}_root/g" .env
    sed -i "s/CHANGE_ME/${DB_PASS}/g" .env

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

# ── Pull image ────────────────────────────────────────────────────────────────
echo ""
echo "  Pulling AirTrack image from GHCR…"
docker pull "$IMAGE"
echo "  ✓  Image ready"

# ── Start ─────────────────────────────────────────────────────────────────────
echo ""
echo "  Starting AirTrack…"
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "  ✈  AirTrack is running at http://localhost:5000"
echo ""
echo "  Useful commands:"
echo "    View logs:  docker compose -f $COMPOSE_FILE logs -f"
echo "    Stop:       docker compose -f $COMPOSE_FILE down"
echo "    Restart:    docker compose -f $COMPOSE_FILE restart"
echo ""
