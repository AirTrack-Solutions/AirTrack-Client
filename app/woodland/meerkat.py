#!/usr/bin/env python3
# AirTrack Client Utility
# app/woodland/meerkat.py
#
# Meerkat — local caretaker for this AirTrack installation.
# Watches the health of local AirTrack services and (in later passes)
# scheduled-job outcomes, and hands a status snapshot to Mangy Marmot on
# Marmot's own 5-minute tick. Meerkat never talks to Wombat directly and
# never receives instructions from anywhere — see meerkat-local-agent-spec.md
# sections 3.4/4.3/4.8 for why. This file only observes; it does not repair.
#
# Scope of this pass (spec section 4.1 — "watching the health of local
# AirTrack services"):
#   - Flask/gunicorn responsive
#   - MariaDB reachable
#   - Disk free space
#   - Container uptime
#
# NOT yet in this file (deliberately — separate build-order steps):
#   - 4.2 scheduled-job monitoring (reads Marmot's own daily_schedule.json)
#   - 5.1/5.2 heartbeat payload assembly + four-state health model
#   - 4.3 wiring this into Marmot's tick
# Those add to this module rather than replace it; check_* functions below
# are written so later passes can import and compose them directly.
#
# SAFE FOR CLIENT DISTRIBUTION.

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pymysql
import requests
from dotenv import load_dotenv

from woodland.status_writer import write_status

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Same .env as the rest of the woodland critters (mangy_marmot.py loads the
# identical file) — Meerkat reads the same DB_* vars, no new config surface.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "user":     os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD", os.getenv("DB_PASS", "")),
    "database": os.getenv("DB_NAME", "airtrack"),
}

# Flask health check target. Meerkat itself runs inside the scheduler
# container (invoked by Marmot's tick), a different container from the one
# running gunicorn — so this is a real network hop, not a local check.
# Default matches docker-compose.client.yml's service name for the web
# container; override via env for non-standard deployments (e.g. a future
# Windows-native install with no compose networking at all).
FLASK_HEALTH_URL = os.getenv("MEERKAT_APP_HEALTH_URL", "http://airtrack:5000/")
FLASK_HEALTH_TIMEOUT = float(os.getenv("MEERKAT_APP_HEALTH_TIMEOUT", "5"))

# Docker container name for uptime — same env var Mangy Marmot already uses
# to know what to restart, so the two files agree on "the web container"
# without a second convention.
WEB_CONTAINER = os.getenv("AIRTRACK_WEB_CONTAINER", "airtrack-client-airtrack-1")

# Disk-space target. Spec section 4.1 says "disk space on AIRTRACK_HOME" —
# AIRTRACK_HOME is a Windows-service-only env var (see app.py's
# get_backup_dir()) and is normally unset on today's Linux Docker client.
# Mirrors get_backup_dir()'s own fallback logic exactly: respect
# AIRTRACK_HOME when set, otherwise fall back to this deployment's real
# persistent volume rather than the ephemeral /app bind mount.
_DISK_CHECK_FALLBACK = "/airtrack_data"

# First-run marker used only if the Docker SDK / socket isn't available
# (e.g. a genuine non-container Windows-native install down the line).
# Lets uptime degrade gracefully instead of failing outright.
_UPTIME_MARKER_FILE = Path(__file__).resolve().parent / "marmot" / "meerkat_first_seen.txt"


def _disk_check_path() -> Path:
    airtrack_home = os.getenv("AIRTRACK_HOME", "").strip()
    if airtrack_home:
        return Path(airtrack_home)
    return Path(_DISK_CHECK_FALLBACK)


# ---------------------------------------------------------------------------
# Individual checks (section 4.1)
# ---------------------------------------------------------------------------

def check_flask_responsive(
    url: str = FLASK_HEALTH_URL,
    timeout: float = FLASK_HEALTH_TIMEOUT,
) -> bool:
    """
    True if the web container answered an HTTP request within timeout with
    anything short of a server error. Connection refused, DNS failure, and
    timeouts are all "not responsive" — same as a 5xx, since a Flask process
    erroring on every request isn't meaningfully healthy either.
    """
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        return resp.status_code < 500
    except requests.RequestException:
        return False


def check_db_reachable(timeout: int = 5) -> bool:
    """
    True if a direct MariaDB connection + trivial query succeeds. Uses the
    same pymysql/DB_CONFIG pattern as mangy_marmot.py's _get_connection() —
    a lightweight direct check, not a Flask-app-context/SQLAlchemy round trip,
    since Meerkat runs in the scheduler container and has no app context to
    borrow.
    """
    conn = None
    try:
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            connect_timeout=timeout,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def check_disk_free_pct(path: Optional[Path] = None) -> float:
    """
    Free space, as a percentage, on the filesystem holding `path` (default:
    AIRTRACK_HOME if set, else this deployment's persistent data volume).
    Returns 0.0 rather than raising if the path can't be statted — a
    dependency Meerkat can't observe should read as "worst case", not crash
    the whole health check.

    One decimal place, per section 5.1's schema.
    """
    target = path or _disk_check_path()
    try:
        # Walk up to an existing ancestor — the target directory itself may
        # not exist yet on a fresh install (e.g. no data volume created).
        probe = target
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        usage = os.statvfs(probe) if hasattr(os, "statvfs") else None
        if usage is None:
            return 0.0
        free_pct = (usage.f_bavail / usage.f_blocks) * 100 if usage.f_blocks else 0.0
        return round(free_pct, 1)
    except Exception:
        return 0.0


