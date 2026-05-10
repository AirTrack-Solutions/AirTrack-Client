# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC




import subprocess
import sys
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("logs/rebuild.log")


def log(message: str) -> None:
    """Write rebuild log entries to logs/rebuild.log and print to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {message}\n")

    print(f"{timestamp} - {message}")


def rebuild() -> None:
    """Rebuild and restart AirTrack via Docker Compose."""
    log("🔧 Rebuild started")

    try:
        # Stop running containers
        subprocess.run(["docker", "compose", "down"], check=True)

        # Rebuild and start containers
        subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            check=True
        )

        log("✅ Rebuild successful — services restarted")

    except subprocess.CalledProcessError as e:
        log(f"❌ Rebuild failed: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    rebuild()
