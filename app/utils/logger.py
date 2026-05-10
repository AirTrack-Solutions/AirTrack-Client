# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



# utils/logger.py
import logging
import os
import sys
from datetime import datetime
import pytz
from flask import current_app
# Set up standard stream logger
logger = logging.getLogger("AirTrack")
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
# Custom admin activity log function


def log_admin_action(message):
    try:
        log_path = os.path.join(
            current_app.root_path,
            "logs",
            "admin_activity.log",
        )
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        tz = pytz.timezone("Australia/Sydney")
        timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {message}\n")
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")
