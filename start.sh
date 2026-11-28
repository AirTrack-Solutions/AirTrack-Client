#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -f .env ]]; then
    echo "No .env found here. Run bash install.sh for a new installation or open your existing AirTrack folder." >&2
    exit 1
fi
docker compose -f docker-compose.client.yml up -d --no-build --wait --wait-timeout 180
endpoint=$(docker compose -f docker-compose.client.yml port airtrack 5000)
printf 'AirTrack is running at http://localhost:%s\n' "${endpoint##*:}"
