"""
AirTrack BOM optional module.

This package is intentionally optional.
Removing this folder should not break AirTrack Logbook.
"""

try:
    from .routes import bom_bp
except Exception:
    bom_bp = None
