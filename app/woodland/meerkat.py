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
# Scope covered so far (spec sections 4.1, 4.2, 5.1, 5.2):
#   4.1 — Flask/gunicorn responsive, MariaDB reachable, disk free space,
#         container uptime.
#   4.2 — last scheduled-job outcome, read from Marmot's own status file
#         rather than re-implemented here (see check_last_scheduled_job()
#         for why that's mangy_marmot.json, not daily_schedule.json as the
#         spec text originally named).
#   5.1 — full heartbeat payload assembly (assemble_heartbeat_payload()):
#         schema_version, identity fields sourced from the existing
#         modules/meerkat/meerkat_client.py registration state (not
#         reinvented here), sequence_number, timestamp, meerkat_version,
#         state/state_reason, and the six checks.* fields above.
#   5.2 — four-state health model (compute_health_state()): healthy /
#         warning / attention_required / offline, computed deterministically
#         from the 4.1/4.2 checks per the locked thresholds (disk warning
#         15% free, disk critical 5% free, job-failure repetition 3
#         consecutive failures).
#   4.3 — is_meerkat_enabled() is the consent gate mangy_marmot.py's
#         _send_meerkat_heartbeat() reads before calling anything else in
#         this file. This module still only assembles and observes; the
#         actual send/wiring lives in mangy_marmot.py, which imports this
#         module, never the other way around.
#
# NOT yet in this file (deliberately — separate build-order steps):
#   - 3.4/4.4 local event bus (health_warning/recovery_notice on state
#     transitions) — a separate concern from the heartbeat itself (5.2)
# Those add to this module rather than replace it; check_*/assemble_*
# functions below are written so later passes can import and compose them
# directly.
#
# SAFE FOR CLIENT DISTRIBUTION.

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pymysql
import requests
from dotenv import load_dotenv

from woodland.status_writer import DEFAULT_STATUS_DIR, write_status

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

# Marmot's own status file — see check_last_scheduled_job()'s docstring for
# why this is the right source for section 4.2, not marmot/daily_schedule.json.
MARMOT_STATUS_FILE = DEFAULT_STATUS_DIR / "mangy_marmot.json"

# ---------------------------------------------------------------------------
# Config — sections 5.1/5.2 (heartbeat payload + health-state model)
# ---------------------------------------------------------------------------
# Fixed per section 5.1 — bump only if the payload shape itself changes.
HEARTBEAT_SCHEMA_VERSION = 1

# Thresholds locked by section 5.2 ("confirmed by Trevor/Bob, 2026-07-11") —
# parameters, not architecture, but not this module's to silently retune.
DISK_WARNING_PCT = 15.0
DISK_CRITICAL_PCT = 5.0
JOB_FAILURE_REPETITION_THRESHOLD = 3

# The Meerkat *module's* own version (app/modules/meerkat/module.json),
# distinct from AIRTRACK_VERSION (version.py) — section 5.1 asks for "the
# Meerkat build that produced this snapshot", not the whole app's version.
MEERKAT_MODULE_JSON = Path(__file__).resolve().parents[1] / "modules" / "meerkat" / "module.json"


def _disk_check_path() -> Path:
    airtrack_home = os.getenv("AIRTRACK_HOME", "").strip()
    if airtrack_home:
        return Path(airtrack_home)
    return Path(_DISK_CHECK_FALLBACK)


# ---------------------------------------------------------------------------
# Individual checks (sections 4.1 and 4.2)
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


