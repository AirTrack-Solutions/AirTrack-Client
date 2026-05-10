# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



import logging

from functools import lru_cache

from datetime import datetime

from extensions import db

from flask import Blueprint, jsonify, render_template, request, abort, url_for

from sqlalchemy import text


logger = logging.getLogger(__name__)
airports_bp = Blueprint('airports', __name__, url_prefix='/airports')


# ---------------------------------------------------------------------------
# Logged Airports List (Sortable)
# ---------------------------------------------------------------------------
@airports_bp.route('/logged')

def logged_airports():
    # Sorting input (default sort by ICAO)
    sort = request.args.get('sort', 'ICAO').upper()

    # Allowed sort columns
    valid_sort_cols = {'ICAO', 'AirportName', 'Country'}
    sort = sort if sort in valid_sort_cols else 'ICAO'

    result = db.session.execute(
        text(
            """
            SELECT DISTINCT ICAO
            FROM (
                SELECT Departure AS ICAO FROM aircraft
                UNION
                SELECT Arrival AS ICAO FROM aircraft
            ) AS all_icaos
            WHERE ICAO IS NOT NULL
            ORDER BY ICAO
            """
        )
    ).fetchall()

    icaos = [row[0] for row in result]
    airports = []

    for icao in icaos:
        row = db.session.execute(
            text(
                f"""
                SELECT ICAO, AirportName, iso_country AS Country
                FROM airports
                WHERE ICAO = :icao
                """
            ),
            {"icao": icao},
        ).fetchone()

        if row:
            airports.append(dict(row._mapping))

    # Python-side sorting using selected column
    airports.sort(key=lambda a: a.get(sort) or "")

    return render_template(
        "logged_airports.html",
        airports=airports,
        sort=sort,
    )


# ---------------------------------------------------------------------------
# Search (full)
# ---------------------------------------------------------------------------
@airports_bp.route("/search")

def search():
    query = request.args.get("q", "").strip().upper()
    if not query:
        return jsonify([])

    try:
        results = db.session.execute(
            text(
                """
                SELECT ICAO, IATA, AirportName, municipality,
                       iso_country, iso_region, type
                FROM airports
                WHERE (
                    UPPER(ICAO) LIKE :query_pattern
                    OR UPPER(IATA) LIKE :query_pattern
                    OR UPPER(AirportName) LIKE :query_pattern
                    OR UPPER(municipality) LIKE :query_pattern
                )
                AND ICAO IS NOT NULL
                ORDER BY
                    CASE
                        WHEN UPPER(ICAO) = :exact THEN 1
                        WHEN UPPER(ICAO) LIKE :query_pattern THEN 2
                        WHEN UPPER(IATA) LIKE :query_pattern THEN 3
                        ELSE 4
                    END,
                    AirportName
                LIMIT 10
                """
            ),
            {"exact": query, "query_pattern": f"{query}%"},
        ).fetchall()

        airports = []
        for row in results:
            airport = dict(row._mapping)
            city = airport["municipality"] or "Unknown City"

            if "(" in city and ")" in city:
                city = city.split("(")[1].split(")")[0]

            state = ""
            if airport["iso_region"] and "-" in airport["iso_region"]:
                state = airport["iso_region"].split("-")[1]

            airport["display_name"] = (
                f"{airport['AirportName']}, {city}, {state}, {airport['iso_country']}"
            )
            airport["code_display"] = f"{airport['ICAO']}" + (
                f" ({airport['IATA']})" if airport["IATA"] else ""
            )

            airports.append(airport)

        return jsonify(airports)

    except Exception as e:
        logger.error(f"Airport search error: {str(e)}")
        return jsonify([]), 500


# ---------------------------------------------------------------------------
# ICAO-only search autocomplete
# ---------------------------------------------------------------------------
@airports_bp.route('/search_icao_only')

def search_icao_only():
    query = request.args.get('q', '').strip().upper()
    if not query:
        return jsonify([])

    try:
        results = db.session.execute(
            text(
                """
                SELECT ICAO, CONCAT(AirportName, ' (', ICAO, ')') AS display_name
                FROM airports
                WHERE UPPER(ICAO) LIKE :query
                ORDER BY ICAO
                LIMIT 10
                """
            ),
            {"query": f"{query}%"},
        ).fetchall()

        airports = [{"ICAO": r.ICAO, "display_name": r.display_name} for r in results]
        return jsonify(airports)

    except Exception as e:
        logger.error(f"ICAO-only airport search error: {str(e)}")
        return jsonify([]), 500


# ---------------------------------------------------------------------------
# Airport Info Page
# ---------------------------------------------------------------------------
@airports_bp.get('/info/<icao>')
@airports_bp.get('/<icao>', endpoint='airport_info')

def airport_info(icao: str):
    try:
        icao = (icao or "").strip().upper()
        if not icao:
            abort(404)

        airport = (
            db.session.execute(
                text(
                    """
                    SELECT *
                    FROM airports
                    WHERE UPPER(TRIM(ICAO)) = :icao
                    LIMIT 1
                    """
                ),
                {"icao": icao},
            )
            .mappings()
            .fetchone()
        )

        if not airport:
            abort(404, description=f"Airport {icao} not found")

        aircraft_count = (
            db.session.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT Registration)
                    FROM flights
                    WHERE UPPER(TRIM(Departure)) = :icao
                       OR UPPER(TRIM(Arrival))   = :icao
                    """
                ),
                {"icao": icao},
            ).scalar()
            or 0
        )

        back_href = request.args.get("from") or "/reports?report=logged_airports"

        return render_template(
            "airport_info.html",
            airport=dict(airport),
            aircraft_count=aircraft_count,
            back_href=back_href,
        )

    except Exception:
        logger.exception("Airport info route failed")
        return "⚠️ Airport info error", 500


# ---------------------------------------------------------------------------
# Airport display helper (used by Jinja + autocomplete)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=100)

def airport_display_lookup(icao_code: str | None):
    if not icao_code:
        return "Unknown Airport"

    icao_code = icao_code.upper()

    try:
        row = db.session.execute(
            text(
                """
                SELECT AirportName, municipality, iso_country, iso_region
                FROM airports
                WHERE ICAO = :icao
                """
            ),
            {"icao": icao_code},
        ).fetchone()

        if not row:
            return f"{icao_code} Airport"

        data = dict(row._mapping)
        name = data.get("AirportName", "Unnamed Airport")
        city = data.get("municipality") or "Unknown City"

        if "(" in city and ")" in city:
            city = city.split("(")[1].split(")")[0]

        country = data.get("iso_country") or "Unknown Country"
        state = ""
        if data.get("iso_region") and "-" in data["iso_region"]:
            state = data["iso_region"].split("-")[1]

        return f"{name}, {city}, {state}, {country}"

    except Exception:
        logger.exception("Error in airport_display_lookup")
        return f"{icao_code} (Unavailable)"


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging():
    import os

    from logging.handlers import RotatingFileHandler

    if not os.path.exists("logs"):
        os.mkdir("logs")

    handler = RotatingFileHandler(
        "logs/airport_lookups.log", maxBytes=10240, backupCount=10
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s "
            "[in %(pathname)s:%(lineno)s]"
        )
    )
    handler.setLevel(logging.INFO)

    airport_logger = logging.getLogger(__name__)
    airport_logger.setLevel(logging.INFO)
    airport_logger.addHandler(handler)
    return airport_logger


logger = setup_logging()
