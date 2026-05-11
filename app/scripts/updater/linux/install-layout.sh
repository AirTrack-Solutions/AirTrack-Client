# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

#!/usr/bin/env bash
# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

set -euo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SELF_DIR}/../common.env"
# shellcheck disable=SC1090
source "${ENV_FILE}"

INSTALL_ROOT="${LINUX_INSTALL_ROOT}"
RELEASES_DIR="${INSTALL_ROOT}/${RELEASES_DIRNAME}"
SYMLINK_CURRENT="${INSTALL_ROOT}/${CURRENT_POINTER_NAME}"
LOG_DIR="${INSTALL_ROOT}/${LOG_DIRNAME}"

mkdir -p "${RELEASES_DIR}" "${LOG_DIR}"
if [ ! -e "${SYMLINK_CURRENT}" ]; then
  ln -s "${RELEASES_DIR}" "${SYMLINK_CURRENT}"
fi

echo "Linux layout ready:"
echo "  ${INSTALL_ROOT}"
echo "  ${RELEASES_DIR}"
echo "  ${SYMLINK_CURRENT} -> (symlink)"
echo "  ${LOG_DIR}"

