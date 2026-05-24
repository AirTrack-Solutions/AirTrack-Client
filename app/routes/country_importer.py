# AirTrack 1.0.0
# Country Importer — routes shim
# Canonical implementation lives in app/utils/country_importer.py
# This file exists only so that legacy imports from routes.country_importer continue to work.

from utils.country_importer import (  # noqa: F401
    AIRTRACK_COLUMNS,
    PREFIX_TABLES,
    normalize_registration,
    normalize_hexcode,
    clean_table_name,
    detect_country_table,
    ensure_country_table,
    upsert_aircraft,
    import_aircraft_row,
)
