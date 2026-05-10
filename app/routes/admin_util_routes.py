# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

import pytz

from extensions import db

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from sqlalchemy import text

admin_util_bp = Blueprint('admin_util', __name__, url_prefix='/admin_util')


# -------- Update First_Sighted --------

def update_first_sighted():
    try:
        update_query = """
            UPDATE aircraft a
            JOIN (
                SELECT Registration, MIN(Timestamp) AS first_ts
                FROM flights
                GROUP BY Registration
            ) f ON a.Registration = f.Registration
            SET a.First_Sighted = f.first_ts
            WHERE a.First_Sighted IS NULL
            OR a.First_Sighted = '0000-00-00 00:00:00'
        """
        result = db.session.execute(text(update_query))
        db.session.commit()
        affected = result.rowcount
        flash(f"✅ First_Sighted updated for {affected} aircraft.", "success")
    except Exception as e:
        flash(f"❌ Error updating First_Sighted: {e}", "danger")
    return redirect(url_for("admin_panel"))


# -------- View Settings Page --------
@admin_util_bp.route("/settings")

def view_settings():
    try:
        current_db = db.session.execute(text("SELECT DATABASE();")).scalar()
        current_app.logger.debug(f"Current database: {current_db}")

        host_result = db.session.execute(text("SELECT @@hostname;")).scalar()
        current_app.logger.debug(f"Connected to MariaDB host: {host_result}")

        tables_result = db.session.execute(text("SHOW TABLES;")).fetchall()
        tables = [row[0] for row in tables_result]
        current_app.logger.debug(f"Tables in current DB: {tables}")

        tz_result = db.session.execute(
            text("SELECT SettingValue FROM app_settings WHERE SettingKey = :key"),
            {"key": "timezone"},
        ).fetchone()
        current_timezone = tz_result[0] if tz_result else "UTC"
        current_app.logger.debug(f"Current timezone loaded: {current_timezone}")

        return render_template(
            "admin_settings.html",
            current_timezone=current_timezone,
            tables=tables,
            database=current_db,
        )
    except Exception as e:
        current_app.logger.error(f"Settings load error: {str(e)}")
        flash("❌ Error loading settings", "danger")
        return redirect(url_for("admin_panel"))


# -------- Save Updated Timezone --------
@admin_util_bp.route("/update_timezone", methods=["POST"])

def update_timezone():
    try:
        new_timezone = request.form.get("timezone", "").strip()

        if not new_timezone:
            flash("❌ No timezone selected.", "danger")
            return redirect(url_for("admin_util.view_settings"))

        if new_timezone not in pytz.all_timezones:
            flash(f"❌ Invalid timezone: {new_timezone}", "danger")
            return redirect(url_for("admin_util.view_settings"))

        db.session.execute(
            text(
                """
                INSERT INTO app_settings (SettingKey, SettingValue)
                VALUES (:key, :val)
                ON DUPLICATE KEY UPDATE SettingValue = VALUES(SettingValue)
                """
            ),
            {"key": "timezone", "val": new_timezone},
        )
        db.session.commit()
        flash(f"✅ Timezone updated to {new_timezone}.", "success")
    except Exception as e:
        flash(f"❌ Error updating timezone: {e}", "danger")

    return redirect(url_for("admin_util.view_settings"))
