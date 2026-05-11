# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# app/config/billing_config.py

billing_plans = {
    "ATS": {
        "name": "Standard License",
        "price_id": "price_xxx_standard",   # TODO replace after creating in Stripe dashboard
        "amount": 2900,                     # cents
        "duration_months": 12,
    },
    "ATP": {
        "name": "Professional License",
        "price_id": "price_xxx_professional",
        "amount": 7900,
        "duration_months": 12,
    },
    "ATI": {
        "name": "Institutional License",
        "price_id": "price_xxx_institutional",
        "amount": 14900,
        "duration_months": 12,
    }
}
