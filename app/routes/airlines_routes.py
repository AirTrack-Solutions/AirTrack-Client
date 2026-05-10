# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

import logging

from datetime import date, datetime

from extensions import db

from flask import Blueprint, flash, redirect, render_template, request, url_for

from sqlalchemy import text

from utils.settings_utils import get_current_theme

# Optional local-time converter (safe fallback)
try:
    from utils.timezone_utils import convert_to_local  # type: ignore
except Exception:
    def convert_to_local(dt):  # noqa: D401
        return dt

airlines_bp = Blueprint("airlines", __name__, url_prefix="/airlines")


def load_settings():
    settings = {}
    try:
        rows = db.session.execute(
            text("SELECT SettingKey, SettingValue FROM app_settings")
        ).fetchall()
        settings = {row[0]: row[1] for row in rows}
    except Exception as e:
        logging.warning(f"⚠️ Failed to load settings: {e}")
    return settings


@airlines_bp.route("/", methods=["GET"], endpoint="airlines_table")
def airlines_table():
    """Paginated Airlines table."""
    try:
        airline_filter = request.args.get("airline", "").strip()
        search_query = request.args.get("search", "").strip()
        page = request.args.get("page", default=1, type=int)
        per_page = 10
        offset = (page - 1) * per_page

        params = {
            "search": f"%{search_query}%",
            "limit": per_page,
            "offset": offset,
        }

        count_result = db.session.execute(
            text(
                """
                SELECT COUNT(DISTINCT a.AirlineID) AS total
                FROM airlines a
                LEFT JOIN aircraft ac ON a.AirlineID = ac.AirlineID
                WHERE a.AirlineName LIKE :search
                """
            ),
            params,
        ).fetchone()
        total_records = count_result[0] if count_result else 0
        total_pages = max(1, (total_records + per_page - 1) // per_page)

        # Block pagination
        block = 10
        start_page = ((page - 1) // block) * block + 1
        end_page = min(start_page + block - 1, total_pages)
        prev_10_page = start_page - block if start_page > 1 else None
        next_10_page = end_page + 1 if end_page < total_pages else None
        prev_page = page - 1 if page > 1 else None
        next_page = page + 1 if page < total_pages else None

        result = db.session.execute(
            text(
                """
                SELECT a.AirlineID, a.AirlineName, a.Logo,
                       COUNT(ac.AircraftID) AS TotalAircraft
                FROM airlines a
                LEFT JOIN aircraft ac ON a.AirlineID = ac.AirlineID
                WHERE a.AirlineName LIKE :search
                GROUP BY a.AirlineID, a.AirlineName, a.Logo
                ORDER BY a.AirlineName
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        airlines = [dict(row._mapping) for row in result.fetchall()]

        settings = load_settings()
        current_theme = get_current_theme()
        return render_template(
            "airlines_table.html",
            airlines=airlines,
            current_page=page,
            total_pages=total_pages,
            start_page=start_page,
            end_page=end_page,
            prev_10_page=prev_10_page,
            next_10_page=next_10_page,
            prev_page=prev_page,
            next_page=next_page,
            per_page=per_page,
            search_query=search_query,
            airline_filter=airline_filter,
            settings=settings,
            current_theme=current_theme,
        )
    except Exception as e:
        logging.error(f"❌ Error fetching airlines: {e}")
        flash("An error occurred loading airlines.", "danger")
        settings = load_settings()
        current_theme = get_current_theme()
        # Keep the template shape stable on error
        return render_template(
            "airlines_table.html",
            airlines=[],
            current_page=1,
            total_pages=1,
            start_page=1,
            end_page=1,
            per_page=10,
            search_query="",
            airline_filter="",
            prev_10_page=None,
            next_10_page=None,
            prev_page=None,
            next_page=None,
            settings=settings,
            current_theme=current_theme,
        )


@airlines_bp.route("/info/<int:airline_id>", methods=["GET"], endpoint="airline_info")
def airline_info(airline_id: int):
    """
    Airline detail page.
    URL: /airlines/info/<airline_id>
    Templates should link via: url_for('airlines.airline_info', airline_id=ID)
    """
    try:
        # --- Airline row (now actually fetches Country / IATA / ICAO / Callsign)
        airline_row = db.session.execute(
            text(
                """
                SELECT AirlineID, AirlineName, Logo, Country, IATA, ICAO, Callsign, Last_Updated
                FROM airlines
                WHERE AirlineID = :id
                """
            ),
            {"id": airline_id},
        ).fetchone()

        if not airline_row:
            flash("Airline not found.", "warning")
            return redirect(url_for("airlines.airlines_table"))

        airline = dict(airline_row._mapping)

        # Normalize and present-friendly values
        def norm(s):
            return (s or "").strip() or None

        airline["Country"] = norm(airline.get("Country"))
        airline["IATA"] = norm(airline.get("IATA"))
        airline["ICAO"] = norm(airline.get("ICAO"))
        airline["Callsign"] = norm(airline.get("Callsign"))

        # Format Last_Updated to local display
        lu = airline.get("Last_Updated")

        if isinstance(lu, date) and not isinstance(lu, datetime):
            lu = datetime.combine(lu, datetime.min.time())

        if lu:
            local_lu = convert_to_local(lu)
            airline["Last_Updated_Display"] = local_lu.strftime("%d-%m-%Y %H:%M:%S")
        else:
            airline["Last_Updated_Display"] = "—"

        # --- Aircraft operated by this airline ---
        rows = db.session.execute(
            text(
                """
                SELECT
                    ac.AircraftID,
                    ac.Registration,
                    ac.Aircraft_Type,
                    ac.FlightNumber,
                    ac.Departure,
                    ac.Arrival,
                    ac.First_Sighted,
                    ac.Aircraft_Updated
                FROM aircraft ac
                WHERE ac.AirlineID = :id
                ORDER BY ac.Aircraft_Updated DESC
                """
            ),
            {"id": airline_id},
        ).fetchall()

        aircraft_list = []
        for r in rows:
            d = dict(r._mapping)

            # Time displays
            fs = d.get("First_Sighted")
            if isinstance(fs, date) and not isinstance(fs, datetime):
                fs = datetime.combine(fs, datetime.min.time())

            up = d.get("Aircraft_Updated")
            if isinstance(up, date) and not isinstance(up, datetime):
                up = datetime.combine(up, datetime.min.time())

            # Format to display strings
            local_fs = convert_to_local(fs) if fs else None
            local_up = convert_to_local(up) if up else None

            d["First_Sighted_Display"] = (
                local_fs.strftime("%Y-%m-%d %H:%M:%S") if local_fs else "—"
            )
            d["Aircraft_Updated_Display"] = (
                local_up.strftime("%Y-%m-%d %H:%M:%S") if local_up else "—"
            )

            aircraft_list.append(d)

        current_theme = get_current_theme()
        return render_template(
            "airline_info.html",
            airline=airline,
            aircraft_list=aircraft_list,
            selected_theme=current_theme,
            cache_bust=datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        )
    except Exception as e:
        logging.error("❌ Failed to load airline info", exc_info=True)
        flash("Could not load airline info.", "danger")
        return redirect(url_for("airlines.airlines_table"))


@airlines_bp.route("/add", methods=["GET", "POST"], endpoint="add_airline")
def add_airline():
    settings = load_settings() or {}
    if request.method == "POST":
        airline_name = request.form.get("AirlineName", "").strip()
        if not airline_name:
            flash("Airline name is required.", "danger")
            return redirect(url_for("airlines.add_airline"))
        try:
            db.session.execute(
                text("INSERT INTO airlines (AirlineName) VALUES (:name)"),
                {"name": airline_name},
            )
            db.session.commit()
            flash("Airline added successfully!", "success")
            return redirect(url_for("airlines.airlines_table"))
        except Exception as e:
            logging.error(f"❌ Error adding airline: {e}", exc_info=True)
            flash("Failed to add airline.", "danger")
            return redirect(url_for("airlines.add_airline"))

    return render_template("add_airline.html", settings=settings)
