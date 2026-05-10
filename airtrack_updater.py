# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



# utils/airtrack_updater.py
# Client-pull updater. Fetches update.json from airtracksolutions.com,
# compares hashes, downloads changed files. No git, no SSH, no rebuild.

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR  = Path(__file__).resolve().parent.parent   # /app
LOG_DIR   = BASE_DIR / "logs"
LOG_FILE  = LOG_DIR / "updater.log"
CONFIG_FILE = BASE_DIR / "config.json"

UPDATE_BASE_URL  = "https://www.airtracksolutions.com/updates/"
UPDATE_JSON_URL  = UPDATE_BASE_URL + "update.json"
REQUEST_TIMEOUT  = (10, 60)   # (connect, read) seconds

# Files / directories that must never be overwritten
PROTECTED = {
    "config",
    "config.json",
    "database",
    "uploads",
    "backups",
    "license.lic",
    ".env",
    ".env.server",
    ".env.client",
    "app_data",
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
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data.get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def _is_protected(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return bool(parts and parts[0] in PROTECTED)


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
                _log(f"⚠️  Hash mismatch after download: {rel_path}")
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
    Full update cycle: check → download changed files → report.
    Returns a result dict suitable for the Flask route to return as JSON.
    """
    _log("🚀 Update check started")

    check = check_for_updates()
    if check.get("error") and check.get("up_to_date"):
        return {
            "status": "error",
            "detail": check["error"],
            "local_version": check["local_version"],
            "remote_version": check["remote_version"],
        }

    if check["up_to_date"]:
        _log("✅ Already up to date.")
        return {
            "status": "ok",
            "detail": "✅ Already up to date.",
            "local_version": check["local_version"],
            "remote_version": check["remote_version"],
            "updated": [],
            "failed": [],
        }

    _log(f"📦 {len(check['files_needing_update'])} file(s) to update")
    result = download_updates(check["files_needing_update"])

    _log(f"🎉 Update complete. Updated: {len(result['updated'])}, Failed: {len(result['failed'])}")

    detail = f"✅ {len(result['updated'])} file(s) updated."
    if result["failed"]:
        detail += f" ⚠️ {len(result['failed'])} file(s) failed."

    return {
        "status": "ok" if not result["failed"] else "partial",
        "detail": detail,
        "local_version": check["local_version"],
        "remote_version": check["remote_version"],
        "updated": result["updated"],
        "failed": result["failed"],
        "restart_required": len(result["updated"]) > 0,
    }
