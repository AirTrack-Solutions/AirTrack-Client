#!/usr/bin/env python3
# AirTrack Woodland Utility
# github_gorilla.py
#
# Checks whether the running app code is behind origin/main.
# If behind, pulls the latest and notifies the operator to restart
# the container so the new code takes effect.
#
# Cron (server):  0 3 * * *  cd /path/to/app && python app/woodland/github_gorilla.py
# Cron (client):  0 3 * * *  cd /app && python app/woodland/github_gorilla.py
#
# NOTE: requires git to be available in the running environment.
# For Docker client installs, add the following to the Dockerfile:
#   RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent.parent   # /app
LOG_DIR    = BASE_DIR / "logs"
LOG_FILE   = LOG_DIR / "github_gorilla.log"
FLAG_FILE  = LOG_DIR / ".update_pending"              # touched after a successful pull

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
NTFY_URL   = f"https://ntfy.sh/{NTFY_TOPIC}" if NTFY_TOPIC else ""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR.mkdir(parents=True, exist_ok=True)

_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))

log = logging.getLogger("github_gorilla")
log.setLevel(logging.INFO)
if not log.handlers:
    log.addHandler(_handler)
    log.addHandler(logging.StreamHandler())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _notify(title: str, body: str, priority: str = "default") -> None:
    if not NTFY_URL:
        return
    try:
        requests.post(
            NTFY_URL,
            data=body.encode(),
            headers={"Title": title, "Priority": priority},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"ntfy notification failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("🦍 Github Gorilla checking for updates...")

    # ── Confirm git is available ──────────────────────────────────────────────
    if not shutil.which("git"):
        log.error(
            "❌ git not found in this environment. "
            "Add git to the Dockerfile to enable automatic updates."
        )
        return

    # ── Confirm we're inside a git repo ──────────────────────────────────────
    rc, _, _ = _run(["git", "rev-parse", "--is-inside-work-tree"])
    if rc != 0:
        log.error("❌ Not a git repository — Gorilla cannot check for updates.")
        return

    # ── Fetch from origin ─────────────────────────────────────────────────────
    log.info("Fetching from origin...")
    rc, _, err = _run(["git", "fetch", "origin"])
    if rc != 0:
        log.error(f"❌ git fetch failed: {err}")
        _notify("AirTrack — Update Check Failed", f"git fetch failed:\n{err}", priority="low")
        return

    # ── Count commits behind origin/main ─────────────────────────────────────
    rc, behind_str, _ = _run(["git", "rev-list", "--count", "HEAD..origin/main"])
    if rc != 0:
        log.error("❌ Could not compare local HEAD against origin/main.")
        return

    behind = int(behind_str or "0")

    if behind == 0:
        log.info("✅ Already up to date.")
        return

    # ── Pull the latest ───────────────────────────────────────────────────────
    log.info(f"📦 {behind} commit(s) behind origin/main — pulling...")

    rc, _, err = _run(["git", "reset", "--hard", "origin/main"])
    if rc != 0:
        log.error(f"❌ git reset --hard failed: {err}")
        _notify(
            "AirTrack — Update Failed",
            f"Could not apply update:\n{err}",
            priority="high",
        )
        return

    log.info(f"✅ {behind} commit(s) applied.")

    # ── Write flag so the app knows a restart is pending ─────────────────────
    FLAG_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")

    # ── Notify operator ───────────────────────────────────────────────────────
    _notify(
        "AirTrack Update Ready",
        (
            f"✅ {behind} update(s) pulled from GitHub.\n\n"
            "Restart the container to activate:\n"
            "  docker compose restart airtrack"
        ),
        priority="default",
    )

    log.info("🦍 Gorilla done. Restart the airtrack container to activate the update.")


if __name__ == "__main__":
    main()
