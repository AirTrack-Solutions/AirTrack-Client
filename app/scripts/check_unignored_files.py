# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



import fnmatch
import os

IGNORE_FILE = ".airtrackignore"
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)  # go up from /scripts/


def load_ignore_patterns():
    path = os.path.join(os.path.dirname(__file__), IGNORE_FILE)
    patterns = []
    if not os.path.exists(path):
        return patterns

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    return patterns


def is_ignored(path, patterns):
    for pattern in patterns:
        # Folder ignore patterns (ending with "/")
        if pattern.endswith("/"):
            if os.path.isdir(path) and pattern in path + "/":
                return True
            if pattern in path:
                return True

        # Match full path or basename
        if fnmatch.fnmatch(path, pattern):
            return True
        if fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    return False


def main():
    patterns = load_ignore_patterns()
    print(f"📂 Scanning {PROJECT_ROOT}")

    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Check directories and files
        for name in dirs + files:
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, PROJECT_ROOT)

            if not is_ignored(rel_path, patterns):
                print("⚠️ Not ignored:", rel_path)


if __name__ == "__main__":
    main()
