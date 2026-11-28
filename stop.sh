#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -f .env ]]; then
    echo "No .env found here. Open your existing AirTrack installation folder." >&2
    exit 1
fi
docker compose -f docker-compose.client.yml down
echo "AirTrack stopped. Database volume retained."
