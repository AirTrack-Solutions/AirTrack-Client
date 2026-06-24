# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

"""
First-run setup wizard.

Shown once after disclaimer acceptance when app_settings has no
'setup_complete' key. On submit, writes user choices to app_settings
and sets setup_complete=true so the gate never fires again.
"""

import logging
import os

import requests as http_requests
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from sqlalchemy import text

from extensions import db

log = logging.getLogger(__name__)

setup_bp = Blueprint("setup", __name__, url_prefix="/setup")

_EXEMPT = ("/setup", "/static", "/api/", "/disclaimer", "/billing/webhook", "/favicon.ico")


def setup_complete() -> bool:
    """Return True if the first-run wizard has been completed."""
    try:
        with db.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT SettingValue FROM app_settings "
                    "WHERE SettingKey='setup_complete' LIMIT 1"
                )
            ).scalar()
            return result == "true"
    except Exception:
        return True  # DB not ready — don't block


def check_setup():
    """before_request hook — redirect to wizard if setup not done."""
    path = request.path
    for prefix in _EXEMPT:
        if path.startswith(prefix):
            return None
    if not setup_complete():
        return redirect(url_for("setup.wizard"))
    return None


def _upsert(conn, key, value):
    conn.execute(
        text(
            "INSERT INTO app_settings (SettingKey, SettingValue) VALUES (:k, :v) "
            "ON DUPLICATE KEY UPDATE SettingValue = :v"
        ),
        {"k": key, "v": value},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------



@setup_bp.route("/rerun", methods=["GET"])
def rerun():
    """Clear setup_complete and restart the wizard. Accessible from Cockpit settings."""
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM app_settings WHERE SettingKey='setup_complete'")
            )
        log.info("setup_routes: setup_complete cleared — wizard will run on next request")
    except Exception as exc:
        log.error("setup_routes: failed to clear setup_complete: %s", exc)
    return redirect(url_for("setup.wizard"))

@setup_bp.route("/", methods=["GET"])
def wizard():
    """Render the first-run wizard."""
    edition = "Lite"
    aircraft_limit = 100
    try:
        if os.getenv("AIRTRACK_ROLE") == "client":
            from config.license import load_license
            lic = load_license()
            if lic:
                from config.license import EDITION_NAMES
                edition = EDITION_NAMES.get(lic.edition, lic.edition)
                aircraft_limit = None  # Licensed — no cap shown
    except Exception:
        pass
    return render_template(
        "setup_wizard.html",
        edition=edition,
        aircraft_limit=aircraft_limit,
    )


@setup_bp.route("/detect-ollama", methods=["GET"])
def detect_ollama():
    """Check whether Ollama is reachable on this machine."""
    try:
        r = http_requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            return jsonify({"detected": True})
    except Exception:
        pass
    return jsonify({"detected": False})


@setup_bp.route("/submit", methods=["POST"])
def submit():
    """Write wizard answers to app_settings and mark setup complete."""
    data = request.form

    # Validate timezone — fall back to UTC
    import pytz
    tz = data.get("timezone", "").strip()
    if tz not in pytz.all_timezones_set:
        tz = "UTC"

    home_airport = data.get("home_airport", "").strip().upper()[:4]

    support_reporting = data.get("support_reporting", "ask").strip()
    if support_reporting not in ("auto", "ask", "never"):
        support_reporting = "ask"

    mappings = {
        "FirstName":          data.get("first_name", "").strip(),
        "LastName":           data.get("last_name", "").strip(),
        "use_case":           data.get("use_case", "other"),
        "timezone":           tz,
        "home_airport":       home_airport,
        "country":            data.get("country", "").strip().upper(),
        "adsb_source":        data.get("adsb_source", "none"),
        "photo_storage":      data.get("photo_storage", "disk"),
        "registry_updates":   data.get("registry_updates", "automatic"),
        "aria_enabled":       data.get("aria_enabled", "false"),
        "support_reporting":  support_reporting,
        "setup_complete":     "true",
    }

    try:
        with db.engine.begin() as conn:
            for k, v in mappings.items():
                _upsert(conn, k, v)
        log.info("setup_routes: first-run wizard completed")
    except Exception as exc:
        log.error("setup_routes: failed to write settings: %s", exc)

    # Write support_prefs.json to AIRTRACK_HOME so app_updater.py can read
    # the preference without DB access (used by rollback event reporting)
    try:
        import json as _json, sys as _sys
        from pathlib import Path as _Path
        _home = _Path(os.environ.get("AIRTRACK_HOME") or (
            os.path.join(os.environ.get("ProgramData", "C:/ProgramData"), "AirTrack")
            if _sys.platform == "win32" else "/airtrack_data"
        ))
        _home.mkdir(parents=True, exist_ok=True)
        (_home / "support_prefs.json").write_text(
            _json.dumps({"mode": support_reporting}), encoding="utf-8"
        )
    except Exception as exc:
        log.warning("setup_routes: could not write support_prefs.json: %s", exc)

    return redirect(url_for("setup.done"))


@setup_bp.route("/done", methods=["GET"])
def done():
    """Completion screen — shown after submit."""
    # Read back what was saved so the checklist reflects reality
    settings = {}
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT SettingKey, SettingValue FROM app_settings")
            ).fetchall()
            settings = {r[0]: r[1] for r in rows}
    except Exception:
        pass
    return render_template("setup_done.html", settings=settings)
