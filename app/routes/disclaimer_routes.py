# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# routes/disclaimer_routes.py
#
# Mandatory safety disclaimer gate.
#
# Every request is checked before any page renders. If the browser session
# has not accepted the disclaimer within the last 6 months, the user is
# redirected to /disclaimer regardless of what they requested.
#
# Acceptance is stored in two places:
#   1. Flask session cookie — fast check on every request
#   2. disclaimer_acceptance DB table — permanent audit log
#
# The disclaimer must be re-accepted every 6 months.
# There is no "remind me later". Declining closes the app.
#
# DISCLAIMER_VERSION must be bumped any time the text changes materially.
# Bumping the version resets acceptance for all existing sessions.

import logging
from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import text
from extensions import db

log = logging.getLogger(__name__)

disclaimer_bp = Blueprint("disclaimer", __name__)

DISCLAIMER_VERSION = "1.0"
DISCLAIMER_EXPIRY_DAYS = 183  # ~6 months

# Routes that are always allowed — no disclaimer required
_EXEMPT_PREFIXES = (
    "/disclaimer",
    "/setup",
    "/static",
    "/api/",
    "/billing/webhook",
)


def disclaimer_accepted_in_session() -> bool:
    """Check if the current browser session has a valid, unexpired acceptance."""
    v = session.get("disclaimer_version")
    ts = session.get("disclaimer_accepted_at")
    if not v or not ts or v != DISCLAIMER_VERSION:
        return False
    try:
        accepted_at = datetime.fromisoformat(ts)
        expires_at = accepted_at + timedelta(days=DISCLAIMER_EXPIRY_DAYS)
        return datetime.now(timezone.utc) < expires_at
    except Exception:
        return False


def check_disclaimer():
    """
    before_request hook — called before every request.
    Redirects to /disclaimer if acceptance is missing or expired.
    """
    path = request.path

    # Always allow exempt paths
    for prefix in _EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return None

    if not disclaimer_accepted_in_session():
        # Store intended destination so we can redirect after acceptance
        session["disclaimer_next"] = request.url
        return redirect(url_for("disclaimer.show_disclaimer"))

    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@disclaimer_bp.route("/disclaimer", methods=["GET"])
def show_disclaimer():
    return render_template("disclaimer.html", version=DISCLAIMER_VERSION)


@disclaimer_bp.route("/disclaimer/accept", methods=["POST"])
def accept_disclaimer():
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=DISCLAIMER_EXPIRY_DAYS)

    # Write to session
    session["disclaimer_version"] = DISCLAIMER_VERSION
    session["disclaimer_accepted_at"] = now.isoformat()
    session.permanent = True

    # Write to DB audit log (best-effort — don't crash if DB is unreachable)
    try:
        db.session.execute(
            text(
                "INSERT INTO disclaimer_acceptance "
                "(disclaimer_version, accepted_at, expires_at, ip_address, user_agent) "
                "VALUES (:ver, :accepted, :expires, :ip, :ua)"
            ),
            {
                "ver": DISCLAIMER_VERSION,
                "accepted": now.strftime("%Y-%m-%d %H:%M:%S"),
                "expires": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                "ip": request.remote_addr,
                "ua": (request.user_agent.string or "")[:500],
            },
        )
        db.session.commit()
        log.info(f"disclaimer_routes: accepted v{DISCLAIMER_VERSION} from {request.remote_addr}")
    except Exception as exc:
        log.warning(f"disclaimer_routes: DB log failed (session still set): {exc}")

    # Redirect to intended destination or home
    next_url = session.pop("disclaimer_next", None) or url_for("index")
    return redirect(next_url)


@disclaimer_bp.route("/disclaimer/decline", methods=["POST"])
def decline_disclaimer():
    """User declined. Show a final message — they should close the window."""
    return render_template("disclaimer_declined.html"), 200
