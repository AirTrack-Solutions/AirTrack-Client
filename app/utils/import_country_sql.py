#!/usr/bin/env python3
"""
AirTrack Country SQL Importer

Drop country SQL files into:

    app/registry_imports/inbox/

Example:

    app/registry_imports/inbox/sweden.sql

Then run:

    python3 import_country_sql.py

Rules:
- File name becomes table name.
- sweden.sql imports into table `sweden`.
- SQL is first imported into a temporary table.
- Existing live data is only overwritten when incoming data has a real value.
- NULL/blank incoming values do not erase existing live values.
- New rows are inserted.
- Existing user/manual data is preserved when incoming data is empty.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INBOX_DIR = PROJECT_ROOT / "app" / "registries" / "inbox"
PROCESSED_DIR = PROJECT_ROOT / "app" / "registries" / "processed"
FAILED_DIR = PROJECT_ROOT / "app" / "registries" / "failed"
REGISTRIES_DIR = PROJECT_ROOT / "app" / "registries"

DOCKER_CONTAINER = "airtrack-logbook-airtrack-db-1"
DB_NAME = "airtrack"
DB_USER = "SirBob"
DB_PASS = "ofAirTrack"

SAFE_TABLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

MATCH_PRIORITY = [
    "hexcode",
    "icao24",
    "registration",
    "msn",
    "serial_number",
    "serialnumber",
]

NEVER_UPDATE_COLUMNS = {
    "id",
    "created_at",
    "updated_at",
    "last_synced",
    "source_node",
    "uuid",
    "user_notes",
    "user_added",
    "user_modified",
    "manual_override",
}


def log(message: str) -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}")


def run_cmd(
    args: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def mysql_exec(sql: str, *, check: bool = True) -> subprocess.CompletedProcess:
    args = [
        "docker",
        "exec",
        "-i",
        DOCKER_CONTAINER,
        "mariadb",
        "-u",
        DB_USER,
        f"-p{DB_PASS}",
        DB_NAME,
    ]

    return run_cmd(args, input_text=sql, check=check)


def mysql_query_lines(sql: str) -> list[str]:
    args = [
        "docker",
        "exec",
        "-i",
        DOCKER_CONTAINER,
        "mariadb",
        "-u",
        DB_USER,
        f"-p{DB_PASS}",
        DB_NAME,
        "-N",
        "-B",
        "-e",
        sql,
    ]

    result = run_cmd(args)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def mysql_import_file(sql_file: Path) -> None:
    args = [
        "docker",
        "exec",
        "-i",
        DOCKER_CONTAINER,
        "mariadb",
        "-u",
        DB_USER,
        f"-p{DB_PASS}",
        DB_NAME,
    ]

    with sql_file.open("rb") as handle:
        result = subprocess.run(
            args,
            stdin=handle,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    if result.returncode != 0:
        stdout = result.stdout.decode(errors="replace")
        stderr = result.stderr.decode(errors="replace")
        raise RuntimeError(
            f"MariaDB import failed for {sql_file}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        )


def ensure_dirs() -> None:
    for folder in [INBOX_DIR, PROCESSED_DIR, FAILED_DIR, REGISTRIES_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def table_exists(table_name: str) -> bool:
    rows = mysql_query_lines(
        f"""
        SELECT COUNT(*)
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = '{table_name}';
        """
    )
    return bool(rows and rows[0] == "1")


def get_columns(table_name: str) -> list[str]:
    rows = mysql_query_lines(
        f"""
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = '{table_name}'
        ORDER BY ORDINAL_POSITION;
        """
    )
    return rows


def get_row_count(table_name: str) -> int:
    rows = mysql_query_lines(f"SELECT COUNT(*) FROM `{table_name}`;")
    return int(rows[0]) if rows else 0


def sql_identifier(name: str) -> str:
    return f"`{name}`"


def safe_table_name_from_file(sql_file: Path) -> str:
    table_name = sql_file.stem.strip().lower().replace("-", "_").replace(" ", "_")

    if not SAFE_TABLE_RE.match(table_name):
        raise ValueError(
            f"Unsafe table name derived from filename: {sql_file.name} -> {table_name}"
        )

    return table_name


def pretty_country_folder_name(table_name: str) -> str:
    return "_".join(part.capitalize() for part in table_name.split("_"))


def rewrite_sql_for_temp_table(sql_text: str, table_name: str, temp_table: str) -> str:
    """
    Rewrite CREATE TABLE and INSERT INTO statements from the live table
    to the temp table.

    Also converts INSERT INTO to INSERT IGNORE INTO so duplicate rows in
    source data do not stop the import.
    """

    def table_pattern(name: str) -> str:
        return rf"(?:`{re.escape(name)}`|{re.escape(name)})"

    target = table_pattern(table_name)
    replacement = f"`{temp_table}`"

    rewritten = sql_text

    rewritten = re.sub(
        rf"\bCREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?{target}",
        lambda m: f"CREATE TABLE {m.group(1) or ''}{replacement}",
        rewritten,
        flags=re.IGNORECASE,
    )

    rewritten = re.sub(
        rf"\bINSERT\s+INTO\s+{target}",
        f"INSERT IGNORE INTO {replacement}",
        rewritten,
        flags=re.IGNORECASE,
    )

    rewritten = re.sub(
        rf"\bREPLACE\s+INTO\s+{target}",
        f"INSERT IGNORE INTO {replacement}",
        rewritten,
        flags=re.IGNORECASE,
    )

    return rewritten


def validate_sql_targets_table(sql_text: str, table_name: str) -> None:
    pattern = re.compile(
        rf"\b(?:CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|INSERT\s+INTO|REPLACE\s+INTO)\s+`?{re.escape(table_name)}`?\b",
        flags=re.IGNORECASE,
    )

    if not pattern.search(sql_text):
        raise ValueError(
            f"{table_name}.sql does not appear to create or insert into table `{table_name}`."
        )


def create_live_table_if_missing(table_name: str, temp_table: str) -> None:
    if table_exists(table_name):
        return

    log(f"Live table `{table_name}` does not exist. Creating it from temp table.")

    mysql_exec(
        f"""
        CREATE TABLE `{table_name}` LIKE `{temp_table}`;
        """
    )

    columns = get_columns(table_name)

    if "id" not in columns:
        log(f"Adding id primary key to `{table_name}`.")

        # If table has an old primary key, drop it. Ignore failure if none exists.
        mysql_exec(
            f"""
            ALTER TABLE `{table_name}`
            DROP PRIMARY KEY;
            """,
            check=False,
        )

        mysql_exec(
            f"""
            ALTER TABLE `{table_name}`
            ADD COLUMN `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT FIRST,
            ADD PRIMARY KEY (`id`);
            """
        )

    columns = get_columns(table_name)

    if "registration" in columns:
        mysql_exec(
            f"""
            CREATE INDEX `idx_registration`
            ON `{table_name}` (`registration`);
            """,
            check=False,
        )


def build_match_condition(live_alias: str, temp_alias: str, common_columns: set[str]) -> str:
    conditions: list[str] = []

    for col in MATCH_PRIORITY:
        if col in common_columns:
            conditions.append(
                f"""
                (
                    {temp_alias}.`{col}` IS NOT NULL
                    AND TRIM(CAST({temp_alias}.`{col}` AS CHAR)) <> ''
                    AND {live_alias}.`{col}` IS NOT NULL
                    AND TRIM(CAST({live_alias}.`{col}` AS CHAR)) <> ''
                    AND UPPER(TRIM(CAST({live_alias}.`{col}` AS CHAR))) =
                        UPPER(TRIM(CAST({temp_alias}.`{col}` AS CHAR)))
                )
                """
            )

    if not conditions:
        raise RuntimeError(
            "No usable match column found. Need at least one of: "
            + ", ".join(MATCH_PRIORITY)
        )

    return " OR ".join(conditions)


def build_update_assignments(common_columns: Iterable[str]) -> str:
    assignments: list[str] = []

    for col in sorted(common_columns):
        if col in NEVER_UPDATE_COLUMNS:
            continue

        assignments.append(
            f"""
            live.`{col}` =
                CASE
                    WHEN incoming.`{col}` IS NOT NULL
                         AND TRIM(CAST(incoming.`{col}` AS CHAR)) <> ''
                    THEN incoming.`{col}`
                    ELSE live.`{col}`
                END
            """
        )

    if not assignments:
        raise RuntimeError("No updateable common columns found.")

    return ",\n".join(assignments)


def merge_temp_into_live(table_name: str, temp_table: str) -> tuple[int, int, int]:
    live_columns = get_columns(table_name)
    temp_columns = get_columns(temp_table)

    live_set = set(live_columns)
    temp_set = set(temp_columns)
    common = live_set.intersection(temp_set)

    if not common:
        raise RuntimeError(f"No common columns between `{table_name}` and `{temp_table}`.")

    match_condition = build_match_condition("live", "incoming", common)
    update_assignments = build_update_assignments(common)

    before_count = get_row_count(table_name)

    update_sql = f"""
    UPDATE `{table_name}` AS live
    JOIN `{temp_table}` AS incoming
      ON {match_condition}
    SET
      {update_assignments};
    """

    mysql_exec(update_sql)

    insert_columns = [
        col for col in live_columns
        if col in temp_set and col not in {"id"}
    ]

    if not insert_columns:
        raise RuntimeError("No insertable columns found.")

    insert_column_sql = ", ".join(f"`{col}`" for col in insert_columns)
    select_column_sql = ", ".join(f"incoming.`{col}`" for col in insert_columns)

    not_exists_condition = build_match_condition("live", "incoming", common)

    insert_sql = f"""
    INSERT INTO `{table_name}` ({insert_column_sql})
    SELECT {select_column_sql}
    FROM `{temp_table}` AS incoming
    WHERE NOT EXISTS (
        SELECT 1
        FROM `{table_name}` AS live
        WHERE {not_exists_condition}
    );
    """

    mysql_exec(insert_sql)

    after_count = get_row_count(table_name)
    temp_count = get_row_count(temp_table)
    inserted = max(after_count - before_count, 0)

    return temp_count, inserted, after_count


def archive_processed_sql(sql_file: Path, table_name: str) -> Path:
    country_folder = REGISTRIES_DIR / pretty_country_folder_name(table_name)
    country_folder.mkdir(parents=True, exist_ok=True)

    destination = country_folder / f"{table_name}.sql"
    shutil.copy2(sql_file, destination)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    processed_destination = PROCESSED_DIR / f"{table_name}_{stamp}.sql"
    shutil.move(str(sql_file), processed_destination)

    return destination


def move_to_failed(sql_file: Path, reason: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    failed_destination = FAILED_DIR / f"{sql_file.stem}_{stamp}.sql"
    shutil.move(str(sql_file), failed_destination)

    reason_file = failed_destination.with_suffix(".error.txt")
    reason_file.write_text(reason, encoding="utf-8")

    return failed_destination


def process_sql_file(sql_file: Path) -> None:
    table_name = safe_table_name_from_file(sql_file)
    temp_table = f"__import_tmp_{table_name}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    log(f"Processing {sql_file.name}")
    log(f"Target table: `{table_name}`")

    sql_text = sql_file.read_text(encoding="utf-8", errors="replace")
    validate_sql_targets_table(sql_text, table_name)

    rewritten_sql = rewrite_sql_for_temp_table(sql_text, table_name, temp_table)

    if temp_table not in rewritten_sql:
        raise RuntimeError("SQL rewrite failed. Temp table name was not found in rewritten SQL.")

    mysql_exec(f"DROP TABLE IF EXISTS `{temp_table}`;")

    temp_sql_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=f"_{table_name}_temp.sql",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(f"DROP TABLE IF EXISTS `{temp_table}`;\n")
            tmp.write(rewritten_sql)
            tmp.write("\n")
            temp_sql_path = Path(tmp.name)

        log(f"Importing into temporary table `{temp_table}`.")
        mysql_import_file(temp_sql_path)

        if not table_exists(temp_table):
            raise RuntimeError(f"Temporary table `{temp_table}` was not created.")

        create_live_table_if_missing(table_name, temp_table)

        log(f"Merging `{temp_table}` into `{table_name}`.")
        temp_rows, inserted_rows, final_rows = merge_temp_into_live(table_name, temp_table)

        archived_path = archive_processed_sql(sql_file, table_name)

        log(f"Import complete for `{table_name}`.")
        log(f"Incoming rows read: {temp_rows}")
        log(f"New rows inserted: {inserted_rows}")
        log(f"Final live row count: {final_rows}")
        log(f"SQL archived to: {archived_path}")

    finally:
        mysql_exec(f"DROP TABLE IF EXISTS `{temp_table}`;", check=False)

        if temp_sql_path and temp_sql_path.exists():
            temp_sql_path.unlink(missing_ok=True)


def main() -> int:
    ensure_dirs()

    sql_files = sorted(INBOX_DIR.glob("*.sql"))

    if not sql_files:
        log(f"No SQL files found in inbox: {INBOX_DIR}")
        return 0

    log(f"Found {len(sql_files)} SQL file(s) in inbox.")

    failures = 0

    for sql_file in sql_files:
        try:
            process_sql_file(sql_file)
            print()
        except Exception as exc:
            failures += 1
            reason = str(exc)
            log(f"FAILED: {sql_file.name}")
            log(reason)

            try:
                failed_path = move_to_failed(sql_file, reason)
                log(f"Moved failed file to: {failed_path}")
            except Exception as move_exc:
                log(f"Could not move failed file: {move_exc}")

            print()

    if failures:
        log(f"Finished with {failures} failure(s).")
        return 1

    log("All imports completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())