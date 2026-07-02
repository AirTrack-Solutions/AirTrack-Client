#!/usr/bin/env python3
# AirTrack Client Utility
# mangy_marmot.py
#
# Client-side Registry Manager and Code Update Agent.
# Connects to Waddling Wombat for registry patches and Mrs Wombat
# for application code updates.
#
# Registry patches: applied via two-stage validation (MariaDB success
# + row-count delta check), rolls back cleanly on failure.
# Code updates: tarball delivery from Mrs Wombat, backup before apply,
# container restart via Docker SDK.
#
# Both operations run once daily at randomly chosen fixed times,
# selected on first run and persisted in marmot/daily_schedule.json.
# Registry time = code time + 12 hours, ensuring they never bunch up.
#
# Phase 1: Manifest sync + patch application + rollback + code updates.
# Phase 2: License-gated authentication, SQL Embargo compliance.
#
# Ships with AirTrack client installs. Also runs on the server in server mode
# when WOMBAT_URL is not set (manifest syncs from localhost Wombat).
#
# Runs every 5 minutes via the Woodland Scheduler.
# SAFE FOR CLIENT DISTRIBUTION.

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pymysql
from dotenv import load_dotenv

from woodland.status_writer import write_status


# =============================================================================
# CONFIG
# =============================================================================

TIMEZONE = ZoneInfo("Australia/Sydney")

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "user":     os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD", os.getenv("DB_PASS", "")),
    "database": os.getenv("DB_NAME", "airtrack"),
}

# URL of the Waddling Wombat manifest endpoint on the distribution server.
# If not set, Marmot runs in standalone/local mode — no remote sync.
WOMBAT_URL = os.getenv("WOMBAT_URL", "").rstrip("/")

# URL of Mrs Wombat on the distribution server (.201) for code updates.
# Separate from WOMBAT_URL which points to the local registry Wombat.
WOMBAT_CODE_URL = os.getenv("WOMBAT_CODE_URL", "").rstrip("/")

# AirTrack license key — sent to Wombat for authentication (Phase 2).
AIRTRACK_LICENSE = os.getenv("AIRTRACK_LICENSE_KEY", "")

WOMBAT_TIMEOUT = int(os.getenv("WOMBAT_TIMEOUT", "30"))

# Which GitHub repo to pull code updates from
CODE_REPO = os.getenv("AIRTRACK_CODE_REPO", "AirTrack-Client")

# Docker container names — used to restart after a code update
WEB_CONTAINER       = os.getenv("AIRTRACK_WEB_CONTAINER", "airtrack-logbook-airtrack-1")
SCHEDULER_CONTAINER = os.getenv("AIRTRACK_SCHEDULER_CONTAINER", "airtrack-logbook-airtrack-scheduler-1")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR      = PROJECT_ROOT / "app" / "logs"
LOG_FILE     = LOG_DIR / "mangy_marmot.log"

APP_DIR       = Path(__file__).resolve().parents[1]
REGISTRIES    = APP_DIR / "registries"

INBOX_DIR     = REGISTRIES / "inbox"        # Squirrel's inbox
PATCHES_DIR   = REGISTRIES / "patches"
INCOMING_DIR  = PATCHES_DIR / "incoming"    # Marmot watches this
APPLIED_DIR   = PATCHES_DIR / "applied"
FAILED_DIR    = PATCHES_DIR / "failed"

MARMOT_DIR      = Path(__file__).resolve().parent / "marmot"
LOCAL_MANIFEST  = MARMOT_DIR / "manifest_cache.json"
SCHEDULE_FILE   = MARMOT_DIR / "daily_schedule.json"

# Code backup directory — one previous version kept here
CODE_BACKUP_DIR = APP_DIR / "runtime" / "woodland" / "code_backups"

# Direct path to the Wombat manifest file (shared volume fallback)
_WOMBAT_MANIFEST_FILE = Path(__file__).resolve().parent / "wombat" / "manifest.json"


# =============================================================================
# LOGGING
# =============================================================================

def now_local() -> datetime:
    return datetime.now(TIMEZONE)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def timestamp() -> str:
    return now_local().strftime("%Y-%m-%d %H:%M:%S %Z")


def log(message: str) -> None:
    line = f"[{timestamp()}] {message}"
    print(line)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


