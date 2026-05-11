# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

#!/bin/bash
# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


SQL_DIR="/home/trevor/docker/airtrack/app/static/updates/sql"
OUTPUT="$SQL_DIR/airlines_logos.sql"
CONTAINER_NAME="airtrack-airtrack-1"
DB_HOST="airtrack-airtrack-db-1"
DB_USER="SirBob"
DB_PASS="ofAirTrack"  # Replace this with your actual password
DB_NAME="airtrack"
DB_TABLE="airlines"

mkdir -p "$SQL_DIR"

echo "[INFO] Exporting $DB_TABLE table with logos from app container..."

docker exec "$CONTAINER_NAME" \
  sh -c "mysqldump -h $DB_HOST -u $DB_USER -p$DB_PASS --skip-comments --no-create-info --skip-triggers --where='Logo IS NOT NULL' $DB_NAME $DB_TABLE" > "$OUTPUT"

if [ $? -eq 0 ]; then
  echo "[SUCCESS] Export completed to $OUTPUT"
else
  echo "[ERROR] Export failed"
fi
