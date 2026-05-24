"""
AirTrack NOTAM Module

Optional module scaffold for NOTAM ingestion, parsing, classification,
API exposure, and later Logbook/Kiosk display integration.
"""

from __future__ import annotations

MODULE_NAME = "notams"
MODULE_TITLE = "NOTAM Awareness"
MODULE_DESCRIPTION = (
    "Receives, parses, classifies, and exposes NOTAM information for "
    "Logbook, Kiosk, Overwatch Owl, Groundhog Gus, and Ledger Goblin."
)


def register_optional_module(app):
    """
    Register the NOTAM module with a Flask app.

    This is intentionally defensive. If imports fail, AirTrack should continue
    running without the NOTAM module.
    """
    try:
        from .routes import notams_bp
        from .api import notams_api_bp

        app.register_blueprint(notams_bp)
        app.register_blueprint(notams_api_bp)
        app.logger.info("NOTAM module registered")
        return True
    except Exception as exc:
        try:
            app.logger.warning("NOTAM module unavailable: %s", exc)
        except Exception:
            pass
        return False
