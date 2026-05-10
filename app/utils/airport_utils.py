# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from __future__ import annotations

import re

from functools import lru_cache

from typing import Optional, Tuple

from extensions import db

from sqlalchemy import text

from utils.logger import logger  # your existing logger
_CODE_RE = re.compile(
    r"^[A-Za-z]{3,4}$"
)  # classic tokens; others can still be idents in DB


def _clean_city(municipality: Optional[str]) -> str:
    if not municipality:
        return "Unknown City"
    s = str(municipality).strip()
    if '(' in s and ')' in s:
        try:
            return s.split('(', 1)[1].split(')', 1)[0].strip() or s
        except Exception:
            return s
    return s or "Unknown City"


def _state_from_region(iso_region: Optional[str]) -> str:
    if not iso_region:
        return ''
    parts = str(iso_region).split('-', 1)
    return parts[1] if len(parts) == 2 else ''


def _build_label(
    name: Optional[str],
    municipality: Optional[str],
    iso_country: Optional[str],
    iso_region: Optional[str],
) -> str:
    name_ = (name or "Unnamed Airport").strip()
    city_ = _clean_city(municipality)
    state_ = _state_from_region(iso_region)
    country_ = (iso_country or "Unknown Country").strip()
    parts = [name_, city_]
    if state_:
        parts.append(state_)
    parts.append(country_)
    return ", ".join([p for p in parts if p])


@lru_cache(maxsize=4096)

def _lookup_by_code_anylen(code_norm: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Try both ICAO and IATA (case-insensitive, trimmed). No length restriction.
    Returns (AirportName, municipality, iso_country, iso_region) or None.
    """
    sql = text(
        """
        SELECT AirportName, municipality, iso_country, iso_region
        FROM airports
        WHERE UPPER(TRIM(ICAO)) = :code COLLATE utf8mb4_uca1400_ai_ci
            OR UPPER(TRIM(IATA)) = :code COLLATE utf8mb4_uca1400_ai_ci
        LIMIT 1
    """
    )
    row = db.session.execute(sql, {"code": code_norm}).fetchone()
    if not row:
        return None
    try:
        return (
            row.AirportName,
            row.municipality,
            row.iso_country,
            row.iso_region,
        )
    except Exception:
        return (row[0], row[1], row[2], row[3])  # type: ignore[index]


@lru_cache(maxsize=100)

def format_airport_display(value: Optional[str]) -> str:
    """
    Human-friendly airport label resolver across 200/153/clients.
    - Empty/blank -> "Unknown Airport"
    - Token-like 3/4 letters -> ICAO or IATA lookup (case-insensitive)
    - Other idents (e.g., 'US-11706') -> still try lookup; else return literal
    - Not found: if code-like, return 'CODE Airport'; otherwise return literal text
    - DB error -> 'CODE (Unavailable)' or 'Airport (Unavailable)'
    """
    if not value:
        logger.debug("Empty ICAO/IATA value provided to airport display")
        return "Unknown Airport"
    raw = str(value).strip()
    if not raw:
        return "Unknown Airport"
    code_norm = raw.upper()
    try:
        rec = _lookup_by_code_anylen(code_norm)
        if rec:
            label = _build_label(*rec)
            logger.debug(f"Resolved airport {code_norm}: {label}")
            return label
        if _CODE_RE.match(raw):
            logger.warning("Airport not found in database for code: %s", code_norm)
            return f"{code_norm} Airport"
        else:
            logger.info(f"No match for '{raw}', returning literal text")
            return raw
    except Exception as e:
        logger.error(f"Database error looking up airport '{raw}': {e}")
        token = code_norm if raw else "Airport"
        return f"{token} (Unavailable)"
