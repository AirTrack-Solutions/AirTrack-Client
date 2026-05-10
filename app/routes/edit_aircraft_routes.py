# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



import logging

from datetime import datetime

from typing import Optional

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from sqlalchemy import text

from extensions import db

edit_aircraft_bp = Blueprint('edit_aircraft', __name__, url_prefix='/edit_aircraft')

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _get_str(form, key: str, default: str = "") -> str:
    v = form.get(key, default)
    return (v if isinstance(v, str) else default).strip()

def _get_upper(form, key: str, default: str = "") -> str:
    return _get_str(form, key, default).upper()

def _get_int_or_none(form, key: str) -> Optional[int]:
    s = _get_str(form, key, "")
    if s == "":
        return None
    try:
        return int(s)
    except ValueError:
        return None

def _none_if_zero(n: Optional[int]) -> Optional[int]:
    return None if n in (None, 0) else n


# ---------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------

@edit_aircraft_bp.route("/<int:aircraft_id>", methods=["GET", "POST"])
def edit_aircraft(aircraft_id):

    try:
        # Load airlines for dropdown
        result = db.session.execute(
            text("SELECT AirlineID, AirlineName FROM airlines ORDER BY AirlineName")
        )
        airlines = [dict(r._mapping) for r in result.fetchall()]

        if request.method == "POST":

            # ✅ DEBUG (now correctly placed)
            print("✅ EDIT POST HIT:", dict(request.form))

            # ✅ Default to EDIT if button name is missing
            save_mode = request.form.get("save_mode", "edit")

            # ----------------------------
            # Extract fields
            # ----------------------------
            registration = _get_upper(request.form, 'Registration')
            flight_number = _get_upper(request.form, 'FlightNumber')
            aircraft_type = _get_str(request.form, 'Aircraft_Type')
            msn = _get_str(request.form, 'MSN')
            category = _get_str(request.form, 'Category')
            spotted_at = _get_str(request.form, 'Spotted_At')
            notes = _get_str(request.form, 'Notes')
            country_of_reg = _get_str(request.form, 'Country_of_Reg')
            times_seen = _none_if_zero(_get_int_or_none(request.form, 'Times_Seen'))
            manufacture_year = _none_if_zero(_get_int_or_none(request.form, 'Manufacture_Year'))
            manufacture_month = _none_if_zero(_get_int_or_none(request.form, 'Manufacture_Month'))
            airline_id = _none_if_zero(_get_int_or_none(request.form, 'AirlineID'))
            icao_address = _get_upper(request.form, 'ICAO_Address')
            departure = _get_upper(request.form, 'Departure')
            arrival = _get_upper(request.form, 'Arrival')
            now = datetime.utcnow()

            # =========================================================
            # ✅ SAVE CHANGES — UPDATE AIRCRAFT
            # =========================================================
            if save_mode == "edit":

                db.session.execute(
                    text("""
                        UPDATE aircraft
                        SET AirlineID         = :AirlineID,
                            Registration      = :Registration,
                            FlightNumber      = :FlightNumber,
                            Aircraft_Type     = :Aircraft_Type,
                            MSN               = :MSN,
                            Category          = :Category,
                            Country_of_Reg    = :Country_of_Reg,
                            Times_Seen        = :Times_Seen,
                            Manufacture_Year  = :Manufacture_Year,
                            Manufacture_Month = :Manufacture_Month,
                            ICAO_Address      = :ICAO_Address,
                            Spotted_At        = :Spotted_At,
                            Notes             = :Notes,
                            Departure         = :Departure,
                            Arrival           = :Arrival,
                            Aircraft_Updated  = :Updated
                        WHERE AircraftID = :AircraftID
                    """),
                    {
                        "AirlineID": airline_id,
                        "Registration": registration,
                        "FlightNumber": flight_number,
                        "Aircraft_Type": aircraft_type,
                        "MSN": msn,
                        "Category": category,
                        "Country_of_Reg": country_of_reg,
                        "Times_Seen": times_seen,
                        "Manufacture_Year": manufacture_year,
                        "Manufacture_Month": manufacture_month,
                        "ICAO_Address": icao_address,
                        "Spotted_At": spotted_at,
                        "Notes": notes,
                        "Departure": departure,
                        "Arrival": arrival,
                        "Updated": now,
                        "AircraftID": aircraft_id,
                    },
                )

                db.session.commit()
                flash("Aircraft updated successfully.", "success")
                return redirect(url_for("aircraft.aircraft_table"))

            # =========================================================
            # ✅ NEW FLIGHT
            # =========================================================
            elif save_mode == "new":

                db.session.execute(
                    text("""
                        INSERT INTO flights (
                            AircraftID,
                            AirlineID,
                            FlightNumber,
                            Registration,
                            MSN,
                            Aircraft_Type,
                            Times_Seen,
                            Departure,
                            Arrival,
                            Country_of_Reg,
                            Timestamp,
                            Spotted_At
                        )
                        VALUES (
                            :AircraftID,
                            :AirlineID,
                            :FlightNumber,
                            :Registration,
                            :MSN,
                            :Aircraft_Type,
                            :Times_Seen,
                            :Departure,
                            :Arrival,
                            :Country_of_Reg,
                            :Timestamp,
                            :Spotted_At
                        )
                    """),
                    {
                        "AircraftID": aircraft_id,
                        "AirlineID": airline_id,
                        "FlightNumber": flight_number,
                        "Registration": registration,
                        "MSN": msn,
                        "Aircraft_Type": aircraft_type,
                        "Times_Seen": times_seen,
                        "Departure": departure,
                        "Arrival": arrival,
                        "Country_of_Reg": country_of_reg,
                        "Timestamp": now,
                        "Spotted_At": spotted_at,
                    },
                )

                # Stamp Aircraft_Updated so Last Seen reflects this sighting
                db.session.execute(
                    text(
                        "UPDATE aircraft SET Aircraft_Updated = :ts "
                        "WHERE AircraftID = :id"
                    ),
                    {"ts": now, "id": aircraft_id},
                )

                db.session.commit()
                flash("New flight recorded.", "success")
                return redirect(url_for("aircraft.aircraft_info", aircraft_id=aircraft_id))

            else:
                flash("Invalid save action.", "danger")
                return redirect(url_for("aircraft.aircraft_table"))

        # ----------------------------
        # GET: Load aircraft
        # ----------------------------
        result = db.session.execute(
            text("SELECT * FROM aircraft WHERE AircraftID = :id"),
            {"id": aircraft_id},
        )
        row = result.fetchone()

        if not row:
            flash("Aircraft not found.", "danger")
            return redirect(url_for("aircraft.aircraft_table"))

        return render_template(
            "edit_aircraft.html",
            aircraft=dict(row._mapping),
            airlines=airlines,
        )

    except Exception as e:
        db.session.rollback()
        logging.exception("❌ Edit aircraft error: %s", e)
        flash("Unexpected error while editing aircraft.", "danger")
        return redirect(url_for("aircraft.aircraft_table"))
