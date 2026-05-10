# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from extensions import db

class Aircraft(db.Model):
    __tablename__ = "aircraft"

    AircraftID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    AircraftType = db.Column(db.String(255), nullable=True)
    Manufacturer = db.Column(db.String(255), nullable=True)

    AirlineID = db.Column(
        db.Integer,
        db.ForeignKey("airlines.AirlineID"),
        nullable=True
    )

    # Optional fields (present in your DB)
    FirstSeen = db.Column(db.DateTime, nullable=True)
    LastSeen = db.Column(db.DateTime, nullable=True)
    Notes = db.Column(db.Text, nullable=True)
    ImagePath = db.Column(db.String(255), nullable=True)

    airline = db.relationship("Airline", backref="aircraft", lazy=True)

    def __repr__(self):
        return f"<Aircraft {self.AircraftType or 'Unknown'}>"
