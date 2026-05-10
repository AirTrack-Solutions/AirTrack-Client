# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC




from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from zoneinfo import ZoneInfo
import pytz

from flask import has_app_context
from sqlalchemy import text
from extensions import db


def load_settings() -> Dict[str, str]:
    """Return all settings as a dict. Safe without app context (returns {})"""
    if not has_app_context():
        return {}
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT SettingKey, SettingValue FROM app_settings")
            ).fetchall()
        return {r._mapping["SettingKey"]: r._mapping["SettingValue"] for r in rows}
    except Exception:
        return {}

    """Resolve timezone safely; default to UTC on bad input."""
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.utc


def get_current_timezone() -> pytz.BaseTzInfo:
    """
    Fetch the current app timezone from DB.
    Returns UTC if missing or if no app context yet.
    """
    if not has_app_context():
        return pytz.utc
    try:
        with db.engine.connect() as conn:
            tz_name = conn.execute(
                text(
                    "SELECT SettingValue "
                    "FROM app_settings "
                    "WHERE SettingKey = 'timezone' "
                    "LIMIT 1"
                )
            ).scalar()
        return _tz_from_name(tz_name)
    except Exception:
        return pytz.utc


def convert_to_local(
    dt: Optional[datetime],
    tz_name: Optional[str] = "Australia/Sydney",
) -> Optional[datetime]:
    """
    Convert a datetime to the given local timezone.
    - If dt is naive, assume UTC.
    - If tz_name is None, use DB-defined timezone (safe fallback to UTC).
    """
    if dt is None:
        return None
    if not isinstance(dt, datetime):
        raise TypeError("convert_to_local expects a datetime object")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    tz = _tz_from_name(tz_name) if tz_name else get_current_timezone()
    try:
        return dt.astimezone(tz)
    except Exception:
        return dt


def get_current_theme() -> str:
    """Return the theme from cookie or 'default' (used only during requests)."""
    from flask import request  # imported here to avoid early import issues
    return request.cookies.get("airtrack-theme") or "default"


def _tz_from_name(tz_name: Optional[str]) -> pytz.BaseTzInfo:
    """Helper to resolve a tz name to a pytz timezone object, with fallback."""
    try:
        return pytz.timezone(tz_name or "")
    except Exception:
        return pytz.utc