def check_container_uptime_seconds(container_name: str = WEB_CONTAINER) -> int:
    """
    Seconds since the web container started, via Docker SDK (same lazy-import
    pattern as mangy_marmot.py's _restart_containers(), so a missing `docker`
    package degrades the same way in both files). Bounded to a 10-year sanity
    ceiling per section 5.1.

    Falls back to a locally-persisted "first seen" marker if Docker itself
    isn't reachable (no socket mounted, package missing) — this keeps the
    check meaningful on a hypothetical future non-container deployment
    instead of always reporting 0.
    """
    try:
        import docker as _docker  # type: ignore

        client = _docker.DockerClient(base_url="unix:///var/run/docker.sock")
        container = client.containers.get(container_name)
        started_at = container.attrs["State"]["StartedAt"]
        # Docker's timestamp has nanosecond precision Python can't parse
        # directly; truncate to microseconds.
        started_at = started_at.split(".")[0] + "Z" if "." in started_at else started_at
        started_dt = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        seconds = int((datetime.now(timezone.utc) - started_dt).total_seconds())
        return max(0, min(seconds, 315360000))
    except Exception:
        return _uptime_from_marker()


def _uptime_from_marker() -> int:
    """
    Degraded-mode uptime: seconds since Meerkat first ever ran on this
    install, tracked via a plain text marker file it writes itself once.
    Not a substitute for real container uptime (a restart won't reset this),
    just a graceful floor when Docker isn't available at all.
    """
    try:
        _UPTIME_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not _UPTIME_MARKER_FILE.exists():
            _UPTIME_MARKER_FILE.write_text(str(time.time()), encoding="utf-8")
            return 0
        first_seen = float(_UPTIME_MARKER_FILE.read_text(encoding="utf-8").strip())
        return max(0, min(int(time.time() - first_seen), 315360000))
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def run_health_checks() -> Dict[str, Any]:
    """
    Runs all four section-4.1 checks and returns them under the same field
    names section 5.1's heartbeat schema uses (checks.flask_responsive,
    checks.db_reachable, checks.disk_free_pct, checks.container_uptime_seconds).

    Does NOT include checks.last_scheduled_job_status /
    checks.last_scheduled_job_at — those are section 4.2 (task: read
    Marmot's scheduled-job state), added to this dict by a later pass, not
    invented here as placeholders.
    """
    return {
        "flask_responsive": check_flask_responsive(),
        "db_reachable": check_db_reachable(),
        "disk_free_pct": check_disk_free_pct(),
        "container_uptime_seconds": check_container_uptime_seconds(),
    }


def write_local_status(checks: Optional[Dict[str, Any]] = None) -> Path:
    """
    Writes Meerkat's own status file via the shared woodland status_writer
    (app/woodland/status/meerkat.json) — reusing the same atomic-write
    convention every other critter uses, rather than a bespoke one. Spec
    section 4.1 was drafted before status_writer.py became a general
    woodland convention (it was .158-only at the time); it's the right
    tool for this now.

    The "ok"/"warning"/"error" status here is a provisional, coarse mapping
    for this pass only — the real four-state health model (healthy /
    warning / attention_required / offline, section 5.2) is computed in a
    later pass and will supersede this once heartbeat assembly (5.1/5.2) is
    built. This function exists so 4.1's checks are visible on disk in the
    meantime, not as a preview of the final state machine.
    """
    checks = checks if checks is not None else run_health_checks()

    if checks["flask_responsive"] and checks["db_reachable"]:
        status = "ok"
    else:
        status = "error"

    last_action = (
        f"flask={'up' if checks['flask_responsive'] else 'DOWN'}, "
        f"db={'up' if checks['db_reachable'] else 'DOWN'}, "
        f"disk_free={checks['disk_free_pct']}%, "
        f"uptime={checks['container_uptime_seconds']}s"
    )

    return write_status(
        "meerkat",
        status=status,
        last_action=last_action,
        expected_interval_seconds=300,  # matches Marmot's 5-minute tick
        last_error=None if status == "ok" else "One or more 4.1 health checks failed.",
        extra={"checks": checks},
    )


if __name__ == "__main__":
    # Tiny manual smoke test: python meerkat.py
    result = run_health_checks()
    print(result)
    path = write_local_status(result)
    print(f"Wrote {path}")
