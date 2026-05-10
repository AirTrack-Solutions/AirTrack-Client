# AirTrack 1.0.0
# Country Importer / Manual Entry Engine
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

import re
from sqlalchemy import text

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

PREFIX_TABLES = {
    "VH": "australia",
    "P2": "papua_new_guinea",
    "4R": "sri_lanka",
    "ZK": "new_zealand",
    "SE": "sweden",
    "G": "united_kingdom",
    "C": "canada",
    "N": "united_states",
}


def normalize_registration(reg):
    """Normalize user-entered aircraft registrations."""
    if not reg:
        return ""

    reg = reg.strip().upper()

    if reg.startswith("N-"):
        reg = reg.replace("-", "", 1)

    return reg


def normalize_hexcode(hexcode):
    """Normalize ADS-B ICAO24 hex codes."""
    if not hexcode:
        return None

    value = str(hexcode).strip().upper()
    value = re.sub(r"[^A-F0-9]", "", value)

    return value or None


def clean_table_name(name):
    """Return a safe MariaDB table name."""
    if not name:
        return "unknown"

    table = name.strip().lower()
    table = table.replace(" ", "_").replace("-", "_")
    table = re.sub(r"[^a-z0-9_]", "", table)

    return table or "unknown"


def detect_country_table(registration):
    """Detect the destination country table from an aircraft registration."""
    reg = normalize_registration(registration)

    for prefix, table in sorted(
        PREFIX_TABLES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if reg.startswith(prefix):
            return table

    return "unknown"


def ensure_country_table(db, table_name):
    """Create a country aircraft table if it does not already exist."""
    table = clean_table_name(table_name)

    db.session.execute(
        text(
            f"""
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
            """
        )
    )

    db.session.commit()
    return table


def upsert_aircraft(db, table_name, data):
    """Insert/update one aircraft row into the selected country table."""
    table = ensure_country_table(db, table_name)

    reg = normalize_registration(data.get("registration"))
    if not reg:
        raise ValueError("Registration is required")

    cleaned = {}

    for col in AIRTRACK_COLUMNS:
        value = data.get(col)

        if isinstance(value, str):
            value = value.strip()

        cleaned[col] = value if value not in ("", None) else None

    cleaned["registration"] = reg
    cleaned["hexcode"] = normalize_hexcode(cleaned.get("hexcode"))

    for field in ["maxtakeoffweight", "enginecount", "yearmanu", "monthmanu"]:
        if cleaned.get(field):
            try:
                cleaned[field] = int(cleaned[field])
            except (TypeError, ValueError):
                cleaned[field] = None

    columns = []
    values = []
    updates = []

    for key in cleaned.keys():
        columns.append(f"`{key}`")
        values.append(f":{key}")

        if key != "registration":
            updates.append(f"`{key}` = VALUES(`{key}`)")

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


def import_aircraft_row(db, raw_data):
    """Import one aircraft row using automatic prefix-based table detection."""
    reg = normalize_registration(raw_data.get("registration"))

    if not reg:
        raise ValueError("Missing registration")

    table = detect_country_table(reg)

    return upsert_aircraft(db, table, raw_data)
