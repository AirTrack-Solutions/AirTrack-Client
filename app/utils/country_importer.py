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
    # ---- 4-char prefixes (VP/VQ territories — must match before shorter VP/VQ) ----
    "VP-C": "cayman_islands",
    "VQ-T": "turks_and_caicos_islands",

    # ---- 2-char prefixes ----
    "4L":  "georgia",
    "4O":  "montenegro",
    "4R":  "sri_lanka",
    "5B":  "cyprus",
    "5V":  "togo",
    "6V":  "senegal",
    "6W":  "senegal",
    "6Y":  "jamaica",
    "8Q":  "maldives",
    "9A":  "croatia",
    "9H":  "malta",
    "9M":  "malaysia",
    "9V":  "singapore",
    "9Y":  "trinidad_and_tobago",
    "A5":  "bhutan",
    "A6":  "united_arab_emirates",
    "A7":  "qatar",
    "A8":  "liberia",
    "AP":  "pakistan",
    "C6":  "bahamas",
    "CC":  "chile",
    "CN":  "morocco",
    "CP":  "bolivia",
    "CU":  "cuba",
    "CX":  "uruguay",
    "DQ":  "fiji",
    "EC":  "spain",
    "EI":  "ireland",
    "EJ":  "ireland",
    "EK":  "armenia",
    "EL":  "liberia",
    "EP":  "iran",
    "ER":  "moldova",
    "ES":  "estonia",
    "ET":  "ethiopia",
    "HA":  "hungary",
    "HB":  "switzerland",
    "HL":  "south_korea",
    "HP":  "panama",
    "HS":  "thailand",
    "HZ":  "saudi_arabia",
    "JA":  "japan",
    "LN":  "norway",
    "LQ":  "argentina",
    "LV":  "argentina",
    "LX":  "luxembourg",
    "LY":  "lithuania",
    "LZ":  "bulgaria",
    "OE":  "austria",
    "OH":  "finland",
    "OK":  "czech_republic",
    "OM":  "slovakia",
    "OO":  "belgium",
    "OY":  "denmark",
    "P2":  "papua_new_guinea",
    "PH":  "netherlands",
    "PK":  "indonesia",
    "PP":  "brazil",
    "PR":  "brazil",
    "PT":  "brazil",
    "PU":  "brazil",
    "PZ":  "suriname",
    "RA":  "russia",
    "RF":  "russia",
    "RP":  "philippines",
    "S7":  "seychelles",
    "SE":  "sweden",
    "SP":  "poland",
    "SU":  "egypt",
    "SX":  "greece",
    "T7":  "san_marino",
    "T9":  "bosnia_and_herzegovina",
    "TC":  "turkey",
    "TF":  "iceland",
    "TI":  "costa_rica",
    "V3":  "belize",
    "VH":  "australia",
    "VT":  "india",
    "YL":  "latvia",
    "YR":  "romania",
    "YU":  "serbia",
    "Z3":  "north_macedonia",
    "ZK":  "new_zealand",
    "ZS":  "south_africa",
    "ZT":  "south_africa",
    "ZU":  "south_africa",

    # ---- 1-char prefixes (matched last) ----
    "2":   "guernsey",
    "B":   "china",
    "C":   "canada",
    "D":   "germany",
    "F":   "france",
    "G":   "united_kingdom",
    "I":   "italy",
    "M":   "isleofman",
    "N":   "united_states",
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


def normalize_hexcode(hexcode):
    """Normalize ADS-B ICAO24 hex codes."""
    if not hexcode:
        return None
    value = str(hexcode).strip().upper()
    value = re.sub(r"[^A-F0-9]", "", value)
    return value or None


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
    cleaned["hexcode"] = normalize_hexcode(cleaned.get("hexcode"))

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