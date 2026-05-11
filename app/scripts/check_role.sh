# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

#!/bin/bash
# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


echo "Checking AirTrack container role..."

ROLE=$(docker exec airtrack-airtrack-1 printenv AIRTRACK_ROLE)

if [ "$ROLE" = "client" ]; then
  echo "✅ This unit is correctly set as a CLIENT."
elif [ "$ROLE" = "server" ]; then
  echo "🛑 This unit is set as SERVER."
else
  echo "⚠️  AIRTRACK_ROLE is not set or unknown: '$ROLE'"
fi
