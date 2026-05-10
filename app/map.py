# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# map.py
from app import app
with app.app_context():
    for rule in app.url_map.iter_rules():
        print(rule)
