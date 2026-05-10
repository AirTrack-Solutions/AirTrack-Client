# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from __future__ import annotations
from functools import lru_cache
from typing import Mapping, Optional
from sqlalchemy import text
from flask import Flask
from extensions import db
# Try to find a “best” display from any common column layouts.
_NAME_KEYS = (
    "AirportName",
    "Name",
    "airport_name",
    "Airport",
    "AirportFullName",
    "Airport_Name",
)
_COUNTRY_KEYS = ("Country", "country", "country_name", "CountryName")


def _pick(
    mapping: Mapping[str, object],
    keys: tuple[str, ...],
) -> Optional[str]:
    for k in keys:
        if k in mapping and mapping[k]:
            v = str(mapping[k]).strip()
            if v:
                return v
    return None


@lru_cache(maxsize=4096)
def _lookup_display(code: str) -> str:
    c = (code or "").strip().upper()
    if not c:
        return ""
    try:
        # 1) Try a precise, minimal SELECT first (fast path)
        with db.engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    SELECT AirportName, Country
                    FROM airports
                    WHERE ICAO = :c OR IATA = :c
                    LIMIT 1
                    """
                    ),
                    {"c": c},
                )
                .mappings()
                .fetchone()
            )
        if row:
            name = _pick(row, _NAME_KEYS) or c
            country = _pick(row, _COUNTRY_KEYS) or ""
            return f"{name}, {country}" if country else name
    except Exception:
        # 2) Fallback: SELECT * and pick whatever columns exist
        try:
            with db.engine.connect() as conn:
                row = (
                    conn.execute(
                        text(
                            """
                    SELECT *
                    FROM airports
                    WHERE ICAO = :c OR IATA = :c
                    LIMIT 1
                    """
                        ),
                        {"c": c},
                    )
                    .mappings()
                    .fetchone()
                )
            if row:
                name = _pick(row, _NAME_KEYS) or c
                country = _pick(row, _COUNTRY_KEYS) or ""
                return f"{name}, {country}" if country else name
        except Exception:
            pass
    # Couldn’t resolve -> return the raw code
    return c


def airport(value) -> str:
    if value is None:
        return ""
    return _lookup_display(str(value))


def register_filters(app: Flask):
    app.add_template_filter(airport, name="airport_display")
