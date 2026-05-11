# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from datetime import datetime
import uuid
from extensions import db


class License(db.Model):
    __tablename__ = "licenses"

    LicenseID = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK to Customer
    CustomerID = db.Column(
        db.Integer,
        db.ForeignKey("customers.CustomerID"),
        nullable=False
    )

    # Product Type: standard / professional / institutional
    LicenseType = db.Column(db.String(50), nullable=False)

    # Unique generated key (UUIDv4)
    LicenseKey = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4())
    )

    # Status
    Active = db.Column(db.Boolean, default=True)
    CreatedAt = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to log activity
    activities = db.relationship(
        "LicenseActivity",
        backref="license",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<License {self.LicenseType} for Customer {self.CustomerID}>"
