# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from datetime import date, datetime

import pytz

import logging

from extensions import db

from flask import Blueprint, render_template, request

from sqlalchemy import text

from utils.country_flags import get_country_flag

from utils.settings_utils import get_current_timezone

search_unified_bp = Blueprint('search_unified', __name__)

@search_unified_bp.route('/search_unified')

def search_unified():
    from flask import current_app
    current_app.logger.info(
        f"🔍 search_unified called: type={request.args.get('type')}, search={request.args.get('search')}"
    )

    search_type = (request.args.get('type') or '').strip().lower()
    search_query = (request.args.get('search') or '').strip()
    page = int(request.args.get('page', 1))
    per_page = 50
    offset = (page - 1) * per_page
    filtered_data = []
    total_pages = 1
    like_query = f"%{search_query.lower()}%"

    # ============================================================
    # Aircraft search FIXED
    # ============================================================
    if search_type in ('aircraft', 'aircrafts'):
        count_result = db.session.execute(
            text("""
                SELECT COUNT(*) FROM aircraft a
                LEFT JOIN airlines al ON a.AirlineID = al.AirlineID
                WHERE LOWER(a.Registration) LIKE :q
                OR LOWER(a.Aircraft_Type) LIKE :q
                OR LOWER(a.Departure) LIKE :q
                OR LOWER(a.Arrival) LIKE :q
                OR LOWER(a.Country_of_Reg) LIKE :q
                OR LOWER(al.AirlineName) LIKE :q
            """),
            {"q": like_query},
        ).scalar()

        total_pages = max(1, (count_result + per_page - 1) // per_page)

        result = db.session.execute(
            text("""
                SELECT a.AircraftID, a.Registration, a.FlightNumber,
                    a.Aircraft_Type, a.Departure, a.Arrival, a.Country_of_Reg,
                    a.Category,
                    a.First_Sighted,
                    a.Aircraft_Updated AS Last_Sighted,
                    a.Aircraft_Updated AS Timestamp,
                    a.AirlineID, al.AirlineName
                FROM aircraft a
                LEFT JOIN airlines al ON a.AirlineID = al.AirlineID
                WHERE LOWER(a.Registration) LIKE :q
                OR LOWER(a.Aircraft_Type) LIKE :q
                OR LOWER(a.Departure) LIKE :q
                OR LOWER(a.Arrival) LIKE :q
                OR LOWER(a.Country_of_Reg) LIKE :q
                OR LOWER(al.AirlineName) LIKE :q
                ORDER BY a.Aircraft_Updated DESC
                LIMIT :limit OFFSET :offset
            """),
            {"q": like_query, "limit": per_page, "offset": offset},
        )

        timezone = get_current_timezone()

        for row in result:
            aircraft = dict(row._mapping)

            logging.debug(
                f"🛫 Airline data check: ID={aircraft.get('AirlineID')}, Name={aircraft.get('AirlineName')}"
            )

            # --- Fix AirlineName if missing ---
            if not aircraft.get("AirlineName"):
                if "airlinename" in aircraft:
                    aircraft["AirlineName"] = aircraft["airlinename"]
                elif aircraft.get("AirlineID"):
                    lookup = db.session.execute(
                        text("SELECT AirlineName FROM airlines WHERE AirlineID = :id"),
                        {"id": aircraft["AirlineID"]},
                    ).fetchone()
                    aircraft["AirlineName"] = lookup[0] if lookup else "—"
                else:
                    aircraft["AirlineName"] = "—"

            # --- Timestamps ---
            dt_fs = aircraft.get("First_Sighted")
            if dt_fs:
                if isinstance(dt_fs, date) and not isinstance(dt_fs, datetime):
                    dt_fs = datetime.combine(dt_fs, datetime.min.time())
                if dt_fs.tzinfo is None:
                    dt_fs = dt_fs.replace(tzinfo=pytz.utc)
                aircraft["First_Sighted"] = dt_fs.astimezone(timezone).strftime("%Y-%m-%d %H:%M")
            else:
                aircraft["First_Sighted"] = "—"

            dt_ls = aircraft.get("Last_Sighted")
            if dt_ls:
                if isinstance(dt_ls, date) and not isinstance(dt_ls, datetime):
                    dt_ls = datetime.combine(dt_ls, datetime.min.time())
                if dt_ls.tzinfo is None:
                    dt_ls = dt_ls.replace(tzinfo=pytz.utc)
                aircraft["Last_Sighted"] = dt_ls.astimezone(timezone).strftime("%Y-%m-%d %H:%M")
            else:
                aircraft["Last_Sighted"] = "—"

            dt_upd = aircraft.get("Timestamp")
            if dt_upd:
                if isinstance(dt_upd, date) and not isinstance(dt_upd, datetime):
                    dt_upd = datetime.combine(dt_upd, datetime.min.time())
                if dt_upd.tzinfo is None:
                    dt_upd = dt_upd.replace(tzinfo=pytz.utc)
                aircraft["Timestamp"] = dt_upd.astimezone(timezone).strftime("%Y-%m-%d %H:%M")
            else:
                aircraft["Timestamp"] = "—"

            # --- Country Flag ---
            aircraft["Country_Flag"] = get_country_flag(aircraft.get("Country_of_Reg"))

            # 🚀 ALWAYS append aircraft — FIXED
            filtered_data.append(aircraft)

        return render_template(
            "partials/_aircraft_table_rows.html",
            filtered_aircraft=filtered_data,
            total_pages=total_pages,
            current_page=page,
            search_query=search_query,
        )

    # ============================================================
    # Airline search (unchanged)
    # ============================================================
    elif search_type in ("airline", "airlines"):
        count_result = db.session.execute(
            text("SELECT COUNT(*) FROM airlines WHERE LOWER(AirlineName) LIKE :q"),
            {"q": like_query},
        ).scalar()

        total_pages = max(1, (count_result + per_page - 1) // per_page)

        result = db.session.execute(
            text("""
                SELECT al.AirlineID, al.AirlineName,
                       COUNT(a.AircraftID) AS TotalAircraft
                FROM airlines al
                LEFT JOIN aircraft a ON al.AirlineID = a.AirlineID
                WHERE LOWER(al.AirlineName) LIKE :q
                GROUP BY al.AirlineID, al.AirlineName
                ORDER BY al.AirlineName ASC
                LIMIT :limit OFFSET :offset
            """),
            {"q": like_query, "limit": per_page, "offset": offset},
        )

        for row in result:
            airline = dict(row._mapping)
            filtered_data.append(airline)

        return render_template(
            "partials/filtered_airlines.html",
            filtered_airlines=filtered_data,
            total_pages=total_pages,
            current_page=page,
            search_query=search_query,
        )

    return "Search type not supported", 400
