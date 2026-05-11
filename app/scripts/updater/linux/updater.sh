# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

#!/usr/bin/env bash
# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# Linux updater: uses .tar.gz + sha256, flips 'current' symlink atomically.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SELF_DIR}/../common.env"
# shellcheck disable=SC1090
source "${ENV_FILE}"

INSTALL_ROOT="${LINUX_INSTALL_ROOT}"
RELEASES_DIR="${INSTALL_ROOT}/${RELEASES_DIRNAME}"
SYMLINK_CURRENT="${INSTALL_ROOT}/${CURRENT_POINTER_NAME}"
LOG_DIR="${INSTALL_ROOT}/${LOG_DIRNAME}"

REMOTE_BASE="https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${GITHUB_BRANCH}"
REMOTE_VERSION_URL="${REMOTE_BASE}/VERSION"

mkdir -p "${RELEASES_DIR}" "${LOG_DIR}"

TS="$(date +'%Y-%m-%d_%H-%M-%S')"
LOG_FILE="${LOG_DIR}/updater_linux_${TS}.log"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "[*] Linux updater started ${TS}"

LOCAL_VERSION="0.0.0"
if [ -L "${SYMLINK_CURRENT}" ]; then
  TARGET="$(readlink -f "${SYMLINK_CURRENT}")"
  LOCAL_VERSION="$(basename "${TARGET}")"
fi
echo "[*] Local version: ${LOCAL_VERSION}"

echo "[*] Fetching remote VERSION…"
REMOTE_VERSION="$(curl -fsSL "${REMOTE_VERSION_URL}" | tr -d '[:space:]')"
[ -n "${REMOTE_VERSION}" ] || { echo "[!] Empty remote VERSION"; exit 1; }
echo "[*] Remote version: ${REMOTE_VERSION}"

# compare A vs B (semver-ish)
ver() { printf "%03d%03d%03d" ${1//./ }; }
if   [[ "$(ver "$LOCAL_VERSION")" == "$(ver "$REMOTE_VERSION")" ]]; then echo "[=] Up to date."; exit 0
elif [[ "$(ver "$LOCAL_VERSION")" >  "$(ver "$REMOTE_VERSION")" ]]; then echo "[?] Local newer; skip."; exit 0
fi

PKG="${PKG_PREFIX}-${REMOTE_VERSION}.tar.gz"
SHA="${PKG_PREFIX}-${REMOTE_VERSION}.sha256"
TMP="$(mktemp -d)"; trap 'rm -rf "${TMP}"' EXIT
echo "[*] Downloading ${PKG} + ${SHA}"
curl -fsSL -o "${TMP}/${PKG}" "${REMOTE_BASE}/releases/${PKG}"
curl -fsSL -o "${TMP}/${SHA}" "${REMOTE_BASE}/releases/${SHA}"

( cd "${TMP}" && sha256sum -c "${SHA}" )

NEW_DIR="${RELEASES_DIR}/${REMOTE_VERSION}"
mkdir -p "${NEW_DIR}"
tar -xzf "${TMP}/${PKG}" -C "${NEW_DIR}" --strip-components=1

TMP_LINK="${SYMLINK_CURRENT}.tmp"
ln -sfn "${NEW_DIR}" "${TMP_LINK}"
mv -Tf "${TMP_LINK}" "${SYMLINK_CURRENT}"
echo "[✓] current → ${NEW_DIR}"

