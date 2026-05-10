# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC




import os
import requests
import json

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def send_sales_notification(event_type: str, data: dict):
    """
    Sends a formatted sale notification to Discord.
    Automatically no-ops if no webhook URL defined.
    """

    if not DISCORD_WEBHOOK_URL:
        return  # Silently ignore if no webhook set

    try:
        # Discord requires content or embeds
        message = {
            "content": f"🛒 **AirTrack Sale Event:** `{event_type}`",
            "embeds": [
                {
                    "title": "Sale Details",
                    "color": 0x00FFAA,
                    "fields": [
                        {"name": k, "value": str(v), "inline": False}
                        for k, v in data.items()
                    ],
                }
            ],
        }

        headers = {"Content-Type": "application/json"}
        requests.post(DISCORD_WEBHOOK_URL, headers=headers, data=json.dumps(message))

    except Exception as e:
        # Don't let Discord issues crash anything
        print(f"❌ Discord notification failed: {e}")