def check_last_scheduled_job() -> Dict[str, Any]:
    """
    Reads Marmot's own last-run outcome for section 4.2 ("monitoring whether
    scheduled jobs run correctly ... Meerkat observes, it doesn't
    re-implement").

    Deliberate deviation from the spec's literal file reference: section 4.2
    names marmot/daily_schedule.json as the source. That file only tracks
    *scheduling* state for Marmot's two once-daily windows (code_time,
    registry_time, and the date each was last checked) — it has no
    success/failure verdict in it at all. What Marmot actually writes on
    every 5-minute tick (the real "scheduled job" a heartbeat cares about)
    is its own status file, app/woodland/status/mangy_marmot.json, via the
    same status_writer.write_status() convention Meerkat itself uses. That
    file is Marmot's own state in every meaningful sense the spec intends —
    reading it observes Marmot's last outcome without duplicating any of
    Marmot's logic, and without inventing a success/failure signal
    daily_schedule.json was never designed to hold. (This mismatch is a
    case of the spec text predating status_writer.py's generalisation
    across woodland critters, same as 4.1's own status-file note.)

    Returns section 5.1's two job fields directly:
      - last_scheduled_job_status: "success" | "failure" | "unknown"
        ("unknown" only when Marmot has never ticked on this install yet —
        no status file written at all)
      - last_scheduled_job_at: ISO 8601 UTC string, or None when unknown

    Marmot's own "warning" status (e.g. SQL Embargo active, WOMBAT_URL not
    configured) maps to "success" here — those are expected operating
    states Marmot reports honestly, not evidence the job itself failed.
    Only Marmot's "error" status (patch application failed) maps to
    "failure".
    """
    if not MARMOT_STATUS_FILE.exists():
        return {"last_scheduled_job_status": "unknown", "last_scheduled_job_at": None}

    try:
        data = json.loads(MARMOT_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        # File exists but couldn't be read/parsed — treat as unknown rather
        # than guessing a verdict from a status file Meerkat can't trust.
        return {"last_scheduled_job_status": "unknown", "last_scheduled_job_at": None}

    marmot_status = str(data.get("status", "")).lower()
    job_status = "failure" if marmot_status == "error" else "success" if marmot_status else "unknown"

    last_run = data.get("last_run")
    job_at: Optional[str] = None
    if last_run:
        try:
            # status_writer writes local-tz-aware isoformat (e.g.
            # "...+10:00"); the heartbeat schema wants UTC.
            parsed = datetime.fromisoformat(last_run)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            job_at = parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        except Exception:
            job_at = None

    if job_status == "unknown":
        job_at = None

    return {"last_scheduled_job_status": job_status, "last_scheduled_job_at": job_at}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def run_health_checks() -> Dict[str, Any]:
    """
    Runs the section-4.1 checks plus 4.2's job-status read and returns them
    under the same field names section 5.1's heartbeat schema uses:
    checks.flask_responsive, checks.db_reachable, checks.disk_free_pct,
    checks.container_uptime_seconds, checks.last_scheduled_job_status,
    checks.last_scheduled_job_at.
    """
    checks: Dict[str, Any] = {
        "flask_responsive": check_flask_responsive(),
        "db_reachable": check_db_reachable(),
        "disk_free_pct": check_disk_free_pct(),
        "container_uptime_seconds": check_container_uptime_seconds(),
    }
    checks.update(check_last_scheduled_job())
    return checks


def write_local_status(checks: Optional[Dict[str, Any]] = None) -> Path:
    """
    Writes Meerkat's own status file via the shared woodland status_writer
    (app/woodland/status/meerkat.json) — reusing the same atomic-write
    convention every other critter uses, rather than a bespoke one. Spec
    section 4.1 was drafted before status_writer.py became a general
    woodland convention (it was .158-only at the time); it's the right
    tool for this now.

    The "ok"/"warning"/"error" status here is a deliberately coarse,
    Marmot-style mapping for this local status file only — it is not the
    section 5.2 four-state model. That model (healthy / warning /
    attention_required / offline) is what actually goes out on the
    heartbeat; see compute_health_state() and assemble_heartbeat_payload()
    below. Keeping this file's own status field simple (ok/error, matching
    every other woodland critter's status_writer convention) avoids two
    competing state vocabularies on disk for the same install.
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
        f"uptime={checks['container_uptime_seconds']}s, "
        f"last_job={checks['last_scheduled_job_status']}"
        + (f"@{checks['last_scheduled_job_at']}" if checks["last_scheduled_job_at"] else "")
    )

    return write_status(
        "meerkat",
        status=status,
        last_action=last_action,
        expected_interval_seconds=300,  # matches Marmot's 5-minute tick
        last_error=None if status == "ok" else "One or more 4.1 health checks failed.",
        extra={"checks": checks},
    )


# ---------------------------------------------------------------------------
# Identity fields (section 5.1) — reused from modules/meerkat, not reinvented
# ---------------------------------------------------------------------------
# meerkat_id/customer_id/license_id are already established, working
# concepts owned by app/modules/meerkat/meerkat_client.py (the opt-in
# consent/registration UI module) — that's section 2's existing
# register()/deregister() flow. Meerkat's own woodland caretaker (this
# file) reuses that identity rather than minting a second one; only
# get_or_create_meerkat_id() (a public function, not underscore-prefixed)
# is imported directly. customer_id/license_id are re-read the same way
# meerkat_client.py itself reads them (env var / config.license), rather
# than importing that module's private helpers across a package boundary.

def _get_meerkat_id() -> str:
    """
    This install's stable meerkat_id, from modules/meerkat's own state
    file (creating it if this is the very first time anything on this
    install has asked for it). Lazily imported — a missing/unimportable
    modules.meerkat package shouldn't crash Meerkat's own health reporting,
    it should just report an empty identity field for Wombat to reject
    per section 6's validation rule, same failure mode as any other
    packet with a missing required field.
    """
    try:
        from modules.meerkat.meerkat_client import get_or_create_meerkat_id

        return get_or_create_meerkat_id()
    except Exception:
        return ""


def _get_customer_id() -> str:
    """Same env var meerkat_client.py's register() reads — no second convention."""
    return os.environ.get("AIRTRACK_CUSTOMER_ID", "")


def _get_license_id() -> str:
    """Same config.license.load_license() path meerkat_client.py's register() uses."""
    try:
        from config.license import load_license

        return load_license().license_id
    except Exception:
        return ""


def _get_meerkat_version() -> str:
    """
    The Meerkat *module's* own version (modules/meerkat/module.json's
    "version" field) — this is "the Meerkat build that produced this
    snapshot" per section 5.1, not AIRTRACK_VERSION (version.py), which
    versions the whole client app and would conflate the two.
    """
    try:
        data = json.loads(MEERKAT_MODULE_JSON.read_text(encoding="utf-8"))
        return str(data.get("version", "0.0.0"))
    except Exception:
        return "0.0.0"


def is_meerkat_enabled() -> bool:
    """
    Whether this install has actually opted in to Meerkat. The sole,
    authoritative record is modules/meerkat/module.json's own "enabled"
    field -- the same field routes/admin_routes.py's modules_toggle() and
    modules_consent() routes read and atomically rewrite (tempfile +
    .replace()). There is no separate DB-backed toggle; module.json *is*
    the opt-in state.

    Read fresh on every call rather than cached: enabling/disabling
    happens via the admin UI, in a different process (gunicorn) from
    wherever Marmot's scheduler tick calls this, so a cached value could
    go stale for up to 5 minutes after an opt-out.

    Fails closed. Any error (missing file, unreadable/malformed JSON,
    missing key) returns False. This is a consent boundary (section 7's
    promise that nothing leaves an opted-out install) -- "can't confirm
    enabled" must mean "don't send", never "send anyway".
    """
    try:
        data = json.loads(MEERKAT_MODULE_JSON.read_text(encoding="utf-8"))
        return bool(data.get("enabled", False))
    except Exception:
        return False


def _next_sequence_number() -> int:
    """
    Monotonically increasing per-install counter for section 5.1's
    sequence_number, persisted in the same state.json meerkat_id already
    lives in (app/modules/meerkat/state.json) — sequence_number and
    meerkat_id are both properties of "this registered install", so tying
    their storage together means they naturally reset together too.

    Honest caveat on "resets only on reinstall/re-register" (5.1's own
    words): in today's codebase, re-registering via the admin toggle
    (meerkat_client.register()) does NOT regenerate meerkat_id — it's
    read from state.json if already present. So in practice this only
    resets on a genuine reinstall (state.json wiped, e.g. a fresh data
    volume), matching meerkat_id's own actual reset behaviour rather than
    the spec's slightly broader phrase. Flagged here rather than silently
    assumed.

    Side-effecting: increments and persists on every call. Callers should
    only call this once per real heartbeat assembly (assemble_heartbeat_payload()
    below), never from a health-check probe that isn't actually being sent.
    """
    from modules.meerkat.meerkat_client import STATE_FILE

    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    except Exception:
        state = {}

    next_seq = int(state.get("sequence_number", 0)) + 1
    state["sequence_number"] = next_seq

    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(STATE_FILE)
    except Exception:
        # Persisting the counter failed (e.g. read-only filesystem) — still
        # return the computed value for this one payload rather than
        # blocking heartbeat assembly over it. The next call will simply
        # recompute from the same last-persisted (or absent) value.
        pass

    return next_seq


def _read_marmot_consecutive_failures() -> int:
    """
    Marmot's own consecutive_failures counter from mangy_marmot.json (the
    same file check_last_scheduled_job() reads) — this is exactly section
    5.2's "job-failure repetition threshold" input: how many scheduled-job
    ticks in a row have failed. Not part of the heartbeat wire schema
    itself (5.1 only asks for status/at), used internally by
    compute_health_state() to decide Warning vs. Attention Required.
    """
    if not MARMOT_STATUS_FILE.exists():
        return 0
    try:
        data = json.loads(MARMOT_STATUS_FILE.read_text(encoding="utf-8"))
        return int(data.get("consecutive_failures", 0))
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Health-state model (section 5.2)
# ---------------------------------------------------------------------------

def compute_health_state(
    checks: Dict[str, Any],
    consecutive_job_failures: Optional[int] = None,
) -> Dict[str, Optional[str]]:
    """
    Computes section 5.2's four-state model deterministically from the
    4.1/4.2 checks — never inferred, never guessed. Returns
    {"state": ..., "state_reason": ...} ready to merge straight into the
    5.1 heartbeat payload.

    State priority follows 5.2's own definitions in the order they're
    written: Warning's and Attention Required's definitions both open
    with "flask_responsive and db_reachable both true" — so a dependency
    outage always wins as Offline, checked first, never overridden by a
    disk or job condition on the same tick.

    Within Attention Required and Warning, 5.2 phrases the disk and
    job-repetition conditions as independent "either/or" triggers, but
    doesn't say which one becomes state_reason when both are true on the
    same tick. This implementation checks disk before job-repetition in
    both bands — disk is the more actionable, faster-moving signal an
    operator would check first — but that ordering is this module's own
    tie-break, not something 5.2 mandates.

    state_reason is 5.1's "fixed set derived from checks" — the schema
    text doesn't spell out the literal enum strings, so they're defined
    here: flask_unresponsive, db_unreachable, disk_critical,
    job_failure_repeated, disk_low, job_failing, or None (healthy only).

    consecutive_job_failures defaults to reading Marmot's own counter
    (_read_marmot_consecutive_failures()) if not passed explicitly —
    exposed as a parameter mainly so callers/tests can pin a value
    without needing a real mangy_marmot.json on disk.
    """
    if consecutive_job_failures is None:
        consecutive_job_failures = _read_marmot_consecutive_failures()

    flask_ok = bool(checks["flask_responsive"])
    db_ok = bool(checks["db_reachable"])
    disk_pct = float(checks["disk_free_pct"])
    job_status = checks["last_scheduled_job_status"]
    job_failed = job_status == "failure"
    job_repeat_breach = job_failed and consecutive_job_failures >= JOB_FAILURE_REPETITION_THRESHOLD

    # Offline (self-reported) — 4.1's own dependencies, checked first.
    if not flask_ok:
        return {"state": "offline", "state_reason": "flask_unresponsive"}
    if not db_ok:
        return {"state": "offline", "state_reason": "db_unreachable"}

    # Attention Required.
    if disk_pct < DISK_CRITICAL_PCT:
        return {"state": "attention_required", "state_reason": "disk_critical"}
    if job_repeat_breach:
        return {"state": "attention_required", "state_reason": "job_failure_repeated"}

    # Warning.
    if disk_pct < DISK_WARNING_PCT:
        return {"state": "warning", "state_reason": "disk_low"}
    if job_failed:
        return {"state": "warning", "state_reason": "job_failing"}

    # Healthy — flask/db up, disk at or above the warning threshold, and
    # last_scheduled_job_status is "success" or "unknown" (per 5.2).
    return {"state": "healthy", "state_reason": None}


# ---------------------------------------------------------------------------
# Heartbeat payload assembly (section 5.1)
# ---------------------------------------------------------------------------

def assemble_heartbeat_payload(checks: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Builds the full, exact-shape heartbeat payload section 5.1 defines —
    every field fixed and required, nothing optional or free-form (per
    section 6's "exact shape" acceptance rule). This is what 4.3's tick
    handoff to Marmot will eventually pass along; this function only
    assembles it; it does not send anything anywhere.

    checks.* fields are nested here under a "checks" object rather than
    written with the table's dotted field names literally — 5.1's schema
    table lists paths like "checks.flask_responsive" to describe nested
    JSON, not flat keys with dots in them, consistent with how the
    envelope in section 6.1 nests fields.

    Calling this performs one real side effect: it advances the persisted
    sequence_number (_next_sequence_number()). Call it once per genuine
    heartbeat, not speculatively.
    """
    checks = checks if checks is not None else run_health_checks()
    health = compute_health_state(checks)

    return {
        "schema_version": HEARTBEAT_SCHEMA_VERSION,
        "meerkat_id": _get_meerkat_id(),
        "customer_id": _get_customer_id(),
        "license_id": _get_license_id(),
        "sequence_number": _next_sequence_number(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "meerkat_version": _get_meerkat_version(),
        "state": health["state"],
        "state_reason": health["state_reason"],
        "checks": {
            "flask_responsive": checks["flask_responsive"],
            "db_reachable": checks["db_reachable"],
            "disk_free_pct": checks["disk_free_pct"],
            "container_uptime_seconds": checks["container_uptime_seconds"],
            "last_scheduled_job_status": checks["last_scheduled_job_status"],
            "last_scheduled_job_at": checks["last_scheduled_job_at"],
        },
    }


if __name__ == "__main__":
    # Tiny manual smoke test: python meerkat.py
    result = run_health_checks()
    print(result)
    path = write_local_status(result)
    print(f"Wrote {path}")
    print(assemble_heartbeat_payload(result))
