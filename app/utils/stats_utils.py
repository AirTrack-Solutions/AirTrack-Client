# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC




# utils/stats_utils.py
import logging
from sqlalchemy import text
# ABSOLUTE import (flat layout)
from extensions import db


def get_all_airlines():
    """
    Return a list like [{'AirlineID': ..., 'AirlineName': ...}, ...] using
    SQLAlchemy to query the airlines table.
    """
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT AirlineID, AirlineName FROM airlines "
                    "ORDER BY AirlineName"
                )
            ).fetchall()
            return [{"AirlineID": r[0], "AirlineName": r[1]} for r in rows]
    except Exception as e:
        logging.error("❌ Error in get_all_airlines: %s", e)
        return []


def get_airtrack_stats():
    """
    Aggregate dashboard stats. All queries tolerate empty tables.
    """
    try:
        with db.engine.connect() as conn:
            total_aircraft = (
                conn.execute(
                    text("SELECT COUNT(*) FROM aircraft")
                ).scalar()
            )
            total_flights = (
                conn.execute(
                    text("SELECT COUNT(*) FROM flights")
                ).scalar()
            )
            total_airlines = (
                conn.execute(
                    text("SELECT COUNT(*) FROM airlines")
                ).scalar()
            )
            models_seen = (
                conn.execute(
                    text(
                        """
                SELECT COUNT(DISTINCT Aircraft_Type)
                FROM aircraft
                WHERE Aircraft_Type IS NOT NULL AND Aircraft_Type != ''
            """
                    )
                ).scalar()
                or 0
            )
            photos_logged = (
                conn.execute(
                    text(
                        """
                SELECT COUNT(*)
                FROM aircraft
                WHERE Aircraft_Image IS NOT NULL AND Aircraft_Image != ''
            """
                    )
                ).scalar()
                or 0
            )
            total_countries = (
                conn.execute(
                    text(
                        """
                SELECT COUNT(DISTINCT Country_of_Reg)
                FROM aircraft
                WHERE Country_of_Reg IS NOT NULL AND Country_of_Reg != ''
            """
                    )
                ).scalar()
                or 0
            )
            orphaned_aircraft = (
                conn.execute(
                    text(
                        """
                SELECT COUNT(*)
                FROM aircraft
                WHERE AirlineID IS NULL OR AirlineID = ''
            """
                    )
                ).scalar()
                or 0
            )
            # Count distinct ICAOs present in aircraft that also exist in the
            # airports table
            airports_logged = (
                conn.execute(
                    text(
                        """
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT ICAO
                    FROM (
                        SELECT Departure AS ICAO FROM aircraft
                        UNION
                        SELECT Arrival AS ICAO FROM aircraft
                    ) AS all_icaos
                    WHERE ICAO IS NOT NULL AND ICAO != ''
                    AND ICAO IN (SELECT ICAO FROM airports)
                ) AS valid_airports
            """
                    )
                ).scalar()
                or 0
            )
            return {
                "total_aircraft": total_aircraft,
                "total_flights": total_flights,
                "total_airlines": total_airlines,
                "models_seen": models_seen,
                "photos_logged": photos_logged,
                "total_countries": total_countries,
                "orphaned_aircraft": orphaned_aircraft,
                "airports_logged": airports_logged,
            }
    except Exception as e:
        logging.error("❌ Error fetching admin stats: %s", e)
        return {
            "total_aircraft": 0,
            "total_flights": 0,
            "total_airlines": 0,
            "models_seen": 0,
            "photos_logged": 0,
            "total_countries": 0,
            "orphaned_aircraft": 0,
            "airports_logged": 0,
        }
