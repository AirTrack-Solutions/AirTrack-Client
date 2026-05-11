#!/bin/bash
# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

echo "Starting Docker cleanup... this won't touch running containers"

# Remove stopped containers
echo "🗑️ Removing stopped containers..."
docker container prune -f

# Remove unused images
echo "🗑️ Removing unused Docker images..."
docker image prune -a -f

# Remove unused volumes
echo "🗑️ Removing dangling volumes..."
docker volume prune -f

# Remove unused networks
echo "🗑️ Removing unused networks..."
docker network prune -f

# Remove dangling build cache
echo "🧹 Cleaning up builder cache..."
docker builder prune -f

# Optional: clear old update archives
UPDATE_DIR="${AIRTRACK_UPDATES_DIR:-/app/static/updates}/old"
if [ -d "$UPDATE_DIR" ]; then
  echo "🧹 Cleaning up old AirTrack update archives..."
  find "$UPDATE_DIR" -type f -name "*.zip" -delete
fi

echo "✅ Cleanup complete. AirTrack remains safe and flying."
df