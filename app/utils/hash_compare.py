# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



import hashlib
import json
import os
from pathlib import Path
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_DIR = os.path.join(APP_ROOT, "static")
UPDATE_FILE = os.path.join(STATIC_DIR, "updates", "update.json")
LOCAL_HASH_FILE = os.path.join(STATIC_DIR, "updates", "local_hashes.json")


def compute_file_hash(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def main():
    if not os.path.exists(UPDATE_FILE):
        print(f"❌ update.json not found at {UPDATE_FILE}")
        return
    if not os.path.exists(LOCAL_HASH_FILE):
        print(f"❌ local_hashes.json not found at {LOCAL_HASH_FILE}")
        return
    with open(UPDATE_FILE) as f:
        update_data = json.load(f)
    with open(LOCAL_HASH_FILE) as f:
        local_hashes = json.load(f)
    missing = []
    mismatched = []
    for entry in update_data.get("files", []):
        path = entry["path"]
        expected = entry["hash"]
        full_path = os.path.join(APP_ROOT, path)
        if not os.path.exists(full_path):
            missing.append(path)
            continue
        actual_hash = local_hashes.get(path)
        real_hash = compute_file_hash(full_path)
        if actual_hash != expected:
            mismatched.append(
                {
                    "path": path,
                    "local_hash.json": actual_hash,
                    "actual_file_hash": real_hash,
                    "expected_hash": expected,
                }
            )
    print("🔍 Hash Comparison Report")
    print("=========================\n")
    print(f"Total files in update.json: {len(update_data.get('files', []))}")
    print(f"Total entries in local_hashes.json: {len(local_hashes)}\n")
    if missing:
        print("❗ Missing files:")
        for f in missing:
            print(f"  - {f}")
        print()
    if mismatched:
        print("❗ Mismatched hashes:")
        for entry in mismatched:
            print(f"  - {entry['path']}")
            print(f"    local_hash.json : {entry['local_hash.json']}")
            print(f"    actual on disk  : {entry['actual_file_hash']}")
            print(f"    expected        : {entry['expected_hash']}")
            print()
    else:
        print("✅ All hashes match!")


if __name__ == "__main__":
    main()
