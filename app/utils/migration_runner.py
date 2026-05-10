# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

import logging
from pathlib import Path
from sqlalchemy import text

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


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
                sql = migration_file.read_text(encoding="utf-8")
                statements = [
                    stmt.strip()
                    for stmt in sql.split(";")
                    if stmt.strip() and not stmt.strip().startswith("--")
                ]
                for statement in statements:
                    if statement:
                        db.session.execute(text(statement))
                db.session.execute(
                    text("INSERT IGNORE INTO migrations (migration) VALUES (:name)"),
                    {"name": migration_file.name},
                )
                db.session.commit()
                logger.info("✅ Migration applied: %s", migration_file.name)
            except Exception as e:
                db.session.rollback()
                logger.error("❌ Migration failed: %s — %s", migration_file.name, e)

    except Exception as e:
        logger.error("❌ Migration runner error: %s", e)
