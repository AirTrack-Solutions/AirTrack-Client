# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC




# AirTrack package initializer
# Do NOT create a Flask app here.
# The integrity audit and runtime environment expect:
#     from app.app import app

"""
Marks the 'app' directory as a Python package.
Do not put application logic here.
All application creation happens in app/app.py.
"""

try:
    # Correct relative import
    from .app import app  # noqa: F401,E402
except Exception:
    # Safe fallback for integrity audits or partial loads
    app = None
