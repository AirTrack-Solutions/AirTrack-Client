"""
skylink_adapter.py — Gus's SkyLink NOTAM fetcher for AirTrack.

Fetches active NOTAMs from the SkyLink API (via RapidAPI) for each
configured airport, converts the response to AirTrack's canonical NOTAM
format, runs the classifier and humanizer, then upserts into the notams
table.

Environment variables (read from .env or Docker environment):
    NOTAM_API_KEY           — RapidAPI key for skylink-api.p.rapidapi.com
    NOTAM_PRIMARY_AIRPORTS  — comma-separated ICAO codes (default: YSSY,YSBK,YSRI,YWLM)
    NOTAM_HOME_ICAOS        — comma-separated 'home' airports for severity boost
                              (default: same as NOTAM_PRIMARY_AIRPORTS)
    DB_HOST, DB_USER, DB_PASS — MariaDB connection (standard AirTrack env vars)

Usage:
    # From cron or Gus scheduler:
    python -m app.modules.notams.skylink_adapter

    # Or import and call:
    from app.modules.notams.skylink_adapter import run_fetch
    result = run_fetch()
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pymysql
import requests
from dotenv import load_dotenv

from .classifier import classify_record
from .humanizer import make_detail_text, make_summary
from .models import CREATE_NOTAMS_TABLE_SQL

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "groundhog_gus.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GUS] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
    ],
)
log = logging.getLogger("groundhog_gus")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_ENV_PATH)

SKYLINK_BASE_URL = "https://skylink-api.p.rapidapi.com/notams"
SKYLINK_HOST = "skylink-api.p.rapidapi.com"

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     3306,
    "user":     os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD", os.getenv("DB_PASS")),
    "database": os.getenv("DB_NAME", "airtrack"),
}


def _get_airports() -> list[str]:
    env_val = os.getenv("NOTAM_PRIMARY_AIRPORTS", "").strip()
    if env_val:
        return [x.strip().upper() for x in env_val.split(",") if x.strip()]
    # Fall back to home_airport from app_settings
    try:
        import sqlalchemy
        from sqlalchemy import text as sa_text
        db_cfg = {k: v for k, v in _DB_CFG.items() if v}
        url = sqlalchemy.engine.URL.create("mysql+pymysql", **db_cfg)
        eng = sqlalchemy.create_engine(url, pool_pre_ping=True)
        with eng.connect() as conn:
            val = conn.execute(
                sa_text("SELECT SettingValue FROM app_settings WHERE SettingKey='home_airport' LIMIT 1")
            ).scalar()
        eng.dispose()
        if val and val.strip():
            return [val.strip().upper()]
    except Exception:
        pass
    return ["YSSY"]  # last-resort default


def _get_home_icaos() -> set[str]:
    primary = _get_airports()
    raw = os.getenv("NOTAM_HOME_ICAOS", ",".join(primary))
    return {x.strip().upper() for x in raw.split(",") if x.strip()}


# ---------------------------------------------------------------------------
# SkyLink fetch
# ---------------------------------------------------------------------------

def fetch_skylink(api_key: str, airport: str) -> list[dict]:
    """
    Call the SkyLink API for one airport.
    Returns the list of raw NOTAM dicts from the response.
    Raises requests.HTTPError on non-2xx responses.
    """
    url = f"{SKYLINK_BASE_URL}/{airport}"
    headers = {
        "x-rapidapi-host": SKYLINK_HOST,
        "x-rapidapi-key": api_key,
        "Content-Type": "application/json",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    notams = data.get("notams", [])
    log.info("SkyLink: %s → %d NOTAMs", airport, len(notams))
    return notams


# ---------------------------------------------------------------------------
# Format conversion: SkyLink → AirTrack canonical
# ---------------------------------------------------------------------------

def _parse_skylink_datetime(value: str | None) -> tuple[datetime | None, bool]:
    """
    Parse SkyLink timestamp into UTC datetime.

    Handles formats:
        YYYYMMDDHHMM        e.g. 202603230059
        YYYYMMDDHHMMxxx     e.g. 202605180000EST  (strip trailing timezone suffix)
        YYYYMMDDHHMMSS      e.g. 20260323005900
        PERM / UFN          permanent, no expiry
    Returns (datetime_or_None, is_permanent).
    """
    if not value:
        return None, True

    cleaned = value.strip().upper()

    if cleaned in ("PERM", "UFN", "PERMANENT"):
        return None, True

    # Strip trailing timezone labels (EST, UTC, AEST, etc.)
    digits_only = re.sub(r"[^0-9]", "", cleaned)

    # Try YYYYMMDDHHMM (12 digits) then YYYYMMDDHHMMSS (14 digits)
    for length, fmt in [(12, "%Y%m%d%H%M"), (14, "%Y%m%d%H%M%S")]:
        if len(digits_only) >= length:
            try:
                dt = datetime.strptime(digits_only[:length], fmt)
                return dt.replace(tzinfo=timezone.utc), False
            except ValueError:
                continue

    log.warning("Could not parse SkyLink timestamp: %r", value)
    return None, True


def _parse_skylink_notam_id(notam_id: str) -> tuple[str | None, int | None, int | None]:
    """
    Parse SkyLink notam_id like 'V136/2026' or 'A0042/26'.
    Returns (series, number, year).
    """
    # Match: one letter, 1-5 digits, slash, 2 or 4 digit year
    m = re.match(r"^([A-Z])(\d{1,5})/(\d{2,4})$", notam_id.strip().upper())
    if not m:
        return None, None, None
    series = m.group(1)
    number = int(m.group(2))
    year_raw = int(m.group(3))
    # Normalise to 2-digit year for DB consistency
    year = year_raw % 100
    return series, number, year


def _is_expired(effective_to: datetime | None, is_permanent: bool) -> bool:
    if is_permanent:
        return False
    if effective_to is None:
        return False
    return datetime.now(timezone.utc) > effective_to


def skylink_to_canonical(item: dict, home_icaos: set[str]) -> dict | None:
    """
    Convert one SkyLink NOTAM dict to AirTrack canonical record.
    Returns None if the NOTAM is clearly expired or unparseable.
    """
    notam_id_raw = (item.get("notam_id") or "").strip().upper()
    if not notam_id_raw:
        log.warning("SkyLink item missing notam_id, skipping")
        return None

    series, number, year = _parse_skylink_notam_id(notam_id_raw)

    notam_type = (item.get("type") or "N").strip().upper()
    if notam_type not in ("N", "R", "C"):
        notam_type = "N"

    location = (item.get("location") or "").strip().upper()
    body = (item.get("body") or "").strip()
    raw_text = (item.get("raw") or body).strip()

    effective_from, from_perm = _parse_skylink_datetime(item.get("effective"))
    effective_to, to_perm = _parse_skylink_datetime(item.get("expiration"))
    is_permanent = to_perm

    if effective_from is None:
        effective_from = datetime.now(timezone.utc)

    # Skip NOTAMs that have already expired
    if _is_expired(effective_to, is_permanent):
        return None

    checksum = hashlib.md5(
        f"{notam_id_raw}|{effective_from.isoformat()}".encode("utf-8")
    ).hexdigest()

    record: dict = {
        "notam_id":        notam_id_raw,
        "series":          series,
        "number":          number,
        "year":            year,
        "notam_type":      notam_type,

        # Q-line fields — SkyLink doesn't provide these; classifier uses body text
        "fir":             None,
        "q_code":          None,
        "q_subject":       None,
        "q_condition":     None,
        "q_traffic":       None,
        "q_purpose":       None,
        "q_scope":         None,
        "lower_limit_ft":  None,
        "upper_limit_ft":  None,
        "latitude":        None,
        "longitude":       None,
        "radius_nm":       None,
        "lower_limit_raw": None,
        "upper_limit_raw": None,

        "location_raw":    location,
        "primary_icao":    location or None,
        "effective_from":  effective_from,
        "effective_to":    effective_to,
        "is_permanent":    1 if is_permanent else 0,
        "schedule_raw":    None,
        "text_raw":        body,

        "category":        "other",
        "severity":        "MINOR",
        "parse_confidence": "MEDIUM",

        "status":          "active",
        "superseded_by":   None,

        "source":          "skylink",
        "raw_text":        raw_text,
        "checksum":        checksum,
    }

    # Run through classifier (uses text_raw and q_* fields)
    record = classify_record(record, home_icaos=home_icaos)

    # Attach human-readable fields (not stored in DB, used by API layer)
    record["summary"]     = make_summary(record)
    record["detail_text"] = make_detail_text(record)

    return record


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _get_connection():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset="utf8mb4",
        autocommit=False,
    )


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_NOTAMS_TABLE_SQL)
    conn.commit()


UPSERT_SQL = """
INSERT INTO notams (
    notam_id, series, number, year, notam_type,
    fir, q_code, q_subject, q_condition, q_traffic, q_purpose, q_scope,
    lower_limit_ft, upper_limit_ft, latitude, longitude, radius_nm,
    location_raw, effective_from, effective_to, is_permanent, schedule_raw,
    text_raw, lower_limit_raw, upper_limit_raw,
    category, severity, parse_confidence,
    status, superseded_by, primary_icao,
    source, raw_text, checksum
) VALUES (
    %(notam_id)s, %(series)s, %(number)s, %(year)s, %(notam_type)s,
    %(fir)s, %(q_code)s, %(q_subject)s, %(q_condition)s, %(q_traffic)s,
    %(q_purpose)s, %(q_scope)s,
    %(lower_limit_ft)s, %(upper_limit_ft)s, %(latitude)s, %(longitude)s, %(radius_nm)s,
    %(location_raw)s, %(effective_from)s, %(effective_to)s, %(is_permanent)s, %(schedule_raw)s,
    %(text_raw)s, %(lower_limit_raw)s, %(upper_limit_raw)s,
    %(category)s, %(severity)s, %(parse_confidence)s,
    %(status)s, %(superseded_by)s, %(primary_icao)s,
    %(source)s, %(raw_text)s, %(checksum)s
)
ON DUPLICATE KEY UPDATE
    effective_to      = VALUES(effective_to),
    status            = VALUES(status),
    text_raw          = VALUES(text_raw),
    category          = VALUES(category),
    severity          = VALUES(severity),
    updated_at        = CURRENT_TIMESTAMP
