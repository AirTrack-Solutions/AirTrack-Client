CREATE TABLE IF NOT EXISTS aircraft_images (
    ImageID       INT          NOT NULL AUTO_INCREMENT,
    AircraftID    INT          NOT NULL,
    Registration  VARCHAR(20)  NOT NULL,
    Filename      VARCHAR(255) NOT NULL,
    Image_Number  TINYINT      NOT NULL DEFAULT 2,
    Uploaded_At   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ImageID),
    KEY idx_aircraft_images_aircraft_id (AircraftID),
    KEY idx_aircraft_images_registration (Registration),
    CONSTRAINT fk_aircraft_images_aircraft
        FOREIGN KEY (AircraftID) REFERENCES aircraft (AircraftID)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