# =============================================================================
# DATABASE
# =============================================================================

def _get_connection():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10,
    )


def _count_table(cursor, table_name: str) -> int | None:
    """Return row count for a table, or None if table doesn't exist."""
    try:
        cursor.execute(f"SELECT COUNT(*) AS n FROM `{table_name}`")
        row = cursor.fetchone()
        return row["n"] if row else 0
    except Exception:
        return None


# =============================================================================
# DAILY SCHEDULE
# =============================================================================

def _get_schedule() -> dict:
    """
    Load or create the daily schedule.

    On first run, picks a random code_time (HH:MM) and sets
    registry_time = code_time + 12 hours. Both are persisted and
    never changed. Also tracks last_code_check and last_registry_check
    (date strings YYYY-MM-DD) and the installed_sha for code updates.
    """
    if SCHEDULE_FILE.exists():
        try:
            return json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    hour   = random.randint(0, 23)
    minute = random.randint(0, 59)
    code_time     = f"{hour:02d}:{minute:02d}"
    registry_time = f"{(hour + 12) % 24:02d}:{minute:02d}"

    schedule = {
        "code_time":           code_time,
        "registry_time":       registry_time,
        "last_code_check":     "",
        "last_registry_check": "",
        "installed_sha":       "",
    }
    MARMOT_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULE_FILE.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    log(f"Daily schedule created — code updates: {code_time}, registry sync: {registry_time}")
    return schedule


def _save_schedule(schedule: dict) -> None:
    MARMOT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SCHEDULE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    tmp.replace(SCHEDULE_FILE)


def _is_time_to_run(target_hhmm: str, last_run_date: str) -> bool:
    """
    Return True if:
      - current local time is at or past target_hhmm today, AND
      - we haven't already run today (last_run_date != today).
    """
    now       = datetime.now(TIMEZONE)
    today_str = now.strftime("%Y-%m-%d")
    if last_run_date == today_str:
        return False
    try:
        t_hour, t_min = map(int, target_hhmm.split(":"))
    except Exception:
        return False
    target_today = now.replace(hour=t_hour, minute=t_min, second=0, microsecond=0)
    return now >= target_today


# =============================================================================
# MANIFEST SYNC (REGISTRY)
# =============================================================================

def _fetch_manifest() -> dict | None:
    """
    Fetch the Wombat manifest from the distribution server.
    Falls back to reading the manifest file directly (shared volume)
    when the HTTP endpoint is unreachable.
    """
    url = f"{WOMBAT_URL}/api/wombat/manifest"
    headers = {"User-Agent": "AirTrack-MangyMarmot/1.0"}
    if AIRTRACK_LICENSE:
        headers["X-AirTrack-License"] = AIRTRACK_LICENSE

    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=WOMBAT_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as exc:
        log(f"Manifest fetch failed: {exc.reason}")
    except json.JSONDecodeError as exc:
        log(f"Manifest JSON decode error: {exc}")
        return None
    except Exception as exc:
        log(f"Manifest fetch error: {exc}")

    # HTTP failed — fall back to reading the manifest file directly
    if _WOMBAT_MANIFEST_FILE.exists():
        try:
            data = json.loads(_WOMBAT_MANIFEST_FILE.read_text(encoding="utf-8"))
            log("Manifest loaded from local file (HTTP endpoint unreachable).")
            return data
        except Exception as exc:
            log(f"Manifest direct-file read failed: {exc}")
    return None


def _save_manifest(manifest: dict) -> None:
    MARMOT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = LOCAL_MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(LOCAL_MANIFEST)


