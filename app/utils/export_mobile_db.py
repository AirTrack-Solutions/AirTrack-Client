# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



import os
import sqlite3
import mariadb
import decimal
from pathlib import Path


# ============================================================================
#  Dynamic Export Directory (Safe for Docker + Local Audit)
# ============================================================================

def _detect_export_dir() -> Path:
    # On Windows (AIRTRACK_HOME set by service.py), use AIRTRACK_HOME/exports
    airtrack_home = os.getenv("AIRTRACK_HOME", "").strip()
    if airtrack_home:
        return Path(airtrack_home) / "exports"

    # Docker: /app/export if writable
    container_path = Path('/app/export')
    if container_path.exists() and os.access(container_path, os.W_OK):
        return container_path

    return Path(__file__).resolve().parent / 'mobile_exports'


EXPORT_DIR = _detect_export_dir()
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

EXPORT_DB = EXPORT_DIR / 'airtrack_mobile.db'


# ============================================================================
#  MySQL Configuration (reads from env — works on both server and client)
# ============================================================================

def _mysql_config() -> dict:
    host = os.getenv("DB_HOST", "airtrack-db")
    # DB_HOST may include port as "host:port" — split if needed
    if ":" in host:
        host, _, port_str = host.partition(":")
    else:
        port_str = os.getenv("DB_PORT", "3306")
    return {
        "host": host,
        "user": os.getenv("DB_USER", "SirBob"),
        "password": os.getenv("DB_PASSWORD", "ofAirTrack"),
        "database": os.getenv("DB_NAME", "airtrack"),
        "port": int(port_str),
    }


MYSQL_CONFIG = _mysql_config()


# ============================================================================
#  Tables Included in Mobile Export
# ============================================================================

TABLES = [
    'aircraft',
    'airlines',
    'airports',
    'flights',          # ✅ Added back in properly
]


# ============================================================================
#  Export Function
# ============================================================================

def export_mobile_database():
    try:
        if EXPORT_DB.exists():
            EXPORT_DB.unlink()

        mysql_conn = mariadb.connect(**MYSQL_CONFIG)
        mysql_cursor = mysql_conn.cursor()

        sqlite_conn = sqlite3.connect(str(EXPORT_DB))

        for table in TABLES:
            print(f"📦 Exporting {table}...")

            try:

                # ----------------------------------------------------------
                # SAFE AIRCRAFT SELECT (preserve numeric integrity)
                # ----------------------------------------------------------
                if table == "aircraft":
                    mysql_cursor.execute("""
                        SELECT
                            AircraftID,
                            Registration,
                            Aircraft_Type,
                            AirlineID,
                            Country_of_Reg,
                            Times_Seen,
                            Spotted_At,
                            First_Sighted,
                            CAST(Manufacture_Year AS UNSIGNED INTEGER) AS Manufacture_Year,
                            Manufacture_Month,
                            Departure,
                            Arrival
                        FROM aircraft
                    """)
                else:
                    mysql_cursor.execute(f"SELECT * FROM {table}")

                rows = mysql_cursor.fetchall()
                columns = [desc[0] for desc in mysql_cursor.description]

                # ----------------------------------------------------------
                # Build SQLite table schema dynamically
                # ----------------------------------------------------------
                column_defs = []

                for desc in mysql_cursor.description:
                    col_name = desc[0]
                    col_type = str(desc[1]).lower()

                    if "int" in col_type:
                        sqlite_type = "INTEGER"
                    elif "float" in col_type or "double" in col_type or "decimal" in col_type:
                        sqlite_type = "REAL"
                    else:
                        sqlite_type = "TEXT"

                    column_defs.append(f"`{col_name}` {sqlite_type}")

                create_stmt = f"""
                    CREATE TABLE `{table}`
                    ({', '.join(column_defs)});
                """

                sqlite_conn.execute(create_stmt)

                # ----------------------------------------------------------
                # Convert decimal.Decimal → float for SQLite
                # ----------------------------------------------------------
                converted_rows = []

                for row in rows:
                    converted = []
                    for val in row:
                        if isinstance(val, decimal.Decimal):
                            converted.append(float(val))
                        else:
                            converted.append(val)
                    converted_rows.append(tuple(converted))

                # ----------------------------------------------------------
                # Insert rows
                # ----------------------------------------------------------
                if converted_rows:
                    placeholders = ",".join(["?"] * len(columns))
                    insert_stmt = f"INSERT INTO `{table}` VALUES ({placeholders});"
                    sqlite_conn.executemany(insert_stmt, converted_rows)
                    sqlite_conn.commit()

                print(f"   ✅ {len(converted_rows)} rows exported.")

            except Exception as inner_e:
                print(f"⚠️ Skipping table {table}: {inner_e}")

        mysql_cursor.close()
        mysql_conn.close()
        sqlite_conn.close()

        abs_path = str(EXPORT_DB.resolve())
        print(f"\n✅ Mobile export complete: {abs_path}")
        return abs_path

    except Exception as e:
        print(f"❌ Export failed: {e}")
        return None


# ============================================================================
#  Standalone execution
# ============================================================================

if __name__ == "__main__":
    export_mobile_database()