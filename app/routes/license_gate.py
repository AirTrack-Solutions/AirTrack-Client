# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# routes/license_gate.py
#
# License kill-switch gate.
#
# Every request is checked before any page renders (mirrors
# disclaimer_routes.py / setup_routes.py's existing before_request gates).
# If app_settings.license_revoked is 'true', every non-exempt route is
# redirected to a standalone "license revoked" screen instead of the
# normal app.
#
# The flag itself is written from two places, both outside this file:
#   - app/woodland/mangy_marmot.py's _send_meerkat_heartbeat() — the
#     recurring channel; runs every 5 minutes regardless of anything the
#     customer does, so this is what reliably catches a revocation that
#     happens mid-lifetime (writes via raw pymysql — that file runs in
#     the scheduler container, outside Flask app context).
#   - app/modules/meerkat/meerkat_client.py's register() — a secondary,
#     immediate check on manual opt-in/re-opt-in (writes via SQLAlchemy,
#     since that call already runs inside a Flask request).
# Both write the same app_settings.license_revoked key, so whichever
# fires first is what this gate sees. It also clears itself back to
# 'false' automatically the next time a heartbeat gets ok:true — i.e. the
# next successful tick after Wombat's /restore is called — with no local
# action required.
#
# There is no "remind me later" and no dismiss button on the lock screen
# itself, matching the disclaimer gate's decline behaviour.

import logging

from flask import Blueprint, redirect, render_template, request, url_for
from sqlalchemy import text

from extensions import db

log = logging.getLogger(__name__)

license_bp = Blueprint("license_gate", __name__)

# Routes that are always allowed — no license check required. Must include
# /static and /api/ so heartbeat/asset traffic can never be self-blocked,
# and /license-revoked itself so the lock screen can actually render.
_EXEMPT_PREFIXES = (
    "/license-revoked",
    "/static",
    "/api/",
    "/billing/webhook",
    "/favicon.ico",
)


def license_is_revoked() -> bool:
    """Return True if app_settings.license_revoked is currently 'true'."""
    try:
        with db.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT SettingValue FROM app_settings "
                    "WHERE SettingKey='license_revoked' LIMIT 1"
                )
            ).scalar()
            return result == "true"
    except Exception:
        return False  # DB not ready — don't block; disclaimer/setup gates cover this case too


def check_license_gate():
    """
    before_request hook — called before every request, ahead of the
    disclaimer and setup gates (registered first in app.py) so a revoked
    install is stopped before it can even reach those.
    """
    path = request.path

    for prefix in _EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return None

    if license_is_revoked():
        return redirect(url_for("license_gate.show_revoked"))

    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@license_bp.route("/license-revoked", methods=["GET"])
def show_revoked():
    return render_template("license_revoked.html"), 200
