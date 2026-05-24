"""
Database model helpers for AirTrack NOTAMs.

This file provides raw SQL for the first implementation pass. It does not
assume Flask-Migrate/Alembic is present. Later, this can be converted to a
SQLAlchemy ORM model if preferred.
"""

from __future__ import annotations

CREATE_NOTAMS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS notams (
  id                  INT AUTO_INCREMENT PRIMARY KEY,

  notam_id            VARCHAR(20) NOT NULL,
  series              CHAR(1),
  number              SMALLINT UNSIGNED,
  year                SMALLINT UNSIGNED,
  notam_type          ENUM('N','R','C') NOT NULL DEFAULT 'N',

  fir                 VARCHAR(4),
  q_code              VARCHAR(10),
  q_subject           VARCHAR(2),
  q_condition         VARCHAR(2),
  q_traffic           VARCHAR(5),
  q_purpose           VARCHAR(10),
  q_scope             VARCHAR(5),
  lower_limit_ft      MEDIUMINT UNSIGNED,
  upper_limit_ft      MEDIUMINT UNSIGNED,
  latitude            DECIMAL(8,5),
  longitude           DECIMAL(8,5),
  radius_nm           SMALLINT UNSIGNED,

  location_raw        VARCHAR(200),
  effective_from      DATETIME NOT NULL,
  effective_to        DATETIME,
  is_permanent        TINYINT(1) DEFAULT 0,
  schedule_raw        TEXT,
  text_raw            TEXT,
  lower_limit_raw     VARCHAR(20),
  upper_limit_raw     VARCHAR(20),

  category            ENUM(
                        'runway_closure',
                        'taxiway_closure',
                        'airspace_restriction',
                        'navaid_outage',
                        'gps_interference',
                        'obstacle_warning',
                        'weather_related',
                        'military_activity',
                        'airport_maintenance',
                        'procedural_change',
                        'lighting',
                        'fuel_services',
                        'bird_activity',
                        'other'
                      ) DEFAULT 'other',
  severity            ENUM('CRITICAL','SIGNIFICANT','MINOR','INFORMATIONAL')
                        NOT NULL DEFAULT 'MINOR',
  parse_confidence    ENUM('HIGH','MEDIUM','LOW') DEFAULT 'HIGH',

  status              ENUM('active','expired','cancelled','superseded')
                        NOT NULL DEFAULT 'active',
  superseded_by       VARCHAR(20),

  primary_icao        VARCHAR(4),

  source              VARCHAR(50) DEFAULT 'manual',
  raw_text            TEXT,
  checksum            CHAR(32),
  created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uq_notam_id (notam_id),
  UNIQUE KEY uq_checksum (checksum),
  INDEX idx_status_severity (status, severity),
  INDEX idx_primary_icao (primary_icao),
  INDEX idx_effective_from (effective_from),
  INDEX idx_effective_to (effective_to),
  INDEX idx_category (category),
  INDEX idx_fir (fir)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

CREATE_NOTAMS_ARCHIVE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS notams_archive LIKE notams;
"""

ALTER_NOTAMS_ARCHIVE_SQL = [
    "ALTER TABLE notams_archive ADD COLUMN archived_at DATETIME DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE notams_archive ADD COLUMN archive_reason VARCHAR(50);",
]


def install_notam_tables(db) -> None:
    """
    Create NOTAM tables.

    Expected db object:
      - Flask-SQLAlchemy db instance, or
      - object exposing session.execute() and session.commit()
    """
    db.session.execute(CREATE_NOTAMS_TABLE_SQL)
    db.session.execute(CREATE_NOTAMS_ARCHIVE_TABLE_SQL)

    for statement in ALTER_NOTAMS_ARCHIVE_SQL:
        try:
            db.session.execute(statement)
        except Exception:
            # Column may already exist. Safe to ignore for this scaffold.
            pass

    db.session.commit()
