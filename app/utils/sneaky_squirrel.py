#!/usr/bin/env python3
"""
sneaky_squirrel.py

Moves incoming registry SQL files from registries/inbox into their registry folder,
archives older copies, imports into MariaDB, and merges safely.

Rules:
- filename.sql imports into table `filename`
- old filename.sql is moved to filename/holding/filename_YYYYmmdd_HHMMSS.sql
- target table is created if missing
- incoming data is loaded into staging first
- match by hexcode first when available
- fall back to registration
- incoming real values overwrite live values
- incoming NULL/blank values do not overwrite existing live values
- bananas are rejected
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from dotenv import load_dotenv

try:
    import pymysql
except ImportError:
    print("Missing dependency: pymysql")
    print("Install with:")
    print("  pip install pymysql python-dotenv")
    sys.exit(1)


# ----------------------------------------------------------------------
# ENVIRONMENT
# ----------------------------------------------------------------------

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

AIRTRACK_APP_DIR = Path(os.getenv("AIRTRACK_APP_DIR", "./app"))

REGISTRIES_DIR = AIRTRACK_APP_DIR / "registries"
INBOX_DIR = REGISTRIES_DIR / "inbox"
LOG_DIR = REGISTRIES_DIR / "logs"
REJECTED_DIR = REGISTRIES_DIR / "rejected"

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")


# ----------------------------------------------------------------------
# SCHEMA
# ----------------------------------------------------------------------

COLUMN_DEFINITIONS = {
    "registration":           "varchar(10) NOT NULL",
    "hexcode":                "varchar(10) DEFAULT NULL",
    "aircraftmanufacturer":   "varchar(100) DEFAULT NULL",
    "aircraftmodel":          "varchar(50) DEFAULT NULL",
    "msn":                    "varchar(50) DEFAULT NULL",
    "maxtakeoffweight":       "int(11) DEFAULT NULL",
    "enginecount":            "int(11) DEFAULT NULL",
    "enginemanufacturer":     "varchar(100) DEFAULT NULL",
    "enginetype":             "varchar(50) DEFAULT NULL",
    "enginemodel":            "varchar(50) DEFAULT NULL",
    "fueltype":               "varchar(50) DEFAULT NULL",
    "registrationtype":       "varchar(50) DEFAULT NULL",
    "registeredowner":        "varchar(150) DEFAULT NULL",
    "registeredownercountry": "varchar(50) DEFAULT NULL",
    "operatorname":           "varchar(150) DEFAULT NULL",
    "operatorcountry":        "varchar(50) DEFAULT NULL",
    "firstregistrationdate":  "date DEFAULT NULL",
    "airframe":               "varchar(100) DEFAULT NULL",
    "propmanu":               "varchar(100) DEFAULT NULL",
    "propmodel":              "varchar(50) DEFAULT NULL",
    "typecert":               "varchar(50) DEFAULT NULL",
    "countrymanu":            "varchar(50) DEFAULT NULL",
    "yearmanu":               "int(11) DEFAULT NULL",
    "monthmanu":              "int(11) DEFAULT NULL",
    "icaotypedesig":          "varchar(10) DEFAULT NULL",
}

CANONICAL_COLUMNS = [
    "registration",
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

CREATE_TABLE_SQL_TEMPLATE = """
CREATE TABLE IF NOT EXISTS `{table_name}` (
    `registration` varchar(10) NOT NULL,
    `hexcode` varchar(10) DEFAULT NULL,
    `aircraftmanufacturer` varchar(100) DEFAULT NULL,
    `aircraftmodel` varchar(50) DEFAULT NULL,
    `msn` varchar(50) DEFAULT NULL,
    `maxtakeoffweight` int(11) DEFAULT NULL,
    `enginecount` int(11) DEFAULT NULL,
    `enginemanufacturer` varchar(100) DEFAULT NULL,
    `enginetype` varchar(50) DEFAULT NULL,
    `enginemodel` varchar(50) DEFAULT NULL,
    `fueltype` varchar(50) DEFAULT NULL,
    `registrationtype` varchar(50) DEFAULT NULL,
    `registeredowner` varchar(150) DEFAULT NULL,
    `registeredownercountry` varchar(50) DEFAULT NULL,
    `operatorname` varchar(150) DEFAULT NULL,
    `operatorcountry` varchar(50) DEFAULT NULL,
    `firstregistrationdate` date DEFAULT NULL,
    `airframe` varchar(100) DEFAULT NULL,
    `propmanu` varchar(100) DEFAULT NULL,
    `propmodel` varchar(50) DEFAULT NULL,
    `typecert` varchar(50) DEFAULT NULL,
    `countrymanu` varchar(50) DEFAULT NULL,
    `yearmanu` int(11) DEFAULT NULL,
    `monthmanu` int(11) DEFAULT NULL,
    `icaotypedesig` varchar(10) DEFAULT NULL,
    PRIMARY KEY (`registration`),
    KEY `idx_hexcode` (`hexcode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


# ----------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------

def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "sneaky_squirrel.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ----------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------

def safe_table_name(name: str) -> str:
    cleaned = name.strip().lower()
    cleaned = re.sub(r"[^a-z0-9_]", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")

    if not cleaned:
        raise ValueError("Could not derive safe table name.")

    if cleaned[0].isdigit():
        cleaned = f"registry_{cleaned}"

    return cleaned


def normalize_value(value):
    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()

        if stripped == "":
            return None

        if stripped.upper() == "NULL":
            return None

        return stripped

    return value


def require_env() -> None:
    missing = []

    for name, value in {
        "DB_HOST": DB_HOST,
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASSWORD,
        "DB_NAME": DB_NAME,
    }.items():
        if value is None:
            missing.append(name)

    if missing:
        raise RuntimeError(
            "Missing required .env value(s): " + ", ".join(missing)
        )


# ----------------------------------------------------------------------
# DATABASE
# ----------------------------------------------------------------------

def connect_db():
    require_env()

    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def create_registry_table(cursor, table_name: str) -> None:
    cursor.execute(CREATE_TABLE_SQL_TEMPLATE.format(table_name=table_name))


def ensure_columns(cursor, table_name: str) -> None:
    """Add any CANONICAL_COLUMNS that are missing from an existing table."""
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`;")
    existing = {row["Field"].lower() for row in cursor.fetchall()}

    for col in CANONICAL_COLUMNS:
        if col not in existing:
            col_def = COLUMN_DEFINITIONS[col]
            cursor.execute(
                f"ALTER TABLE `{table_name}` ADD COLUMN `{col}` {col_def};"
            )
            logging.info(
                "Added missing column `%s` to table `%s`.", col, table_name
            )


def create_staging_table(cursor, staging_table: str) -> None:
    cursor.execute(f"DROP TABLE IF EXISTS `{staging_table}`;")
    cursor.execute(CREATE_TABLE_SQL_TEMPLATE.format(table_name=staging_table))


def get_existing_row(cursor, table_name: str, incoming: dict) -> Optional[dict]:
    incoming_hex = normalize_value(incoming.get("hexcode"))
    incoming_reg = normalize_value(incoming.get("registration"))

    if incoming_hex:
        cursor.execute(
            f"""
            SELECT *
            FROM `{table_name}`
            WHERE `hexcode` = %s
            LIMIT 1;
            """,
            (incoming_hex,),
        )
        row = cursor.fetchone()

        if row:
            return row

    if incoming_reg:
        cursor.execute(
            f"""
            SELECT *
            FROM `{table_name}`
            WHERE `registration` = %s
            LIMIT 1;
            """,
            (incoming_reg,),
        )
        return cursor.fetchone()

    return None


def insert_row(cursor, table_name: str, incoming: dict) -> None:
    cleaned = {col: normalize_value(incoming.get(col)) for col in CANONICAL_COLUMNS}

    if not cleaned["registration"]:
        raise ValueError("Cannot insert row without registration.")

    columns_sql = ", ".join(f"`{col}`" for col in CANONICAL_COLUMNS)
    placeholders_sql = ", ".join(["%s"] * len(CANONICAL_COLUMNS))

    cursor.execute(
        f"""
        INSERT INTO `{table_name}` ({columns_sql})
        VALUES ({placeholders_sql});
        """,
        [cleaned[col] for col in CANONICAL_COLUMNS],
    )


def update_row(cursor, table_name: str, existing: dict, incoming: dict) -> bool:
    updates = {}

    for col in CANONICAL_COLUMNS:
        if col == "registration":
            continue

        incoming_value = normalize_value(incoming.get(col))

        if incoming_value is None:
            continue

        if existing.get(col) != incoming_value:
            updates[col] = incoming_value

    if not updates:
        return False

    set_sql = ", ".join(f"`{col}` = %s" for col in updates)
    values = list(updates.values())
    values.append(existing["registration"])

    cursor.execute(
        f"""
        UPDATE `{table_name}`
        SET {set_sql}
        WHERE `registration` = %s;
        """,
        values,
    )

    return True


def merge_staging_into_live(cursor, table_name: str, staging_table: str) -> dict:
    cursor.execute(f"SELECT * FROM `{staging_table}`;")
    incoming_rows = cursor.fetchall()

    stats = {
        "incoming": len(incoming_rows),
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
    }

    for incoming in incoming_rows:
        incoming_reg = normalize_value(incoming.get("registration"))

        if not incoming_reg:
            stats["skipped"] += 1
            logging.warning("Skipping row without registration: %s", incoming)
            continue

        existing = get_existing_row(cursor, table_name, incoming)

        if existing:
            changed = update_row(cursor, table_name, existing, incoming)

            if changed:
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1
        else:
            insert_row(cursor, table_name, incoming)
            stats["inserted"] += 1

    return stats


# ----------------------------------------------------------------------
# SQL PARSING / LOADING
# ----------------------------------------------------------------------

def remove_sql_comments(sql_text: str) -> str:
    lines = []

    for line in sql_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("--"):
            continue

        if stripped.startswith("#"):
            continue

        lines.append(line)

    return "\n".join(lines)


def split_sql_statements(sql_text: str) -> List[str]:
    statements = []
    current = []

    in_single = False
    in_double = False
    escaped = False

    for char in sql_text:
        current.append(char)

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == "'" and not in_double:
            in_single = not in_single
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            continue

        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()

            if statement:
                statements.append(statement)

            current = []

    tail = "".join(current).strip()

    if tail:
        statements.append(tail)

    return statements


def rewrite_statement_for_staging(statement: str, staging_table: str) -> Optional[str]:
    stripped = statement.strip()
    upper = stripped.upper()

    skip_prefixes = (
        "CREATE TABLE",
        "DROP TABLE",
        "LOCK TABLES",
        "UNLOCK TABLES",
        "ALTER TABLE",
        "START TRANSACTION",
        "COMMIT",
        "SET ",
    )

    if not stripped:
        return None

    if upper.startswith(skip_prefixes):
        return None

    if upper.startswith("INSERT INTO") or upper.startswith("INSERT IGNORE INTO"):
        return re.sub(
            r"INSERT\s+(?:IGNORE\s+)?INTO\s+`?([a-zA-Z0-9_]+)`?",
            f"INSERT INTO `{staging_table}`",
            stripped,
            count=1,
            flags=re.IGNORECASE,
        )

    logging.warning("Skipping unsupported SQL statement: %s", stripped[:120])
    return None


def load_sql_into_staging(cursor, sql_file: Path, staging_table: str) -> int:
    raw_sql = sql_file.read_text(encoding="utf-8", errors="replace")
    cleaned_sql = remove_sql_comments(raw_sql)
    statements = split_sql_statements(cleaned_sql)

    executed = 0

    for statement in statements:
        rewritten = rewrite_statement_for_staging(statement, staging_table)

        if not rewritten:
            continue

        cursor.execute(rewritten)
        executed += 1

    return executed


# ----------------------------------------------------------------------
# FILE HANDLING
# ----------------------------------------------------------------------

def bless_file(sql_file: Path) -> bool:
    text = sql_file.read_text(encoding="utf-8", errors="replace").lower()

    if "banana" in text:
        logging.error("Rejected %s because banana was detected.", sql_file)
        return False

    if "drop database" in text:
        logging.error("Rejected %s because DROP DATABASE was detected.", sql_file)
        return False

    return True


def archive_existing_file(destination_file: Path, holding_dir: Path) -> None:
    if not destination_file.exists():
        return

    holding_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived_name = f"{destination_file.stem}_{timestamp}{destination_file.suffix}"
    archived_path = holding_dir / archived_name

    shutil.move(str(destination_file), str(archived_path))
    logging.info("Archived existing file to holding: %s", archived_path)


def find_sql_files() -> Iterable[Path]:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    for item in sorted(INBOX_DIR.iterdir()):
        if item.is_file() and item.suffix.lower() == ".sql":
            yield item


# ----------------------------------------------------------------------
# PROCESSING
# ----------------------------------------------------------------------

def import_sql_file(destination_file: Path, table_name: str) -> None:
    staging_table = f"_staging_{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    conn = connect_db()

    try:
        with conn.cursor() as cursor:
            create_registry_table(cursor, table_name)
            ensure_columns(cursor, table_name)
            create_staging_table(cursor, staging_table)

            executed = load_sql_into_staging(cursor, destination_file, staging_table)

            logging.info(
                "Executed %s INSERT statement(s) into staging table `%s`.",
                executed,
                staging_table,
            )

            stats = merge_staging_into_live(cursor, table_name, staging_table)

            cursor.execute(f"DROP TABLE IF EXISTS `{staging_table}`;")

        conn.commit()

        logging.info(
            "Import complete for `%s`: incoming=%s inserted=%s updated=%s unchanged=%s skipped=%s",
            table_name,
            stats["incoming"],
            stats["inserted"],
            stats["updated"],
            stats["unchanged"],
            stats["skipped"],
        )

    except Exception:
        conn.rollback()
        logging.exception("Import failed for %s. Database rollback completed.", destination_file)
        raise

    finally:
        conn.close()


def process_sql_file(sql_file: Path) -> None:
    folder_name = sql_file.stem
    table_name = safe_table_name(folder_name)

    destination_dir = REGISTRIES_DIR / folder_name
    holding_dir = destination_dir / "holding"
    destination_file = destination_dir / sql_file.name

    destination_dir.mkdir(parents=True, exist_ok=True)
    holding_dir.mkdir(parents=True, exist_ok=True)

    if not bless_file(sql_file):
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        rejected_path = REJECTED_DIR / sql_file.name
        shutil.move(str(sql_file), str(rejected_path))
        logging.warning("Moved rejected file to: %s", rejected_path)
        return

    archive_existing_file(destination_file, holding_dir)

    shutil.move(str(sql_file), str(destination_file))

    logging.info("Moved %s into %s", sql_file.name, destination_dir)
    logging.info("Importing into table: %s", table_name)

    import_sql_file(destination_file, table_name)


def main() -> int:
    setup_logging()

    logging.info("Sneaky squirrel started.")
    logging.info("Registries directory: %s", REGISTRIES_DIR)
    logging.info("Inbox directory: %s", INBOX_DIR)

    sql_files = list(find_sql_files())

    if not sql_files:
        logging.info("No SQL files found in inbox.")
        return 0

    for sql_file in sql_files:
        try:
            process_sql_file(sql_file)
        except Exception as exc:
            logging.error("Failed to process %s: %s", sql_file, exc)

    logging.info("Sneaky squirrel finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
