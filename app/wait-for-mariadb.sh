#!/bin/sh

# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# wait-for-mariadb.sh
# Gracefully wait for MariaDB, then launch AirTrack as PID 1.

file /app/db/schema.sql | grep -qi utf-16 && {
  echo "❌ schema.sql is UTF-16 — refusing to import"
  exit 1
}

set -eu

HOST="${MYSQL_HOST:-airtrack-db}"
PORT="${MYSQL_PORT:-3306}"
TIMEOUT="${WAIT_TIMEOUT:-60}"

echo "Waiting for MariaDB at ${HOST}:${PORT} (timeout ${TIMEOUT}s)…"
i=0
while ! nc -z "$HOST" "$PORT" 2>/dev/null; do
  i=$((i+1))
  if [ "$i" -ge "$TIMEOUT" ]; then
    echo "ERROR: MariaDB not reachable after ${TIMEOUT}s" >&2
    exit 1
  fi
  sleep 1
done
echo "MariaDB is up."

# IMPORTANT: replace the shell with your app so Python is PID 1
exec "$@"