"""


def upsert_notams(conn, records: list[dict]) -> tuple[int, int]:
    """
    Upsert a list of canonical NOTAM records.
    Returns (inserted, updated) counts.
    """
    inserted = updated = 0
    with conn.cursor() as cur:
        for rec in records:
            # Strip non-DB fields before insert
            db_rec = {k: v for k, v in rec.items()
                      if k not in ("summary", "detail_text", "active_now", "_parse_errors")}
            cur.execute(UPSERT_SQL, db_rec)
            if cur.rowcount == 1:
                inserted += 1
            elif cur.rowcount == 2:
                # MySQL ON DUPLICATE KEY UPDATE returns 2 for actual updates
                updated += 1
    conn.commit()
    return inserted, updated


def expire_old_notams(conn) -> int:
    """
    Mark NOTAMs whose effective_to has passed as expired.
    Returns count of rows updated.
    """
    sql = """
        UPDATE notams
        SET status = 'expired'
        WHERE status = 'active'
          AND is_permanent = 0
          AND effective_to IS NOT NULL
          AND effective_to < UTC_TIMESTAMP()
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        count = cur.rowcount
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_fetch(airports: list[str] | None = None) -> dict:
    """
    Full fetch-convert-store cycle.

    Returns a summary dict:
        fetched, skipped_expired, inserted, updated, errors, airports
    """
    api_key = os.getenv("NOTAM_API_KEY")
    if not api_key:
        log.error("NOTAM_API_KEY not set — Gus cannot fetch")
        return {"error": "NOTAM_API_KEY not configured"}

    target_airports = airports or _get_airports()
    home_icaos = _get_home_icaos()

    totals = {
        "airports":        target_airports,
        "fetched":         0,
        "skipped_expired": 0,
        "inserted":        0,
        "updated":         0,
        "errors":          [],
    }

    try:
        conn = _get_connection()
    except Exception as exc:
        log.error("DB connection failed: %s", exc)
        totals["errors"].append(f"DB: {exc}")
        return totals

    try:
        _ensure_table(conn)

        for airport in target_airports:
            try:
                raw_items = fetch_skylink(api_key, airport)
            except Exception as exc:
                msg = f"{airport}: SkyLink fetch failed — {exc}"
                log.error(msg)
                totals["errors"].append(msg)
                continue

            records = []
            for item in raw_items:
                totals["fetched"] += 1
                canonical = skylink_to_canonical(item, home_icaos)
                if canonical is None:
                    totals["skipped_expired"] += 1
                    continue
                records.append(canonical)

            if records:
                ins, upd = upsert_notams(conn, records)
                totals["inserted"] += ins
                totals["updated"]  += upd
                log.info("%s: %d inserted, %d updated", airport, ins, upd)

        expired = expire_old_notams(conn)
        if expired:
            log.info("Expired %d old NOTAMs", expired)
        totals["expired_cleaned"] = expired

    finally:
        conn.close()

    log.info(
        "Gus run complete — fetched=%d inserted=%d updated=%d skipped=%d errors=%d",
        totals["fetched"], totals["inserted"], totals["updated"],
        totals["skipped_expired"], len(totals["errors"]),
    )

    # Write critter status JSON for kiosk display
    try:
        from woodland.status_writer import write_status
        all_airports = _get_airports()
        ap_label = ", ".join(target_airports)
        has_errors = bool(totals["errors"])
        action = f"Fetched NOTAMs for {ap_label} — {totals['inserted']} new, {totals['updated']} updated"
        write_status(
            "groundhog_gus",
            last_action=action,
            status="error" if has_errors else "ok",
            last_error="; ".join(totals["errors"]) if has_errors else None,
        )
    except Exception as exc:
        log.warning("Could not write critter status: %s", exc)

    return totals


if __name__ == "__main__":
    result = run_fetch()
    print(result)
