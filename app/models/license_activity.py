# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from datetime import datetime
from extensions import db


class LicenseActivity(db.Model):
    __tablename__ = "license_activity"

    ActivityID = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK to licenses table
    LicenseID = db.Column(
        db.Integer,
        db.ForeignKey("licenses.LicenseID"),
        nullable=False
    )

    # Type of logged event (example: created/valid/invalid/etc.)
    EventType = db.Column(db.String(100), nullable=False)

    # Optional text details or status message
    EventDetails = db.Column(db.Text, nullable=True)

    CreatedAt = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LicenseActivity {self.EventType} for License {self.LicenseID}>"
