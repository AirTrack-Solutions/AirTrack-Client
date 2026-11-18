"""Read-only SQL sources for aircraft statistics, not record management.

Airline names are the V1 classification agreed with Trevor. Keep unknown or
missing airlines as aircraft; only the two explicit ground labels are excluded.
These SQL fragments are constants and must never contain request input.
"""

GROUND_NAMES = "('ground station', 'ground vehicle')"

AIRLINES_FOR_STATS = f"""(
    SELECT * FROM airlines
    WHERE LOWER(TRIM(COALESCE(AirlineName, ''))) NOT IN {GROUND_NAMES}
)"""

AIRCRAFT_FOR_STATS = f"""(
    SELECT scope_ac.* FROM aircraft scope_ac
    WHERE NOT EXISTS (
        SELECT 1 FROM airlines scope_al
        WHERE scope_al.AirlineID = scope_ac.AirlineID
          AND LOWER(TRIM(scope_al.AirlineName)) IN {GROUND_NAMES}
    )
)"""

# Prefer the current aircraft classification: editing it must also affect old
# sightings whose historical AirlineID is blank or different. If the aircraft
# record is missing, use the sighting's own airline classification instead.
FLIGHTS_FOR_STATS = f"""(
    SELECT scope_f.* FROM flights scope_f
    WHERE NOT EXISTS (
        SELECT 1 FROM aircraft scope_ac
        JOIN airlines scope_al ON scope_al.AirlineID = scope_ac.AirlineID
        WHERE scope_ac.AircraftID = scope_f.AircraftID
          AND LOWER(TRIM(scope_al.AirlineName)) IN {GROUND_NAMES}
    )
    AND (
        EXISTS (SELECT 1 FROM aircraft scope_current
                WHERE scope_current.AircraftID = scope_f.AircraftID)
        OR NOT EXISTS (
            SELECT 1 FROM airlines scope_al
            WHERE scope_al.AirlineID = scope_f.AirlineID
              AND LOWER(TRIM(scope_al.AirlineName)) IN {GROUND_NAMES}
        )
    )
)"""
