# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



# utils/airtrack_updater.py
# Client-pull updater. Fetches update.json from airtracksolutions.com,
# compares hashes, downloads changed files. No git, no SSH, no rebuild.

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent.parent   # /app
LOG_DIR     = BASE_DIR / "logs"
LOG_FILE    = LOG_DIR / "updater.log"
CONFIG_FILE = BASE_DIR / "config.json"

STAGING_DIR = BASE_DIR / "static" / "updates"   # cleaned up after each update

UPDATE_BASE_URL = "https://airtracksolutions.com/updates/"
UPDATE_JSON_URL = UPDATE_BASE_URL + "update.json"
REQUEST_TIMEOUT = (10, 60)   # (connect, read) seconds

# Directories / top-level paths that must never be overwritten.
# Note: config/ is NOT blocked here — config/license.py is a deployable file.
# Sensitive data files inside config/ are blocked individually via PROTECTED_FILES.
PROTECTED = {
    "config.json",
    "database",
    "uploads",
    "backups",
    "app_data",
    "Dockerfile",
    "docker-compose.windows.yml",
    "static/updates",   # staging area — never overwrite, cleaned up post-update
}

# Individual file paths that must never be overwritten regardless of directory
PROTECTED_FILES = {
    "config/license.lic",
    "config.json",
    ".env",
    ".env.server",
    ".env.client",
    "license.lic",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR.mkdir(parents=True, exist_ok=True)

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

logger = logging.getLogger("airtrack_updater")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(_file_handler)
    logger.addHandler(logging.StreamHandler())


def _log(msg: str) -> None:
    logger.info(msg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _local_version() -> str:
    version_file = BASE_DIR / "version.py"
    try:
        for line in version_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("AIRTRACK_VERSION"):
                return line.split("=")[1].strip().strip("'\"")
    except Exception:
        pass
    return "0.0.0"


def _is_protected(rel_path: str) -> bool:
    normalized = Path(rel_path).as_posix()

    # Check exact protected file paths
    if normalized in PROTECTED_FILES:
        return True

    # Check top-level directory names and composite paths
    parts = Path(rel_path).parts
    if parts and parts[0] in PROTECTED:
        return True

    for p in PROTECTED:
        if normalized == p or normalized.startswith(p + "/"):
            return True

    return False


def _load_license_identity() -> tuple[str, str]:
    """
    Silently read name and license_id from config/license.lic.
    Returns ("UNKNOWN", "UNLICENSED") if anything fails.
    Never raises.
    """
    try:
        import json
        lic_path = BASE_DIR / "config" / "license.lic"
        if lic_path.exists():
            data = json.loads(lic_path.read_text(encoding="utf-8"))
            name = data.get("name") or "UNKNOWN"
            license_id = data.get("license_id") or "UNLICENSED"
            return name, license_id
    except Exception:
        pass
    return "UNKNOWN", "UNLICENSED"


# ---------------------------------------------------------------------------
# Staging cleanup
# ---------------------------------------------------------------------------

def cleanup_staging() -> dict[str, Any]:
    """
    Remove the static/updates staging directory if it exists.
    Called automatically after a successful update to prevent stale files
    from being mistaken for live code.

    Returns:
        {"cleaned": bool, "detail": str}
    """
    if not STAGING_DIR.exists():
        _log("🧹 No staging directory found — nothing to clean.")
        return {"cleaned": False, "detail": "No staging directory found."}

    try:
        shutil.rmtree(STAGING_DIR)
        _log(f"🧹 Staging directory removed: {STAGING_DIR}")
        return {"cleaned": True, "detail": f"Staging directory '{STAGING_DIR}' removed."}
    except Exception as e:
        _log(f"⚠️  Failed to remove staging directory: {e}")
        return {"cleaned": False, "detail": f"Failed to remove staging directory: {e}"}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def fetch_update_manifest() -> dict[str, Any]:
    """Fetch update.json from the update server. Returns parsed dict or {}."""
    try:
        r = requests.get(UPDATE_JSON_URL, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log(f"❌ Failed to fetch update.json: {e}")
        return {}


def check_for_updates() -> dict[str, Any]:
    """
    Compare local version + file hashes against remote update.json.

    Returns:
        {
            "up_to_date": bool,
            "local_version": str,
            "remote_version": str,
            "files_needing_update": [{"path": str, "hash": str}, ...],
            "error": str | None,
        }
    """
    local_ver = _local_version()
    manifest = fetch_update_manifest()

    if not manifest:
        return {
            "up_to_date": True,
            "local_version": local_ver,
            "remote_version": local_ver,
            "files_needing_update": [],
            "error": "Could not reach update server.",
        }

    remote_ver = manifest.get("version", "0.0.0")
    files: list[dict] = manifest.get("files", [])

    needs_update: list[dict] = []
    for entry in files:
        rel_path = entry.get("path", "")
        expected_hash = entry.get("hash", "")

        if _is_protected(rel_path):
            _log(f"⚠️  Skipping protected path: {rel_path}")
            continue

        full_path = BASE_DIR / rel_path
        if not full_path.exists():
            needs_update.append(entry)
            continue

        if _sha256(full_path) != expected_hash:
            needs_update.append(entry)

    return {
        "up_to_date": len(needs_update) == 0,
        "local_version": local_ver,
        "remote_version": remote_ver,
        "files_needing_update": needs_update,
        "error": None,
    }


def download_updates(files: list[dict]) -> dict[str, Any]:
    """
    Download and apply a list of files from the update server.

    Args:
        files: list of {"path": str, "hash": str}

    Returns:
        {
            "updated": [str],   # successfully updated paths
            "failed":  [str],   # paths that failed
        }
    """
    updated: list[str] = []
    failed:  list[str] = []

    for entry in files:
        rel_path = entry.get("path", "")
        expected_hash = entry.get("hash", "")

        if _is_protected(rel_path):
            _log(f"⚠️  Skipping protected path: {rel_path}")
            continue

        url = UPDATE_BASE_URL + rel_path.replace(os.sep, "/")
        full_path = BASE_DIR / rel_path

        try:
            _log(f"⬇️  Downloading: {rel_path}")
            r = requests.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()

            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(r.content)

            actual_hash = _sha256(full_path)
            if actual_hash != expected_hash:
                _log(f"⚠️  Hash mismatch after download: {rel_path} | expected={expected_hash} | actual={actual_hash}")
                failed.append(rel_path)
            else:
                _log(f"✅ Updated: {rel_path}")
                updated.append(rel_path)

        except Exception as e:
            _log(f"❌ Failed to download {rel_path}: {e}")
            failed.append(rel_path)

    return {"updated": updated, "failed": failed}


def run_full_update() -> dict[str, Any]:
    """
    Full update cycle: check → download changed files → cleanup staging → report.
    License identity is read silently from config/license.lic and stamped into
    the server-side update log. Nothing is exposed to the user.
    Returns a result dict suitable for the Flask route to return as JSON.
    """
    licensed_to, license_id = _load_license_identity()
    _log(f"🚀 Update check started | Licensed to: {licensed_to} | License ID: {license_id}")

    check = check_for_updates()
    if check.get("error") and check.get("up_to_date"):
        _log(f"❌ Update check error | Licensed to: {licensed_to} | License ID: {license_id}")
        return {
            "status": "error",
            "detail": check["error"],
            "local_version": check["local_version"],
            "remote_version": check["remote_version"],
        }

    if check["up_to_date"]:
        _log(f"✅ Already up to date | Licensed to: {licensed_to} | License ID: {license_id}")
        # Still clean up staging in case it was left over from a previous manual process
        cleanup_staging()
        return {
            "status": "ok",
            "detail": "✅ Already up to date.",
            "local_version": check["local_version"],
            "remote_version": check["remote_version"],
            "updated": [],
            "failed": [],
        }

    _log(f"📦 {len(check['files_needing_update'])} file(s) to update | Licensed to: {licensed_to} | License ID: {license_id}")
    result = download_updates(check["files_needing_update"])

    # Clean up staging directory now that files are in place
    cleanup_result = cleanup_staging()

    _log(f"🎉 Update complete | Updated: {len(result['updated'])} | Failed: {len(result['failed'])} | Licensed to: {licensed_to} | License ID: {license_id}")

    detail = f"✅ {len(result['updated'])} file(s) updated."
    if result["failed"]:
        detail += f" ⚠️ {len(result['failed'])} file(s) failed."
    if cleanup_result["cleaned"]:
        detail += " 🧹 Staging directory cleared."

    # Auto-restart gunicorn if files were updated so migrations run immediately
    if result["updated"]:
        try:
            import signal
            gunicorn_pid = int(Path("/tmp/gunicorn.pid").read_text().strip())
            os.kill(gunicorn_pid, signal.SIGHUP)
            _log("🔄 Gunicorn reload triggered after update.")
        except Exception as e:
            _log(f"⚠ Could not auto-restart: {e} — manual restart may be required.")

    return {
        "status": "ok" if not result["failed"] else "partial",
        "detail": detail,
        "local_version": check["local_version"],
        "remote_version": check["remote_version"],
        "updated": result["updated"],
        "failed": result["failed"],
        "restart_required": len(result["updated"]) > 0,
    }