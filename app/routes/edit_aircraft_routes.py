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
        # Load current AirlineID so we can include it even if ceased
        current_row = db.session.execute(
            text("SELECT AirlineID FROM aircraft WHERE AircraftID = :id"),
            {"id": aircraft_id},
        ).fetchone()
        current_airline_id = current_row[0] if current_row else None

        result = db.session.execute(
            text(
                "SELECT AirlineID, AirlineName FROM airlines "
                "WHERE Ceased_Operations = 0 OR AirlineID = :current "
                "ORDER BY AirlineName"
            ),
            {"current": current_airline_id},
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

                # If operator changed, close old history row and open new one
                if airline_id != current_airline_id:
                    today = datetime.utcnow().date()
                    if current_airline_id:
                        db.session.execute(
                            text(
                                "UPDATE aircraft_owners SET To_Date = :today "
                                "WHERE AircraftID = :ac AND To_Date IS NULL"
                            ),
                            {"today": today, "ac": aircraft_id},
                        )
                    if airline_id:
                        airline_name_snap = db.session.execute(
                            text("SELECT AirlineName FROM airlines WHERE AirlineID = :id"),
                            {"id": airline_id},
                        ).scalar()
                        db.session.execute(
                            text(
                                "INSERT INTO aircraft_owners "
                                "(AircraftID, AirlineID, airline_name_snapshot, From_Date, Notes) "
                                "VALUES (:ac, :al, :snap, :fd, :notes)"
                            ),
                            {
                                "ac":    aircraft_id,
                                "al":    airline_id,
                                "snap":  airline_name_snap,
                                "fd":    today,
                                "notes": "Operator updated via edit form",
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
