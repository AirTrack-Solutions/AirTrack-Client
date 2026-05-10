# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



from extensions import db


class Airline(db.Model):
    __tablename__ = "airlines"

    AirlineID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    AirlineName = db.Column(db.String(255), nullable=False)
    Country = db.Column(db.String(255), nullable=True)
    IATA = db.Column(db.String(10), nullable=True)
    Callsign = db.Column(db.String(255), nullable=True)
    Last_Updated = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Airline {self.AirlineName}>"
