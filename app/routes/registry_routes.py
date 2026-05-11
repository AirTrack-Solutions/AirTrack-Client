# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ("Subhuti"). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

import os
import re
import subprocess
import logging

from datetime import date
from pathlib import Path
from flask import Blueprint, render_template, jsonify, request, current_app
from sqlalchemy import text
from extensions import db
from routes.country_importer import ensure_country_table

registry_bp = Blueprint('registry', __name__, url_prefix='/admin/registries')

# Top-level dirs to skip — not country registries
_SKIP_DIRS = {
    'zoo of registers', 'packs', 'failed', 'rejected',
    'processed', 'logs', 'inbox', 'holding',
}

DAILY_IMPORT_LIMIT = 5


# ── Helpers ──────────────────────────────────────────────────────────────────

def _registries_dir() -> Path:
    return Path(current_app.root_path) / 'registries'


def _find_sql_file(country_dir: Path) -> Path | None:
    """Return the canonical .sql file directly inside a country directory."""
    try:
        sql_files = [
            f for f in country_dir.iterdir()
            if f.is_file() and f.suffix.lower() == '.sql'
        ]
    except PermissionError:
        return None

    if not sql_files:
        return None

    # Prefer a file whose stem matches the directory name (case-insensitive)
    dirname_lower = country_dir.name.lower().replace(' ', '_')
    for f in sql_files:
        if f.stem.lower() == dirname_lower:
            return f

    # Accept any single .sql file
    return sql_files[0]


def _extract_table_name(sql_file: Path) -> str | None:
    """Read the table name from the first INSERT statement in a SQL file."""
    try:
        with sql_file.open('r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                m = re.search(r'INSERT INTO `([^`]+)`', line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def _record_count_from_comment(sql_file: Path) -> int:
    """Try to read the record count from the header comment (-- Records: N)."""
    try:
        with sql_file.open('r', encoding='utf-8', errors='replace') as fh:
            for i, line in enumerate(fh):
                if i >= 10:
                    break
                m = re.search(r'Records:\s*([\d,]+)', line)
                if m:
                    return int(m.group(1).replace(',', ''))
    except Exception:
        pass
    return 0


def _table_exists(table_name: str) -> bool:
    try:
        n = db.session.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :n"
            ),
            {"n": table_name},
        ).scalar()
        return bool(n)
    except Exception:
        return False


def _row_count(table_name: str) -> int:
    try:
        return db.session.execute(
            text(f"SELECT COUNT(*) FROM `{table_name}`")
        ).scalar() or 0
    except Exception:
        return 0


# ── Daily import quota ────────────────────────────────────────────────────────

def _ensure_quota_table():
    """Create the quota tracking table if it doesn't exist."""
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS `registry_quota` (
            `quota_date`   DATE NOT NULL,
            `imports_done` INT  NOT NULL DEFAULT 0,
            PRIMARY KEY (`quota_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))
    db.session.commit()


def _imports_today() -> int:
    """Return how many successful imports have been recorded today."""
    try:
        _ensure_quota_table()
        result = db.session.execute(
            text("SELECT imports_done FROM registry_quota WHERE quota_date = CURDATE()")
        ).scalar()
        return int(result or 0)
    except Exception:
        return 0


def _record_import():
    """Increment today's import counter (upsert)."""
    try:
        db.session.execute(text("""
            INSERT INTO registry_quota (quota_date, imports_done)
            VALUES (CURDATE(), 1)
            ON DUPLICATE KEY UPDATE imports_done = imports_done + 1
        """))
        db.session.commit()
    except Exception:
        logging.exception("Failed to record import quota")


def scan_registries() -> list[dict]:
    """
    Walk the registries directory and return one dict per importable registry.
    Only Title_Case directories with a matching .sql file are included.
    """
    reg_dir = _registries_dir()
    results = []
    seen_tables: set[str] = set()

    try:
        entries = sorted(reg_dir.iterdir(), key=lambda p: p.name.lower())
    except Exception:
        return results

    for item in entries:
        if not item.is_dir():
            continue
        if item.name.lower() in _SKIP_DIRS:
            continue
        if not item.name[0].isupper():
            continue  # Skip lowercase duplicates (armenia/, malta/, etc.)

        sql_file = _find_sql_file(item)
        if not sql_file:
            continue

        table_name = _extract_table_name(sql_file)
        if not table_name:
            continue

        if table_name in seen_tables:
            continue
        seen_tables.add(table_name)

        imported = _table_exists(table_name)
        results.append({
            'display_name': item.name.replace('_', ' '),
            'dir':          item.name,
            'table':        table_name,
            'sql_path':     str(sql_file),
            'file_records': _record_count_from_comment(sql_file),
            'imported':     imported,
            'row_count':    _row_count(table_name) if imported else 0,
        })

    return results


