# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# security/guards.py
from functools import wraps
from flask import request, jsonify, current_app
import os


def require_server(f):
    """Allow access only when running with AIRTRACK_ROLE=server."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        role = os.getenv("AIRTRACK_ROLE", "").lower()
        if role == "server":
            return f(*args, **kwargs)

        # Optional token check for remote tools
        token_env = os.getenv("AIRTRACK_SHUTDOWN_TOKEN")
        token_req = request.headers.get("X-AirTrack-Token") or request.args.get("token")
        if token_env and token_req and token_req == token_env:
            return f(*args, **kwargs)

        # Otherwise reject
        return (
            jsonify({"error": "forbidden", "detail": "Server elevation required"}),
            403,
        )
    return wrapper
