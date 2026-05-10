# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



# AirTrack Logging Utilities
# --------------------------
# Provides log_admin_action() for admin tools/actions.

import os
import logging
from flask import current_app


def _ensure_admin_log_file():
    """
    Ensure the admin activity log exists and return its full path.
    """
    try:
        log_dir = os.path.join(current_app.root_path, "logs")
        os.makedirs(log_dir, exist_ok=True)

        log_path = os.path.join(log_dir, "admin_activity.log")

        # Touch file if missing
        if not os.path.exists(log_path):
            with open(log_path, "a"):
                pass

        return log_path
    except Exception:
        # Fallback: safe temp location
        return "/tmp/airtrack_admin_activity.log"


def log_admin_action(message: str):
    """
    Append an admin action line to admin_activity.log.

    The file receives ISO8601 timestamps in Sydney timezone.
    """
    try:
        log_path = _ensure_admin_log_file()

        logger = logging.getLogger("airtrack.admin")
        logger.info(message)

        # Also append directly for redundancy
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(message + "\n")

    except Exception as e:
        # Last-resort stderr logging
        print(f"[admin log error] {e}")
