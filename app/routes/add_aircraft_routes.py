# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

from datetime import datetime

from dotenv import load_dotenv

from sqlalchemy import text

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    jsonify,
)

from extensions import db, csrf

load_dotenv()

add_aircraft_bp = Blueprint('add_aircraft', __name__, url_prefix='/aircraft')



def _get_aircraft_count():
    """Return total number of aircraft records in the database."""
    return db.session.execute(text("SELECT COUNT(*) FROM aircraft")).scalar() or 0


def _lite_limit_check():
    """
    Returns (is_lite, limit_reached, current_count).
    is_lite     — True if the running edition is lite (no license.lic)
    limit_reached — True if at or over the cap
    current_count — current aircraft count (only queried for lite)
    """
    try:
        from config.license import load_license
        lic = load_license()
        if lic.max_aircraft is None:
            return False, False, 0
        count = _get_aircraft_count()
        return True, count >= lic.max_aircraft, count
    except Exception:
        return False, False, 0


def extract_icao_from_display(display_name):
    """Extract ICAO code from display name or return original string."""
    if not display_name:
        return ""
    if (
        len(display_name) == 4
        and display_name.isupper()
        and display_name.isalpha()
    ):
        return display_name
    try:
        airport_name = display_name.split(",")[0].strip()
        search_terms = [
            airport_name,
            airport_name.replace(" International", ""),
            airport_name.replace(" Airport", ""),
            airport_name.replace(" International Airport", ""),
            airport_name.split()[0],
        ]
        for term in search_terms:
            if term:
                result = db.session.execute(
                    text(
                        "SELECT ICAO "
                        "FROM airports "
                        "WHERE AirportName LIKE :term "
                        "LIMIT 1"
                    ),
                    {"term": f"%{term}%"},
                ).fetchone()

                if result:
                    return result[0]
        return display_name
    except Exception as e:
        print(f"Error converting display to ICAO: {e}")
        return display_name


@add_aircraft_bp.route("/add", methods=["GET", "POST"])
@csrf.exempt  # ✅ exempt this view from CSRFProtect