# ── Routes ───────────────────────────────────────────────────────────────────

@registry_bp.route('/')
def registry_list():
    registries = scan_registries()
    imported_count = sum(1 for r in registries if r['imported'])
    today_count = _imports_today()
    return render_template(
        'admin_registries.html',
        registries=registries,
        imported_count=imported_count,
        total_count=len(registries),
        imports_today=today_count,
        daily_limit=DAILY_IMPORT_LIMIT,
    )


@registry_bp.route('/import/<country>', methods=['POST'])
def import_registry(country):
    reg_dir = _registries_dir()
    country_dir = reg_dir / country

    if not country_dir.is_dir():
        return jsonify({'status': 'error', 'detail': f'Not found: {country}'}), 404

    # ── Daily limit check ────────────────────────────────────────────────────
    today_count = _imports_today()
    if today_count >= DAILY_IMPORT_LIMIT:
        remaining = 0
        return jsonify({
            'status':    'error',
            'detail':    f'Daily limit of {DAILY_IMPORT_LIMIT} imports reached — come back tomorrow!',
            'quota':     {'used': today_count, 'limit': DAILY_IMPORT_LIMIT, 'remaining': remaining},
        }), 429

    sql_file = _find_sql_file(country_dir)
    if not sql_file:
        return jsonify({'status': 'error', 'detail': 'No SQL file found'}), 404

    table_name = _extract_table_name(sql_file)
    if not table_name:
        return jsonify({'status': 'error', 'detail': 'Could not determine table name'}), 400

    try:
        # Ensure the table schema exists before importing
        ensure_country_table(db, table_name)

        db_host     = os.getenv('DB_HOST', 'airtrack-db')
        db_user     = os.getenv('DB_USER', 'airtrack')
        db_password = os.getenv('DB_PASSWORD', '')
        db_name     = os.getenv('DB_NAME', 'airtrack')

        with sql_file.open('r', encoding='utf-8', errors='replace') as fh:
            result = subprocess.run(
                ['mysql', '-h', db_host, f'-u{db_user}', f'-p{db_password}', db_name],
                stdin=fh,
                capture_output=True,
                text=True,
                timeout=600,
            )

        if result.returncode != 0:
            logging.error(f"Registry import failed for {country}: {result.stderr}")
            return jsonify({'status': 'error', 'detail': result.stderr or 'Import failed'}), 500

        rows = _row_count(table_name)
        _record_import()
        new_count = today_count + 1
        remaining  = max(0, DAILY_IMPORT_LIMIT - new_count)
        return jsonify({
            'status':    'ok',
            'detail':    f'Imported {rows:,} records',
            'row_count': rows,
            'quota':     {'used': new_count, 'limit': DAILY_IMPORT_LIMIT, 'remaining': remaining},
        })

    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'detail': 'Import timed out (>10 min)'}), 500
    except Exception as e:
        logging.exception(f"Registry import error for {country}")
        return jsonify({'status': 'error', 'detail': str(e)}), 500


@registry_bp.route('/remove/<country>', methods=['POST'])
def remove_registry(country):
    reg_dir = _registries_dir()
    country_dir = reg_dir / country

    # Derive table name from the SQL file if possible, else from dir name
    table_name = None
    if country_dir.is_dir():
        sql_file = _find_sql_file(country_dir)
        if sql_file:
            table_name = _extract_table_name(sql_file)

    if not table_name:
        table_name = country.lower().replace(' ', '_')

    try:
        db.session.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
        db.session.commit()
        return jsonify({'status': 'ok', 'detail': f'Removed {country}'})
    except Exception as e:
        logging.exception(f"Registry remove error for {country}")
        return jsonify({'status': 'error', 'detail': str(e)}), 500
