# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


from __future__ import annotations
# Tiny built-in map so pages render nicely right now.
# Add more as you like, or swap to a DB query later.
_AIRPORTS = {
    "YSBK": "Sydney Bankstown Airport, Australia",
    "YBAF": "Brisbane Archerfield Airport, Australia",
    "YMEN": "Essendon Fields Airport, Australia",
    "YSSY": "Sydney Kingsford Smith International, Australia",
}

def lookup_airport(code):
    if not code:
        return None
    code = str(code).strip().upper()
    return _AIRPORTS.get(code)
