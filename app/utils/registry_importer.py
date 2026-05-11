#!/usr/bin/env python3
"""
registry_importer.py
AirTrack Registry Auto-Importer

Watches app/registries/inbox/ for .sql files.
For each file found:
  - Derives table name from filename
  - Creates the country table if it doesn't exist
  - Smart-merges data:
      incoming NOT NULL  +  existing NOT NULL  →  overwrite  (incoming wins)
      incoming NOT NULL  +  existing NULL      →  insert     (incoming wins)
      incoming NULL      +  existing NOT NULL  →  leave alone (hands off)
  - Archives the old sql to country/holding/ (dated, one kept)
  - Moves new file to country folder
  - Sends ntfy notification
  - Logs everything

SERVER ONLY. Run as cron job. Do not distribute to client installs.
"""

import os
import re
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pymysql


# ============================================================
# CONFIG
# ============================================================

TIMEZONE        = ZoneInfo("Australia/Sydney")
PROJECT_ROOT    = Path(__file__).resolve().parents[2]
REGISTRIES_DIR  = PROJECT_ROOT / "app" / "registries"
INBOX_DIR       = REGISTRIES_DIR / "inbox"
LOG_DIR         = PROJECT_ROOT / "app" / "logs"
LOG_FILE        = LOG_DIR / "registry_importer.log"

NTFY_URL        = os.getenv("NTFY_URL", "http://100.73.188.9:5380/airtrack")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     3306,
    "user":     os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": "airtrack",
}

# All 24 data columns (everything except registration)
DATA_COLUMNS = [
    "hexcode",
    "aircraftmanufacturer",
    "aircraftmodel",
    "msn",
    "maxtakeoffweight",
    "enginecount",
    "enginemanufacturer",
    "enginetype",
    "enginemodel",
    "fueltype",
    "registrationtype",
    "registeredowner",
    "registeredownercountry",
    "operatorname",
    "operatorcountry",
    "firstregistrationdate",
    "airframe",
    "propmanu",
    "propmodel",
    "typecert",
    "countrymanu",
    "yearmanu",
    "monthmanu",
    "icaotypedesig",
]

COUNTRY_TABLE_DDL = """
    `registration`           VARCHAR(10)  NOT NULL PRIMARY KEY,
    `hexcode`                VARCHAR(10)  DEFAULT NULL,
    `aircraftmanufacturer`   VARCHAR(100) DEFAULT NULL,
    `aircraftmodel`          VARCHAR(50)  DEFAULT NULL,
    `msn`                    VARCHAR(50)  DEFAULT NULL,
    `maxtakeoffweight`       INT          DEFAULT NULL,
    `enginecount`            INT          DEFAULT NULL,
    `enginemanufacturer`     VARCHAR(100) DEFAULT NULL,
    `enginetype`             VARCHAR(50)  DEFAULT NULL,
    `enginemodel`            VARCHAR(50)  DEFAULT NULL,
    `fueltype`               VARCHAR(50)  DEFAULT NULL,
    `registrationtype`       VARCHAR(50)  DEFAULT NULL,
    `registeredowner`        VARCHAR(150) DEFAULT NULL,
    `registeredownercountry` VARCHAR(50)  DEFAULT NULL,
    `operatorname`           VARCHAR(150) DEFAULT NULL,
    `operatorcountry`        VARCHAR(50)  DEFAULT NULL,
    `firstregistrationdate`  DATE         DEFAULT NULL,
    `airframe`               VARCHAR(100) DEFAULT NULL,
    `propmanu`               VARCHAR(100) DEFAULT NULL,
    `propmodel`              VARCHAR(50)  DEFAULT NULL,
    `typecert`               VARCHAR(50)  DEFAULT NULL,
    `countrymanu`            VARCHAR(50)  DEFAULT NULL,
    `yearmanu`               INT          DEFAULT NULL,
    `monthmanu`              INT          DEFAULT NULL,
    `icaotypedesig`          VARCHAR(10)  DEFAULT NULL
"""


# ============================================================
# LOGGING
# ============================================================

def now_local():
    return datetime.now(TIMEZONE)


def timestamp():
    return now_local().strftime("%Y-%m-%d %H:%M:%S %Z")


def log(message):
    line = f"[{timestamp()}] {message}"
    print(line)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ============================================================
# NTFY
# ============================================================

