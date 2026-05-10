# AirTrack 1.0.0
# Country Importer / Manual Entry Engine

import re
from sqlalchemy import text

# --------------------------------------------------
# VALID AIRTRACK COLUMNS (CRITICAL FILTER)
# --------------------------------------------------

AIRTRACK_COLUMNS = [
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

# --------------------------------------------------
# PREFIX → TABLE MAP
# --------------------------------------------------

PREFIX_TABLES = {
    "VH": "australia",
    "P2": "papua_new_guinea",
    "ZK": "new_zealand",
    "SE": "sweden",
    "G": "united_kingdom",
    "C": "canada",
    "N": "united_states",
}

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def normalize_registration(reg):
    if not reg:
        return ""
    reg = reg.strip().upper()

    if reg.startswith("N-"):
        reg = reg.replace("-", "", 1)

    return reg


def clean_table_name(name):
    if not name:
        return "unknown"

    table = name.strip().lower()
    table = table.replace(" ", "_").replace("-", "_")
    table = re.sub(r"[^a-z0-9_]", "", table)

    return table or "unknown"


# --------------------------------------------------
# DETECT COUNTRY TABLE
# --------------------------------------------------

def detect_country_table(registration):
    reg = normalize_registration(registration)

    for prefix, table in sorted(PREFIX_TABLES.items(), key=lambda x: len(x[0]), reverse=True):
        if reg.startswith(prefix):
            return table

    return "unknown"


# --------------------------------------------------
# ENSURE TABLE EXISTS
# --------------------------------------------------

def ensure_country_table(db, table_name):
    table = clean_table_name(table_name)

    db.session.execute(
        text(f"""
        CREATE TABLE IF NOT EXISTS `{table}` (
            registration VARCHAR(10) NOT NULL PRIMARY KEY,
            hexcode VARCHAR(10),
            aircraftmanufacturer VARCHAR(100),
            aircraftmodel VARCHAR(50),
            msn VARCHAR(50),
            maxtakeoffweight INT,
            enginecount INT,
            enginemanufacturer VARCHAR(100),
            enginetype VARCHAR(50),
            enginemodel VARCHAR(50),
            fueltype VARCHAR(50),
            registrationtype VARCHAR(50),
            registeredowner VARCHAR(150),
            registeredownercountry VARCHAR(50),
            operatorname VARCHAR(150),
            operatorcountry VARCHAR(50),
            firstregistrationdate DATE,
            airframe VARCHAR(100),
            propmanu VARCHAR(100),
            propmodel VARCHAR(50),
            typecert VARCHAR(50),
            countrymanu VARCHAR(50),
            yearmanu INT,
            monthmanu INT,
            icaotypedesig VARCHAR(10)
        )
        """)
    )

    db.session.commit()
    return table


# --------------------------------------------------
# UPSERT AIRCRAFT (FIXED + SAFE)
# --------------------------------------------------

def upsert_aircraft(db, table_name, data):
    table = ensure_country_table(db, table_name)

    # Normalize registration
    reg = normalize_registration(data.get("registration"))
    if not reg:
        raise ValueError("Registration is required")

    cleaned = {}

    # 🚨 CRITICAL FIX — ONLY USE VALID COLUMNS
    for col in AIRTRACK_COLUMNS:
        value = data.get(col)

        if isinstance(value, str):
            value = value.strip()

        cleaned[col] = value if value not in ("", None) else None

    cleaned["registration"] = reg

    # Convert numeric fields safely
    for field in ["maxtakeoffweight", "enginecount", "yearmanu", "monthmanu"]:
        if cleaned.get(field):
            try:
                cleaned[field] = int(cleaned[field])
            except ValueError:
                cleaned[field] = None

    # Build SQL dynamically
    columns = []
    values = []
    updates = []

    for key in cleaned.keys():
        columns.append(f"`{key}`")
        values.append(f":{key}")

        if key != "registration":
            updates.append(f"`{key}` = VALUES(`{key}`)")

    # 🚨 NEVER allow empty UPDATE (fixes your previous crash)
    if not updates:
        updates.append("`registration` = VALUES(`registration`)")

    query = f"""
    INSERT INTO `{table}` ({", ".join(columns)})
    VALUES ({", ".join(values)})
    ON DUPLICATE KEY UPDATE
        {", ".join(updates)}
    """

    db.session.execute(text(query), cleaned)
    db.session.commit()

    return table, reg


# --------------------------------------------------
# MAIN IMPORT ENTRY POINT
# --------------------------------------------------

def import_aircraft_row(db, raw_data):
    reg = normalize_registration(raw_data.get("registration"))

    if not reg:
        raise ValueError("Missing registration")

    table = detect_country_table(reg)

    return upsert_aircraft(db, table, raw_data)