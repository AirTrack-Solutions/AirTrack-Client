-- Migration: 004_add_airline_name_snapshot
-- Description: Adds airline_name_snapshot to aircraft_owners for historical name tracking

ALTER TABLE aircraft_owners
    ADD COLUMN IF NOT EXISTS airline_name_snapshot VARCHAR(255) NULL AFTER AirlineID;
