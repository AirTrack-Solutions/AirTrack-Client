# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ('Subhuti'). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# routes/admin_routes.py

from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    jsonify,
    current_app,
)

from sqlalchemy import text

from extensions import db

import os

import logging

from datetime import datetime

# ---------------------------------------------------------------------------
# Update check — runs once when blueprint loads, client only
# ---------------------------------------------------------------------------
try:
    if os.getenv('AIRTRACK_ROLE', 'client').lower() == 'client':
        from utils.airtrack_updater import check_for_updates as _check_for_updates
        _update_check = _check_for_updates()
        update_available = not _update_check.get('up_to_date', True)
    else:
        update_available = None
except Exception:
    update_available = None


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _endpoint_url(name: str) -> str:
    """
    Safely return url_for(name) or an empty string if the endpoint doesn't exist.
    Prevents template crashes when routes differ between server/client builds.
    """
    try:
        return url_for(name)
    except Exception:
        return ""


@admin_bp.route("/")

def admin_dashboard():

    # -----------------------------
    # Stats
    # -----------------------------

    def _get_airtrack_stats():
        try:
            with db.engine.connect() as conn:
                total_aircraft = conn.execute(
                    text("SELECT COUNT(*) FROM aircraft")
                ).scalar()

                total_flights = conn.execute(
                    text("SELECT COUNT(*) FROM flights")
                ).scalar()

                total_airlines = conn.execute(
                    text("SELECT COUNT(*) FROM airlines")
                ).scalar()

                models_seen = conn.execute(
                    text(
                        """
                        SELECT COUNT(DISTINCT Aircraft_Type)
                        FROM aircraft
                        WHERE Aircraft_Type IS NOT NULL
                        AND Aircraft_Type != ''
                        """
                    )
                ).scalar()

                photos_logged = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM aircraft
                        WHERE Aircraft_Image IS NOT NULL
                        AND Aircraft_Image != ''
                        """
                    )
                ).scalar()

                total_countries = conn.execute(
                    text(
                        """
                        SELECT COUNT(DISTINCT Country_of_Reg)
                        FROM aircraft
                        WHERE Country_of_Reg IS NOT NULL
                        AND Country_of_Reg != ''
                        """
                    )
                ).scalar()

                orphaned_aircraft = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM aircraft
                        WHERE AirlineID IS NULL OR AirlineID = ''
                        """
                    )
                ).scalar()

                airports_logged = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM (
                            SELECT DISTINCT ICAO
                            FROM (
                                SELECT Departure AS ICAO FROM aircraft
                                UNION
                                SELECT Arrival AS ICAO FROM aircraft
                            ) AS all_icaos
                            WHERE ICAO IS NOT NULL
                            AND ICAO IN (SELECT ICAO FROM airports)
                        ) AS valid_airports
                        """
                    )
                ).scalar() or 0

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
            logging.error(f"❌ Error fetching admin stats: {e}")
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

    stats = _get_airtrack_stats()

    # -----------------------------
    # Backup file list
    # -----------------------------
    backup_dir = os.path.join(
        os.path.dirname(current_app.root_path),
        "app",
        "backups",
    )

    try:
        files = []

        if os.path.isdir(backup_dir):
            for f in os.listdir(backup_dir):
                if f.endswith(".sql"):
                    p = os.path.join(backup_dir, f)

                    files.append(
                        {
                            "name": f,
                            "modified": datetime.fromtimestamp(
                                os.path.getmtime(p)
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

        backup_files = sorted(
            files,
            key=lambda x: x["modified"],
            reverse=True,
        )

    except Exception as e:
        logging.error(f"❌ Error listing backup files: {e}")
        backup_files = []

    # -----------------------------
    # Role / feature flags
    # -----------------------------
    is_server = os.getenv('AIRTRACK_ROLE', 'client').lower() == 'server'

    show_update_button = (
        update_available is True
        and 'admin_tools.check_updates' in current_app.view_functions
        and 'admin_tools.run_updater' in current_app.view_functions
    )

    show_commit_push = (
        is_server
        and 'admin_tools.git_commit' in current_app.view_functions
        and 'admin_tools.git_push' in current_app.view_functions
    )

    AIRTRACK_SYNC_USER = os.getenv('AIRTRACK_SYNC_USER', '').lower()

    show_sync_button = AIRTRACK_SYNC_USER == 'trevor' and (
        'admin_tools.run_file_sync' in current_app.view_functions
    )

    # -----------------------------
    # Safe endpoint URLs
    # -----------------------------
    airtrack_urls = {
        "git_commit": _endpoint_url('admin_tools.git_commit'),
        "git_push": _endpoint_url('admin_tools.git_push'),
        "check_updates": _endpoint_url('admin_tools.check_updates'),
        "run_updater": _endpoint_url('admin_tools.run_updater'),
        "housekeeping": _endpoint_url('admin_tools.housekeeping'),
    }

    return render_template(
        'admin.html',
        stats=stats,
        backup_files=backup_files,
        show_update_button=show_update_button,
        show_sync_button=show_sync_button,
        show_commit_push=show_commit_push,
        AIRTRACK_SYNC_USER=AIRTRACK_SYNC_USER,
        airtrack_urls=airtrack_urls,
        is_server=is_server,
    )


@admin_bp.route('/settings', methods=['GET'])

def admin_settings():
    # Settings live in the admin.html modal — redirect there
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/save_settings', methods=['POST'])

def save_settings():
    try:
        data = request.get_json(silent=True) or {}
        first_name = (data.get("first_name") or request.form.get("first_name", "")).strip()
        last_name = (data.get("last_name") or request.form.get("last_name", "")).strip()
        callsign = (data.get("callsign") or request.form.get("callsign", "")).strip()

        for key, value in [
            ("FirstName", first_name),
            ("LastName", last_name),
            ("Callsign", callsign),
        ]:
            db.session.execute(
                text(
                    """
                    INSERT INTO app_settings (SettingKey, SettingValue)
                    VALUES (:key, :value)
                    ON DUPLICATE KEY UPDATE
                        SettingValue = VALUES(SettingValue)
                    """
                ),
                {"key": key, "value": value},
            )

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        current_app.logger.exception('save_settings failed')
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/update_app_settings', methods=['POST'])

def update_app_settings():

    try:
        data = request.get_json() or {}

        theme = (data.get("theme") or 'default').strip()
        timezone = (data.get("timezone") or '').strip()

        with db.engine.begin() as conn:
            for k, v in (
                ('timezone', timezone),
                ('Theme', theme),
            ):
                conn.execute(
                    text(
                        """
                        INSERT INTO app_settings (SettingKey, SettingValue)
                        VALUES (:k, :v)
                        ON DUPLICATE KEY UPDATE
                            SettingValue = VALUES(SettingValue)
                        """
                    ),
                    {'k': k, 'v': v},
                )

        return jsonify({"success": True})

    except Exception as e:
        current_app.logger.exception('update_app_settings failed')
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/user_guide')

def user_guide():
    return render_template('user_guide.html')
