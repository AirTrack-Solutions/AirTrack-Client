# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



# utils/timezone_utils.py
import os
from datetime import date, datetime
import pytz
from utils.settings_utils import load_settings  # already in your project
_DEFAULT_TZ = os.environ.get("AIRTRACK_TZ", "Australia/Sydney")


def _local_tz():
    """Return the site's configured TZ, falling back to env/default."""
    try:
        settings = load_settings()
        tz_name = settings.get("Timezone", _DEFAULT_TZ) or _DEFAULT_TZ
        return pytz.timezone(tz_name)
    except Exception:  # settings table may not exist yet
        return pytz.timezone(_DEFAULT_TZ)


_LOCAL = _local_tz()


def convert_to_local(dt):
    """
    Convert a naive (assumed-UTC) or aware datetime to the local zone.
    Returns None if dt is falsy.
    """
    if not dt:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime.combine(dt, datetime.min.time())
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(_LOCAL)
