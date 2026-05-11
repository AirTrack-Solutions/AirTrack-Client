# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from datetime import datetime
from extensions import db


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    full_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    licenses = db.relationship(
        "License",
        backref="customer",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Customer {self.email}>"


class License(db.Model):
    __tablename__ = "licenses"

    id = db.Column(db.Integer, primary_key=True)

    license_key = db.Column(db.String(64), unique=True, nullable=False)
    license_type = db.Column(
        db.Enum("standard", "professional", "institutional", name="license_types"),
    )

    stripe_session_id = db.Column(db.String(255))
    stripe_payment_intent = db.Column(db.String(255))

    purchase_amount = db.Column(db.Numeric(10, 2))
    purchase_currency = db.Column(db.String(10), default="AUD")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    activity = db.relationship(
        "LicenseActivity",
        backref="license",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<License {self.license_key}>"


class LicenseActivity(db.Model):
    __tablename__ = "license_activity"

    id = db.Column(db.Integer, primary_key=True)
    license_id = db.Column(db.Integer, db.ForeignKey("licenses.id"), nullable=False)

    event_type = db.Column(
        db.Enum(
            "created",
            "invoice_sent",
            "discord_notified",
            "webhook_received",
            "validated",
            "error",
        ),
        nullable=False,
    )

    event_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LicenseActivity {self.event_type} for {self.license_id}>"
