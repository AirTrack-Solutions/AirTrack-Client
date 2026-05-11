# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

#!/bin/bash
# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


echo "🔁 Rebuilding AirTrack at $(date)"

cd .. || exit 1

# Optional: pull latest images or clean up
# docker-compose pull

docker compose down
docker compose build
docker compose up -d

echo "✅ AirTrack rebuild complete at $(date)"
exit 0
