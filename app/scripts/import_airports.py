# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
import csv
import os
import mariadb
from dotenv import load_dotenv
load_dotenv()


def get_db_connection():
    try:
        return mariadb.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
        )
    except mariadb.Error as e:
        print(f"❌ Database error: {e}")
        return None


def import_airports():
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        print("🧹 Clearing existing airports table...")
        cursor.execute("DELETE FROM airports")
        # Ensure IATA field can handle 'N/A' or 4-character codes
        cursor.execute("ALTER TABLE airports MODIFY IATA VARCHAR(4)")
        print("⬆️  Importing airports from CSV...")
        with open("airports.csv", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            reader.fieldnames = [f.lower() for f in reader.fieldnames]
            count = 0
            for row in reader:
                icao = row.get("icao", "").strip().upper()
                # Skip if ICAO is missing, 'N/A', or longer than 4 chars
                if not icao or icao == "N/A" or len(icao) > 4:
                    continue
                cursor.execute(
                    """
                    INSERT INTO airports (ICAO, IATA, AirportName, Country,  # truncated
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        icao,
                        row.get("code", "N/A").strip()[:4],  # Ensure max 4  # truncated
                        row.get("name", "N/A"),
                        row.get("country", "N/A"),
                        row.get("latitude", None),
                        row.get("longitude", None),
                        row.get("elevation", None),
                        row.get("time_zone", "N/A"),
                        row.get("city", "N/A"),
                        row.get("state", "N/A"),
                    ),
                )
                count += 1
        conn.commit()
        print(f"✅ Import complete: {count} airports added.")
        cursor.close()
    except Exception as e:
        print(f"❌ Import failed: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    import_airports()
