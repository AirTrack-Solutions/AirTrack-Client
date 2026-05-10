# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, url_for

from sqlalchemy import text

from extensions import db

from utils.timezone_utils import convert_to_local

flight_history_bp = Blueprint(
    'flight_history', __name__, url_prefix='/add_flight_history'
)

# ---------------------------------------------------------------------------
# VIEW FLIGHT HISTORY
# ---------------------------------------------------------------------------
def view_flight_history(aircraft_id):
    try:
        # ── Fetch aircraft ───────────────────────────────────────────────
        aircraft_row = db.session.execute(
            text("SELECT * FROM aircraft WHERE AircraftID = :id"),
            {"id": aircraft_id},
        ).fetchone()

        if not aircraft_row:
            flash("Aircraft not found.", "danger")
            return redirect(url_for("aircraft.aircraft_table"))

        aircraft = dict(aircraft_row._mapping)

        # ── Fetch flight history ─────────────────────────────────────────
        result = db.session.execute(
            text(
                """
                SELECT f.*, a.AirlineName
                FROM flights f
                LEFT JOIN airlines a ON f.AirlineID = a.AirlineID
                WHERE f.AircraftID = :id
                ORDER BY f.Timestamp DESC
                """
            ),
            {"id": aircraft_id},
        )

        history = []
        for row in result.fetchall():
            rec = dict(row._mapping)

            # Timestamp → datetime → local → formatted
            ts = rec.get("Timestamp")
            if isinstance(ts, date) and not isinstance(ts, datetime):
                ts = datetime.combine(ts, datetime.min.time())

            local_ts = convert_to_local(ts) if ts else None
            rec["local_timestamp"] = (
                local_ts.strftime("%d-%m-%Y %H:%M:%S") if local_ts else "—"
            )

            history.append(rec)

        return render_template(
            "flight_history.html",
            aircraft=aircraft,
            history=history,
        )

    except Exception as e:
        print(f"❌ Error fetching flight history: {e}")
        flash("Error loading flight history.", "danger")
        return redirect(url_for("aircraft.aircraft_table"))


# ---------------------------------------------------------------------------
# INSERT NEW FLIGHT HISTORY ENTRY
# ---------------------------------------------------------------------------
@flight_history_bp.route("/<int:aircraft_id>/record", methods=["POST"])
def record_flight_history(aircraft_id):
    try:
        result = db.session.execute(
            text("SELECT * FROM aircraft WHERE AircraftID = :id"),
            {"id": aircraft_id},
        ).fetchone()

        if not result:
            flash("Aircraft not found for flight history.", "danger")
            return redirect(url_for("aircraft.aircraft_table"))

        aircraft = dict(result._mapping)
        timestamp = datetime.utcnow()

        db.session.execute(
            text(
                """
                INSERT INTO flights (
                    AircraftID, AirlineID, FlightNumber, Registration, MSN,
                    Aircraft_Type, Times_Seen, Departure, Arrival,
                    Country_of_Reg, Timestamp, Spotted_At
                ) VALUES (
                    :AircraftID, :AirlineID, :FlightNumber, :Registration,
                    :MSN, :Aircraft_Type, :Times_Seen, :Departure, :Arrival,
                    :Country_of_Reg, :Timestamp, :Spotted_At
                )
                """
            ),
            {
                "AircraftID": aircraft["AircraftID"],
                "AirlineID": aircraft.get("AirlineID"),
                "FlightNumber": aircraft.get("FlightNumber"),
                "Registration": aircraft.get("Registration"),
                "MSN": aircraft.get("MSN"),
                "Aircraft_Type": aircraft.get("Aircraft_Type"),
                "Times_Seen": aircraft.get("Times_Seen"),
                "Departure": aircraft.get("Departure"),
                "Arrival": aircraft.get("Arrival"),
                "Country_of_Reg": aircraft.get("Country_of_Reg"),
                "Timestamp": timestamp,
                "Spotted_At": aircraft.get("Spotted_At"),
            },
        )

        # Update aircraft record so Aircraft_Updated reflects latest sighting
        db.session.execute(
            text(
                """
                UPDATE aircraft
                SET Times_Seen = COALESCE(Times_Seen, 0) + 1,
                    Aircraft_Updated = :ts
                WHERE AircraftID = :id
                """
            ),
            {"ts": timestamp, "id": aircraft_id},
        )
        db.session.commit()
        flash("Flight history recorded.", "success")

    except Exception as e:
        print(f"❌ Failed to insert flight history: {e}")
        db.session.rollback()
        flash("Failed to insert flight history.", "danger")

    return redirect(url_for("aircraft.aircraft_table"))
