-- Migration: 001_add_aircraft_owners
-- Description: Adds aircraft_owners table for tracking ownership history

CREATE TABLE IF NOT EXISTS aircraft_owners (
    OwnerID     INT AUTO_INCREMENT PRIMARY KEY,
    AircraftID  INT NOT NULL,
    AirlineID   INT NOT NULL,
    From_Date   DATE NOT NULL,
    To_Date     DATE NULL,
    Notes       VARCHAR(255) NULL,
    FOREIGN KEY (AircraftID) REFERENCES aircraft(AircraftID) ON DELETE CASCADE,
    FOREIGN KEY (AirlineID)  REFERENCES airlines(AirlineID)  ON DELETE CASCADE
);