def _check_embargo() -> str | None:
    """Check the Wombat embargo endpoint. Returns reason string if active."""
    if not WOMBAT_URL:
        return None
    url = f"{WOMBAT_URL}/api/wombat/embargo"
    try:
        with urlopen(Request(url), timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("embargo_active"):
                return data.get("reason", "No reason given")
    except Exception:
        pass
    return None


def sync_manifest(force: bool = False) -> dict | None:
    """
    Sync manifest from Wombat if force=True. Otherwise return cached copy.
    Returns loaded manifest or None.
    """
    if not WOMBAT_URL:
        log("WOMBAT_URL not configured — using local manifest only.")
        if LOCAL_MANIFEST.exists():
            try:
                return json.loads(LOCAL_MANIFEST.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    if not force:
        log("Registry sync not due yet — using cached manifest.")
        if LOCAL_MANIFEST.exists():
            try:
                return json.loads(LOCAL_MANIFEST.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    log(f"Syncing registry manifest from Wombat at {WOMBAT_URL}...")

    embargo = _check_embargo()
    if embargo:
        log(f"SQL Embargo active — {embargo}. All patch activity suspended.")
        if LOCAL_MANIFEST.exists():
            try:
                return json.loads(LOCAL_MANIFEST.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    manifest = _fetch_manifest()
    if not manifest:
        log("Manifest fetch failed — will retry next scheduled cycle.")
        return None

    if manifest.get("embargo_active"):
        log("Embargo flag set in manifest — all patch activity suspended.")
        _save_manifest(manifest)
        return manifest

    _save_manifest(manifest)
    log(
        f"Manifest synced: {manifest.get('total_registries', 0)} registries, "
        f"{manifest.get('total_records', 0):,} records."
    )
    return manifest


# =============================================================================
# CODE UPDATE
# =============================================================================

def _fetch_code_manifest() -> dict | None:
    """Fetch the code manifest from Mrs Wombat on .201."""
    if not WOMBAT_CODE_URL:
        return None
    url = f"{WOMBAT_CODE_URL}/api/wombat/code/manifest"
    try:
        with urlopen(
            Request(url, headers={"User-Agent": "AirTrack-MangyMarmot/1.0"}),
            timeout=30,
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log(f"Code manifest fetch failed: {exc}")
        return None


def _restart_containers() -> None:
    """Restart the web app and scheduler containers via Docker SDK."""
    try:
        import docker as _docker  # type: ignore
    except ImportError:
        log("docker SDK not available — cannot restart containers.")
        log("Install with: pip install docker (or add to scheduler startup pip command)")
        return

    try:
        client = _docker.DockerClient(base_url="unix:///var/run/docker.sock")
        for name in [WEB_CONTAINER, SCHEDULER_CONTAINER]:
            try:
                container = client.containers.get(name)
                log(f"Restarting {name}...")
                container.restart(timeout=10)
                log(f"  {name} restarted OK")
            except _docker.errors.NotFound:
                log(f"  Container not found: {name}")
            except Exception as exc:
                log(f"  Failed to restart {name}: {exc}")
    except Exception as exc:
        log(f"Docker client error: {exc}")


def check_code_update(schedule: dict) -> bool:
    """
    Check for a new code version from Mrs Wombat.
    Downloads tarball if available, backs up current app/, extracts update,
    restarts containers.
    Returns True if an update was applied.
    """
    if not WOMBAT_CODE_URL:
        log("WOMBAT_CODE_URL not set — code update check skipped.")
        return False

    log(f"Checking code updates from {WOMBAT_CODE_URL}...")
    manifest = _fetch_code_manifest()
    if not manifest:
        log("Code manifest unavailable — skipping.")
        return False

    repo_entry = manifest.get("repos", {}).get(CODE_REPO)
    if not repo_entry:
        log(f"No manifest entry for {CODE_REPO} — skipping.")
        return False

    latest_sha    = repo_entry.get("sha", "")
    installed_sha = schedule.get("installed_sha", "")

    if not latest_sha:
        log("No SHA in code manifest — skipping.")
        return False

    if not installed_sha:
        # First run — record current SHA without downloading (bootstrapping)
        schedule["installed_sha"] = latest_sha
        log(f"Code update bootstrapped: installed SHA set to {latest_sha[:12]} (no download)")
        return False

    if latest_sha == installed_sha:
        log(f"Code is current ({latest_sha[:12]}) — no update needed.")
        return False

    if not repo_entry.get("package_available"):
        log(f"New SHA {latest_sha[:12]} detected but no package available yet — skipping.")
        return False

    log(f"Code update available: {latest_sha[:12]} (installed: {installed_sha[:12]})")

    # Download the tarball
    pkg_filename = repo_entry.get("package_filename", "update.tar.gz")
    dl_url = f"{WOMBAT_CODE_URL}/api/wombat/code/package/{CODE_REPO}"
    tmp_dir = Path(tempfile.mkdtemp())
    tarball = tmp_dir / pkg_filename

    try:
        log(f"Downloading {pkg_filename}...")
        with urlopen(
            Request(dl_url, headers={"User-Agent": "AirTrack-MangyMarmot/1.0"}),
            timeout=120,
        ) as resp:
            tarball.write_bytes(resp.read())
        log(f"Downloaded {tarball.stat().st_size // 1024:,} KB")
    except Exception as exc:
        log(f"Download failed: {exc}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False

    # Backup current app/ (keep one previous version)
    CODE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = CODE_BACKUP_DIR / f"app_backup_{installed_sha[:12]}.tar.gz"
    try:
        log(f"Backing up current app/ → {backup_path.name}")
        with tarfile.open(backup_path, "w:gz") as tf:
            tf.add(APP_DIR, arcname="app")
        # Prune old backups — keep only the one we just made
        for old in CODE_BACKUP_DIR.glob("*.tar.gz"):
            if old != backup_path:
                old.unlink(missing_ok=True)
    except Exception as exc:
        log(f"Backup failed: {exc} — aborting update (safe).")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False

    # Extract new app/ over existing
    try:
        log("Extracting update...")
        with tarfile.open(tarball, "r:gz") as tf:
            tf.extractall(APP_DIR.parent)
        log("Extraction complete.")
    except Exception as exc:
        log(f"Extraction failed: {exc} — restoring backup.")
        try:
            with tarfile.open(backup_path, "r:gz") as tf:
                tf.extractall(APP_DIR.parent)
            log("Backup restored successfully.")
        except Exception as rex:
            log(f"Restore also failed: {rex} — manual intervention required.")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    schedule["installed_sha"] = latest_sha
    log(f"Code updated successfully to {latest_sha[:12]}")
    _restart_containers()
    return True


# =============================================================================
# PATCH PARSING
# =============================================================================

def _parse_patch_header(patch_path: Path) -> dict | None:
    """
    Parse the structured header from a patch file.
    Expected format:
        REGISTRY: spain
        VERSION: 2026-05-14
        EXPECTED_DELTA: +12 -3
        ---
        <sed commands>

    Returns a dict with registry, version, expected_adds, expected_removes, body.
    """
    try:
        content = patch_path.read_text(encoding="utf-8")
    except Exception as exc:
        log(f"Cannot read patch file {patch_path.name}: {exc}")
        return None

    lines = content.splitlines()
    header = {}
    body_start = None

    for i, line in enumerate(lines):
        if line.strip() == "---":
            body_start = i + 1
            break
        if ":" in line:
            key, _, val = line.partition(":")
            header[key.strip().upper()] = val.strip()

    if body_start is None:
        log(f"Patch {patch_path.name}: missing '---' separator.")
        return None

    required = ("REGISTRY", "VERSION", "EXPECTED_DELTA")
    for k in required:
        if k not in header:
            log(f"Patch {patch_path.name}: missing required header field '{k}'.")
            return None

    delta_raw = header["EXPECTED_DELTA"]
    try:
        parts   = delta_raw.split()
        adds    = int(parts[0].lstrip("+")) if len(parts) > 0 else 0
        removes = abs(int(parts[1])) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        log(f"Patch {patch_path.name}: cannot parse EXPECTED_DELTA '{delta_raw}'.")
        return None

    return {
        "registry":         header["REGISTRY"].lower().replace(" ", "_"),
        "version":          header["VERSION"],
        "expected_adds":    adds,
        "expected_removes": removes,
        "net_delta":        adds - removes,
        "body":             "\n".join(lines[body_start:]),
    }


# =============================================================================
# PATCH APPLICATION
# =============================================================================

def _find_registry_sql(registry: str) -> Path | None:
    """Find the canonical SQL file for a registry."""
    candidates = [
        REGISTRIES / registry / f"{registry}.sql",
        REGISTRIES / f"{registry}.sql",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _backup_sql(sql_path: Path, holding_dir: Path) -> Path | None:
    """Back up the current SQL file to holding/ before patching."""
    try:
        holding_dir.mkdir(parents=True, exist_ok=True)
        backup_name = f"{sql_path.stem}_pre_patch.sql"
        backup_path = holding_dir / backup_name
        shutil.copy2(sql_path, backup_path)
        return backup_path
    except Exception as exc:
        log(f"Backup failed: {exc}")
        return None


def _apply_sed(sed_commands: str, target_path: Path) -> tuple[bool, str]:
    """
    Apply sed commands to the target SQL file in-place.
    Returns (success, error_message).
    """
    if not sed_commands.strip():
        return True, ""

    script = target_path.with_suffix(".sed_script")
    try:
        script.write_text(sed_commands, encoding="utf-8")
        result = subprocess.run(
            ["sed", "-f", str(script), "-i", str(target_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return False, f"sed exited {result.returncode}: {result.stderr.strip()}"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "sed timed out after 60s"
    except FileNotFoundError:
        return False, "sed not available on this system"
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            script.unlink(missing_ok=True)
        except Exception:
            pass


def _drop_to_squirrel(sql_path: Path, registry: str) -> None:
    """Copy the patched SQL file into Squirrel's inbox for import."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    dest = INBOX_DIR / f"{registry}.sql"
    shutil.copy2(sql_path, dest)
    log(f"Dropped {sql_path.name} → Squirrel inbox ({dest.name})")


def _wait_for_squirrel_import(registry: str, timeout_seconds: int = 180) -> tuple[bool, str]:
    """
    Wait for Squirrel to remove the SQL from its inbox (meaning it processed it).
    Returns (success, message).
    """
    import time
    inbox_file = INBOX_DIR / f"{registry}.sql"
    waited = 0
    interval = 5

    while waited < timeout_seconds:
        if not inbox_file.exists():
            return True, f"Squirrel imported {registry} in {waited}s"
        time.sleep(interval)
        waited += interval

    return False, f"Squirrel did not process {registry}.sql within {timeout_seconds}s"


def _archive_patch(patch_path: Path, dest_dir: Path, extra_info: str = "") -> None:
    """Move a patch file to applied/ or failed/ directory."""
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_name = patch_path.name
        if extra_info:
            stem = patch_path.stem
            suffix = patch_path.suffix
            safe_info = extra_info[:30].replace(" ", "_").replace("/", "_")
            dest_name = f"{stem}_{safe_info}{suffix}"
        shutil.move(str(patch_path), str(dest_dir / dest_name))
        log(f"Patch archived to {dest_dir.name}/{dest_name}")
    except Exception as exc:
        log(f"Could not archive patch {patch_path.name}: {exc}")


def _notify_wombat(outcome: dict) -> None:
    """Report patch outcome back to Wombat (success or failure)."""
    if not WOMBAT_URL:
        return
    url = f"{WOMBAT_URL}/api/wombat/report"
    payload = json.dumps(outcome).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AirTrack-MangyMarmot/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            log(f"Wombat notified — HTTP {resp.getcode()}")
    except Exception as exc:
        log(f"Wombat notification failed: {exc}")


def _apply_patch(patch_path: Path) -> tuple[bool, str]:
    """
    Apply a single patch file. Returns (success, message).

    Full flow:
    1. Parse header
    2. Record PRE_COUNT
    3. Backup current SQL
    4. Apply sed commands to SQL
    5. Drop patched SQL into Squirrel's inbox
    6. Wait for Squirrel to import
    7. Validation Stage 1: MariaDB (check Squirrel imported cleanly)
    8. Validation Stage 2: Row count delta
    9. Success → archive, notify Wombat
    10. Failure → rollback, archive to failed/, notify Wombat
    """
    log(f"Processing patch: {patch_path.name}")

    header = _parse_patch_header(patch_path)
    if not header:
        return False, f"Could not parse patch header: {patch_path.name}"

    registry     = header["registry"]
    version      = header["version"]
    net_delta    = header["net_delta"]
    sed_commands = header["body"]

    log(f"  Registry : {registry}")
    log(f"  Version  : {version}")
    log(f"  Delta    : {net_delta:+d} (adds={header['expected_adds']}, removes={header['expected_removes']})")

    sql_path = _find_registry_sql(registry)
    if not sql_path:
        msg = f"No SQL file found for registry '{registry}'"
        log(f"  Error: {msg}")
        _archive_patch(patch_path, FAILED_DIR, "no_sql_file")
        return False, msg

    holding_dir = sql_path.parent / "holding"

    # Step 2: PRE_COUNT
    conn   = None
    cursor = None
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        pre_count = _count_table(cursor, registry)
        if pre_count is None:
            log(f"  Warning: table '{registry}' does not exist — treating as fresh install (pre_count=0)")
            pre_count = 0
        else:
            log(f"  PRE_COUNT: {pre_count:,}")
    except Exception as exc:
        msg = f"DB error getting PRE_COUNT: {exc}"
        log(f"  Error: {msg}")
        _archive_patch(patch_path, FAILED_DIR, "db_error")
        return False, msg
    finally:
        if cursor:
            try: cursor.close()
            except Exception: pass
        if conn:
            try: conn.close()
            except Exception: pass

    # Step 3: Backup current SQL
    backup_path = _backup_sql(sql_path, holding_dir)
    if not backup_path:
        msg = "Could not backup SQL file before patching"
        log(f"  Error: {msg}")
        _archive_patch(patch_path, FAILED_DIR, "backup_failed")
        return False, msg
    log(f"  Backup: {backup_path.name}")

    # Step 4: Apply sed commands
    if sed_commands.strip():
        ok, sed_error = _apply_sed(sed_commands, sql_path)
        if not ok:
            log(f"  sed failed: {sed_error}")
            shutil.copy2(backup_path, sql_path)
            log(f"  SQL restored from backup.")
            _archive_patch(patch_path, FAILED_DIR, "sed_failed")
            _notify_wombat({
                "registry":  registry,
                "version":   version,
                "outcome":   "failure",
                "stage":     "sed",
                "error":     sed_error,
                "timestamp": now_utc_iso(),
            })
            return False, f"sed failed: {sed_error}"
        log(f"  sed applied successfully.")
    else:
        log(f"  No sed commands — using SQL as-is (full replace).")

    # Steps 5+6: Drop to Squirrel and wait
    _drop_to_squirrel(sql_path, registry)
    squirrel_ok, squirrel_msg = _wait_for_squirrel_import(registry)

    if not squirrel_ok:
        log(f"  Stage 1 FAIL: {squirrel_msg}")
        shutil.copy2(backup_path, sql_path)
        _drop_to_squirrel(sql_path, registry)
        log(f"  Rollback initiated — original SQL dropped to Squirrel inbox.")
        _archive_patch(patch_path, FAILED_DIR, "squirrel_timeout")
        _notify_wombat({
            "registry":  registry,
            "version":   version,
            "outcome":   "failure",
            "stage":     "squirrel_import",
            "error":     squirrel_msg,
            "timestamp": now_utc_iso(),
        })
        return False, f"Squirrel import failed: {squirrel_msg}"

    log(f"  Stage 1 PASS: {squirrel_msg}")

    # Validation Stage 2: Row count delta
    try:
        conn   = _get_connection()
        cursor = conn.cursor()
        post_count = _count_table(cursor, registry)
        if post_count is None:
            raise ValueError(f"Table '{registry}' vanished after import")
        actual_delta = post_count - pre_count
        log(f"  POST_COUNT: {post_count:,} (actual delta: {actual_delta:+d}, expected: {net_delta:+d})")
    except Exception as exc:
        msg = f"DB error getting POST_COUNT: {exc}"
        log(f"  Error: {msg}")
        _archive_patch(patch_path, FAILED_DIR, "post_count_error")
        return False, msg
    finally:
        if cursor:
            try: cursor.close()
            except Exception: pass
        if conn:
            try: conn.close()
            except Exception: pass

    if actual_delta != net_delta:
        msg = f"Delta mismatch — expected {net_delta:+d}, got {actual_delta:+d}"
        log(f"  Stage 2 FAIL: {msg}")
        shutil.copy2(backup_path, sql_path)
        _drop_to_squirrel(sql_path, registry)
        log(f"  Rollback initiated — original SQL re-queued.")
        _archive_patch(patch_path, FAILED_DIR, "delta_mismatch")
        _notify_wombat({
            "registry":       registry,
            "version":        version,
            "outcome":        "failure",
            "stage":          "row_count",
            "error":          msg,
            "pre_count":      pre_count,
            "post_count":     post_count,
            "expected_delta": net_delta,
            "actual_delta":   actual_delta,
            "timestamp":      now_utc_iso(),
        })
        return False, msg

    # SUCCESS
    log(f"  Stage 2 PASS: delta matches ({actual_delta:+d}).")
    _archive_patch(patch_path, APPLIED_DIR)
    _notify_wombat({
        "registry":   registry,
        "version":    version,
        "outcome":    "success",
        "pre_count":  pre_count,
        "post_count": post_count,
        "delta":      actual_delta,
        "timestamp":  now_utc_iso(),
    })

    success_msg = (
        f"Patch applied: {registry} v{version} — "
        f"{actual_delta:+d} records ({post_count:,} total)"
    )
    log(f"  {success_msg}")
    return True, success_msg


# =============================================================================
# PATCH FOLDER SCAN
# =============================================================================

def scan_incoming_patches() -> tuple[int, int, list[str]]:
    """
    Scan patches/incoming/ for new patch files and process them.
    Returns (applied, failed, messages).
    """
    if not INCOMING_DIR.exists():
        INCOMING_DIR.mkdir(parents=True, exist_ok=True)
        return 0, 0, []

    patches = sorted(
        p for p in INCOMING_DIR.iterdir()
        if p.is_file() and p.suffix in (".patch", ".txt", ".sql_patch")
    )

    if not patches:
        log("No incoming patches.")
        return 0, 0, []

    log(f"Found {len(patches)} incoming patch(es).")

    applied  = 0
    failed   = 0
    messages = []

    for patch_path in patches:
        ok, msg = _apply_patch(patch_path)
        if ok:
            applied += 1
            messages.append(f"✓ {msg}")
        else:
            failed += 1
            messages.append(f"✗ {msg}")

    return applied, failed, messages


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    log("Mangy Marmot starting.")

    for d in (REGISTRIES, INBOX_DIR, INCOMING_DIR, APPLIED_DIR, FAILED_DIR, MARMOT_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    schedule = _get_schedule()
    today    = datetime.now(TIMEZONE).strftime("%Y-%m-%d")

    # ── Code update check (daily at code_time) ──────────────────────────────
    if _is_time_to_run(schedule["code_time"], schedule.get("last_code_check", "")):
        log(f"Code update window reached ({schedule['code_time']}) — checking...")
        updated = check_code_update(schedule)
        schedule["last_code_check"] = today
        _save_schedule(schedule)
        if updated:
            # Containers are restarting — write status and exit cleanly
            write_status(
                "mangy_marmot",
                f"Code updated to {schedule['installed_sha'][:12]} — containers restarting",
                status="ok",
            )
            log("Mangy Marmot finished (update applied, restart triggered).")
            return

    # ── Registry sync (daily at registry_time = code_time + 12h) ────────────
    run_registry = _is_time_to_run(schedule["registry_time"], schedule.get("last_registry_check", ""))
    manifest = sync_manifest(force=run_registry)

    if run_registry:
        schedule["last_registry_check"] = today
        _save_schedule(schedule)

    if manifest and manifest.get("embargo_active"):
        log("SQL Embargo active — patch activity suspended. Marmot standing by.")
        write_status(
            "mangy_marmot",
            "SQL Embargo active — patch delivery suspended",
            status="warning",
        )
        log("Mangy Marmot finished.")
        return

    # ── Patch scan (every 5-minute tick) ────────────────────────────────────
    applied, failed, messages = scan_incoming_patches()

    if applied == 0 and failed == 0:
        if not WOMBAT_URL:
            last_action = "Standing by — WOMBAT_URL not configured"
            status = "warning"
        else:
            last_action = "Patch inbox clear — all registries current"
            status = "ok"
    elif failed > 0:
        last_action = (
            f"{applied} patch(es) applied, {failed} failed — "
            + (messages[-1][:60] if messages else "see log")
        )
        status = "error"
    else:
        last_action = f"{applied} patch(es) applied successfully"
        status = "ok"

    log(f"Summary: {last_action}")
    write_status(
        "mangy_marmot",
        last_action[:120],
        status=status,
        last_error=messages[-1][:120] if failed > 0 and messages else None,
    )

    log("Mangy Marmot finished.")


if __name__ == "__main__":
    main()
