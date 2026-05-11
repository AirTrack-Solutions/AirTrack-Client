# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# utils/discord_utils.py

import os
import requests
import datetime

WEBHOOK_URL = os.getenv("DISCORD_SALES_WEBHOOK_URL", "")


def format_license_embed(data: dict) -> dict:
    """
    Convert license purchase data into a Discord embed structure.
    """

    license_type = data.get("license_type", "Unknown")
    amount = data.get("amount", "0.00 AUD")
    email = data.get("email", "Unknown")
    invoice = data.get("invoice", "N/A")

    return {
        "username": "AirTrack Sales Bot",
        "avatar_url": "https://www.airtracksolutions.com/static/img/airtrack-logo.png",
        "embeds": [
            {
                "title": f"💳 {license_type} License Purchased",
                "color": 0x00FFAA,
                "fields": [
                    {"name": "📦 License", "value": license_type, "inline": True},
                    {"name": "💰 Amount", "value": amount, "inline": True},
                    {"name": "👤 Customer", "value": email, "inline": False},
                    {"name": "🧾 Invoice", "value": invoice, "inline": False},
                ],
                "footer": {
                    "text": f"AirTrack — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                }
            }
        ]
    }


def send_sales_notification(event_type: str, data: dict) -> None:
    """
    Send a sales notification to Discord as a rich embed.
    """

    if not WEBHOOK_URL:
        print("⚠ No Discord webhook URL configured.")
        return

    try:
        payload = format_license_embed(data)
        response = requests.post(WEBHOOK_URL, json=payload)

        if response.status_code >= 400:
            print("⚠ Discord webhook failed:", response.text)

    except Exception as e:
        print("⚠ Error sending Discord notification:", e)