def add_aircraft():
    from utils.settings_utils import load_settings

    # clear old flashes
    session.pop("_flashes", None)

    registration = request.args.get("registration", "").strip().upper()
    airline_id_from_get = request.args.get("airlineID", type=int)

    airlines = []
    try:
        result = db.session.execute(
            text(
                "SELECT AirlineID, AirlineName FROM airlines "
                "WHERE Ceased_Operations = 0 ORDER BY AirlineName"
            )
        )
        airlines = [dict(row._mapping) for row in result.fetchall()]
        print("✅ Airlines loaded for form:", airlines)
    except Exception:
        pass

    # ── Lite edition cap check ──────────────────────────────────────────────
    is_lite, lite_limit_reached, aircraft_count = _lite_limit_check()

    if request.method == "POST":
        # Hard block — reject before any DB work
        if lite_limit_reached:
            flash(
                
                "Lite Edition limit reached. "
                "Upgrade AirTrack to add more.",
                "warning",
            )
            settings = load_settings() or {}
            settings.setdefault("Callsign", "")
            return render_template(
                "add_aircraft.html",
                registration=request.form.get("Registration", "").strip().upper(),
                airlines=airlines,
                selected_airline_id=None,
                settings=settings,
                current_theme=session.get("current_theme", "default"),
                is_lite=is_lite,
                lite_limit_reached=True,
            )

        # Normalise registration
        registration_form = request.form.get("Registration", "")
        registration_form = registration_form.strip().upper()

        # Check for existing aircraft
        existing = db.session.execute(
            text("SELECT 1 FROM aircraft WHERE Registration = :reg"),
            {"reg": registration_form},
        ).scalar()

        airline_id_raw = request.form.get("AirlineID")
        airline_id = (
            int(airline_id_raw)
            if airline_id_raw and airline_id_raw.isdigit()
            else None
        )
        selected_airline_id = airline_id

        settings = load_settings() or {}
        settings.setdefault("Callsign", "")

        if existing:
            flash(
                f"An aircraft with registration {registration_form} already exists.",
                "warning",
            )
            return render_template(
                "add_aircraft.html",
                registration=registration_form,
                airlines=airlines,
                selected_airline_id=selected_airline_id,
                settings=settings,
                current_theme=session.get("current_theme", "default"),
                is_lite=is_lite,
                lite_limit_reached=lite_limit_reached,
            )

        try:
            flight_number_raw = request.form.get("FlightNumber", "")
            flight_number = flight_number_raw.strip().upper()
            aircraft_type = request.form.get("Aircraft_Type")
            msn = request.form.get("MSN")
            category = request.form.get("Category")
            spotted_at = request.form.get("Spotted_At")
            notes = request.form.get("Notes")
            country_of_reg = request.form.get("Country_of_Reg")

            manufacture_year_raw = request.form.get("Manufacture_Year", "")
            manufacture_year = (
                int(manufacture_year_raw)
                if manufacture_year_raw.isdigit()
                else None
            )

            manufacture_month_raw = request.form.get("Manufacture_Month", "0")
            manufacture_month = (
                None
                if manufacture_month_raw in ("", "0")
                else int(manufacture_month_raw)
                if manufacture_month_raw.isdigit()
                else None
            )

            icao_display = request.form.get("ICAO_Address", "").strip()
            icao_address = extract_icao_from_display(icao_display).strip()

            departure = request.form.get("Departure", "").strip()
            arrival = request.form.get("Arrival", "").strip()

            now_utc = datetime.utcnow()
            aircraft_updated = now_utc

            sighting_date = request.form.get("Sighting_Date", "").strip()
            sighting_time = request.form.get("Sighting_Time", "").strip()
            if sighting_date:
                try:
                    from datetime import datetime as _dt
                    dt_str = sighting_date + " " + (sighting_time if sighting_time else "00:00")
                    first_sighted = _dt.strptime(dt_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    first_sighted = now_utc
            else:
                first_sighted = now_utc

            # Insert aircraft
            db.session.execute(
                text(
                    """
                INSERT INTO aircraft (
                    AirlineID,
                    Registration,
                    FlightNumber,
                    Aircraft_Type,
                    MSN,
                    Category,
                    Country_of_Reg,
                    Manufacture_Year,
                    Manufacture_Month,
                    ICAO_Address,
                    Spotted_At,
                    Notes,
                    Departure,
                    Arrival,
                    First_Sighted,
                    Aircraft_Updated
                ) VALUES (
                    :AirlineID,
                    :Registration,
                    :FlightNumber,
                    :Aircraft_Type,
                    :MSN,
                    :Category,
                    :Country_of_Reg,
                    :Manufacture_Year,
                    :Manufacture_Month,
                    :ICAO_Address,
                    :Spotted_At,
                    :Notes,
                    :Departure,
                    :Arrival,
                    :First_Sighted,
                    :Aircraft_Updated
                )
            """
                ),
                {
                    "AirlineID": airline_id,
                    "Registration": registration_form,
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
                    "First_Sighted": first_sighted,
                    "Aircraft_Updated": aircraft_updated,
                },
            )

            # Get last inserted aircraft ID
            aircraft_id = db.session.execute(
                text("SELECT LAST_INSERT_ID()")
            ).scalar()

            # Insert initial flight snapshot
            db.session.execute(
                text(
                    """
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
                ) VALUES (
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
            """
                ),
                {
                    "AircraftID": aircraft_id,
                    "AirlineID": airline_id,
                    "FlightNumber": flight_number,
                    "Registration": registration_form,
                    "MSN": msn,
                    "Aircraft_Type": aircraft_type,
                    "Departure": departure,
                    "Arrival": arrival,
                    "Country_of_Reg": country_of_reg,
                    "Timestamp": aircraft_updated,
                    "Spotted_At": spotted_at,
                },
            )

            # Write initial operator history row if an airline was assigned
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
                        "fd":    first_sighted or aircraft_updated,
                        "notes": "Initial operator at time of add",
                    },
                )

            db.session.commit()
            flash("Aircraft added successfully!", "success")
            return redirect(url_for("aircraft.aircraft_table"))

        except Exception as e:
            db.session.rollback()
            flash(f"Failed to add aircraft: {e}", "danger")
            return render_template(
                "add_aircraft.html",
                registration=registration_form,
                airlines=airlines,
                selected_airline_id=selected_airline_id,
                settings=settings,
                current_theme=session.get("current_theme", "default"),
                is_lite=is_lite,
                lite_limit_reached=lite_limit_reached,
            )

    # GET path
    from utils.settings_utils import load_settings

    settings = load_settings() or {}
    settings.setdefault("Callsign", "")
    selected_airline_id = airline_id_from_get

    return render_template(
        "add_aircraft.html",
        airlines=airlines,
        registration=registration,
        selected_airline_id=selected_airline_id,
        settings=settings,
        current_theme=session.get("current_theme", "default"),
        is_lite=is_lite,
        lite_limit_reached=lite_limit_reached,
    )