def notify(title, message, priority="default", tags="airplane"):
    try:
        req = urllib.request.Request(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers={
                "Title":    title,
                "Priority": priority,
                "Tags":     tags,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:
        log(f"ntfy notification failed: {exc}")


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        cursorclass=pymysql.cursors.Cursor,
        autocommit=False,
    )


def ensure_table(cursor, table_name):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            {COUNTRY_TABLE_DDL}
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci
    """)


def smart_merge(conn, cursor, table_name, sql_text):
    """
    Load incoming SQL into a temporary table, then merge into the real table.

    Merge rules (per column, per row):
        incoming NOT NULL + existing NOT NULL  →  overwrite  (incoming wins)
        incoming NOT NULL + existing NULL      →  insert     (incoming wins)
        incoming NULL     + existing NOT NULL  →  leave alone
        incoming NULL     + existing NULL      →  stays NULL

    Implemented with COALESCE(incoming_value, existing_value) in the UPDATE.
    """

    temp = f"`{table_name}_import_tmp`"

    # Drop any leftover temp table from a previous crashed run
    cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS {temp}")

    # Create temp table with same schema
    cursor.execute(f"""
        CREATE TEMPORARY TABLE {temp} (
            {COUNTRY_TABLE_DDL}
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci
    """)

    # Redirect all INSERT statements to the temp table
    modified_sql = re.sub(
        rf'\bINSERT\s+(?:IGNORE\s+)?INTO\s+`?{re.escape(table_name)}`?',
        f'INSERT IGNORE INTO {temp}',
        sql_text,
        flags=re.IGNORECASE,
    )

    # Execute each INSERT into temp
    rows_to_temp = 0
    for stmt in modified_sql.split(";"):
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        if "INSERT" in stmt.upper():
            cursor.execute(stmt)
            rows_to_temp += cursor.rowcount

    log(f"  Loaded {rows_to_temp} rows into temp table.")

    # Smart UPDATE: update existing rows, incoming NULL leaves existing alone
    update_clauses = ",\n            ".join(
        f"`{table_name}`.`{col}` = COALESCE({temp}.`{col}`, `{table_name}`.`{col}`)"
        for col in DATA_COLUMNS
    )
    cursor.execute(f"""
        UPDATE `{table_name}`
        JOIN {temp} ON `{table_name}`.`registration` = {temp}.`registration`
        SET
            {update_clauses}
    """)
    updated = cursor.rowcount

    # INSERT new registrations that don't exist in the main table yet
    cursor.execute(f"""
        INSERT IGNORE INTO `{table_name}`
        SELECT * FROM {temp}
        WHERE `registration` NOT IN (
            SELECT `registration` FROM `{table_name}`
        )
    """)
    new_rows = cursor.rowcount

    # Clean up
    cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS {temp}")
    conn.commit()

    return new_rows, updated


# ============================================================
# FILE MANAGEMENT
# ============================================================

def folder_name_from_table(table_name):
    """sweden → Sweden, united_states → United_States"""
    return "_".join(word.capitalize() for word in table_name.split("_"))


def archive_existing(country_dir, sql_filename):
    """
    If a current sql file exists in the country folder:
      - Remove any existing file in holding/
      - Move current file to holding/ with a date stamp
    """
    current = country_dir / sql_filename
    if not current.exists():
        return

    holding_dir = country_dir / "holding"
    holding_dir.mkdir(parents=True, exist_ok=True)

    # Remove whatever is already in holding
    for old_file in holding_dir.glob("*.sql"):
        old_file.unlink()
        log(f"  Removed old holding file: {old_file.name}")

    # Archive current with date stamp
    date_str = now_local().strftime("%Y-%m-%d")
    stem = Path(sql_filename).stem
    dated_name = f"{stem}_{date_str}.sql"
    shutil.move(str(current), str(holding_dir / dated_name))
    log(f"  Archived previous import to holding: {dated_name}")


# ============================================================
# PROCESS ONE FILE
# ============================================================

def process_file(sql_file):
    # Derive table name from filename
    table_name = (
        sql_file.stem
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    sql_filename = f"{table_name}.sql"

    log(f"Processing {sql_file.name} → table `{table_name}`")

    sql_text = sql_file.read_text(encoding="utf-8")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure the destination table exists
        ensure_table(cursor, table_name)
        conn.commit()
        log(f"  Table `{table_name}` ready.")

        # Smart merge
        new_rows, updated = smart_merge(conn, cursor, table_name, sql_text)
        log(f"  Result: {new_rows} new registrations, {updated} rows updated.")

        # File management
        folder_name    = folder_name_from_table(table_name)
        country_dir    = REGISTRIES_DIR / folder_name
        country_dir.mkdir(parents=True, exist_ok=True)

        archive_existing(country_dir, sql_filename)

        dest = country_dir / sql_filename
        shutil.move(str(sql_file), str(dest))
        log(f"  Moved to: {dest.relative_to(PROJECT_ROOT)}")

        # Notify
        notify(
            title    = f"Registry imported: {table_name}",
            message  = f"{new_rows} new registrations added, {updated} existing records updated.",
            priority = "low",
        )

        log(f"  Done: {table_name}")

    except Exception as exc:
        log(f"  ERROR: {exc}")
        notify(
            title    = f"Registry import FAILED: {table_name}",
            message  = str(exc),
            priority = "high",
            tags     = "warning",
        )
        if conn:
            conn.rollback()
        raise

    finally:
        if conn:
            conn.close()


# ============================================================
# MAIN
# ============================================================

def main():
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    sql_files = sorted(INBOX_DIR.glob("*.sql"))

    if not sql_files:
        return

    log(f"--- Registry importer started: {len(sql_files)} file(s) in inbox ---")

    for sql_file in sql_files:
        try:
            process_file(sql_file)
        except Exception as exc:
            log(f"  Skipped {sql_file.name}: {exc}")

    log("--- Registry importer finished ---")


if __name__ == "__main__":
    main()
