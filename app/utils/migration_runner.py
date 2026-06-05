# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

import logging
from pathlib import Path
from sqlalchemy import text

logger = logging.getLogger(__name__)

import sys as _sys
if getattr(_sys, 'frozen', False):
    MIGRATIONS_DIR = Path(_sys.executable).parent / '_internal' / 'app' / 'migrations'
    SCHEMA_PATH    = Path(_sys.executable).parent / '_internal' / 'app' / 'db' / 'schema.sql'
else:
    MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / 'migrations'
    SCHEMA_PATH    = Path(__file__).resolve().parent.parent / 'db' / 'schema.sql'
del _sys


def _strip_leading_comments(s):
    lines = s.strip().splitlines()
    while lines and lines[0].strip().startswith("--"):
        lines.pop(0)
    return "\n".join(lines).strip()


def _run_sql_file(db, path, label):
    sql = path.read_text(encoding="utf-8")
    statements = [
        cleaned for stmt in sql.split(";")
        if (cleaned := _strip_leading_comments(stmt))
    ]
    for statement in statements:
        if statement:
            db.session.execute(text(statement))
    db.session.commit()
    logger.info("✅ %s applied.", label)


def run_migrations(db):
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS migrations (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                migration   VARCHAR(255) NOT NULL UNIQUE,
                applied_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()

        # Fresh install detection — bootstrap from schema.sql if no tables exist yet
        table_count = db.session.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name != 'migrations'"
        )).scalar()

        if table_count == 0:
            if SCHEMA_PATH.exists():
                logger.info("🆕 Fresh database detected — bootstrapping from schema.sql")
                _run_sql_file(db, SCHEMA_PATH, "schema.sql")
            else:
                logger.warning("⚠ Fresh database but no schema.sql found at %s", SCHEMA_PATH)
                return

        applied = {
            row[0]
            for row in db.session.execute(
                text("SELECT migration FROM migrations")
            ).fetchall()
        }

        if not MIGRATIONS_DIR.exists():
            logger.warning("⚠ Migrations directory not found: %s", MIGRATIONS_DIR)
            return

        migration_files = sorted(
            f for f in MIGRATIONS_DIR.iterdir()
            if f.suffix == ".sql" and f.name not in applied
        )

        if not migration_files:
            logger.info("✅ All migrations already applied.")
            return

        for migration_file in migration_files:
            logger.info("🔄 Applying migration: %s", migration_file.name)
            try:
                _run_sql_file(db, migration_file, migration_file.name)
                db.session.execute(
                    text("INSERT IGNORE INTO migrations (migration) VALUES (:name)"),
                    {"name": migration_file.name},
                )
                db.session.commit()
                logger.info("✅ Migration applied: %s", migration_file.name)
            except Exception as e:
                db.session.rollback()
                logger.error("❌ Migration failed: %s - %s", migration_file.name, e)

    except Exception as e:
        logger.error("❌ Migration runner error: %s", e)
