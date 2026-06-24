# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ('Subhuti'). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# routes/admin_routes.py

from pathlib import Path
from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    jsonify,
    current_app,
)

from sqlalchemy import text

from utils.country_importer import import_aircraft_row

from extensions import db

import json
import os

import logging

from datetime import datetime



admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _endpoint_url(name: str) -> str:
    """
    Safely return url_for(name) or an empty string if the endpoint doesn't exist.
    Prevents template crashes when routes differ between server/client builds.
    """
    try:
        return url_for(name)
    except Exception:
        return ""


@admin_bp.route("/")

def admin_dashboard():

    # -----------------------------
    # Stats
    # -----------------------------

    def _get_airtrack_stats():
        try:
            with db.engine.connect() as conn:
                total_aircraft = conn.execute(
                    text("SELECT COUNT(*) FROM aircraft")
                ).scalar()

                total_flights = conn.execute(
                    text("SELECT COUNT(*) FROM flights")
                ).scalar()

                total_airlines = conn.execute(
                    text("SELECT COUNT(*) FROM airlines")
                ).scalar()

                models_seen = conn.execute(
                    text(
                        """
                        SELECT COUNT(DISTINCT Aircraft_Type)
                        FROM aircraft
                        WHERE Aircraft_Type IS NOT NULL
                        AND Aircraft_Type != ''
                        """
                    )
                ).scalar()

                photos_logged = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM aircraft
                        WHERE Aircraft_Image IS NOT NULL
                        AND Aircraft_Image != ''
                        """
                    )
                ).scalar()

                total_countries = conn.execute(
                    text(
                        """
                        SELECT COUNT(DISTINCT Country_of_Reg)
                        FROM aircraft
                        WHERE Country_of_Reg IS NOT NULL
                        AND Country_of_Reg != ''
                        """
                    )
                ).scalar()

                orphaned_aircraft = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM aircraft
                        WHERE AirlineID IS NULL OR AirlineID = ''
                        """
                    )
                ).scalar()

                airports_logged = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM (
                            SELECT DISTINCT ICAO
                            FROM (
                                SELECT Departure AS ICAO FROM aircraft
                                UNION
                                SELECT Arrival AS ICAO FROM aircraft
                            ) AS all_icaos
                            WHERE ICAO IS NOT NULL
                            AND ICAO IN (SELECT ICAO FROM airports)
                        ) AS valid_airports
                        """
                    )
                ).scalar() or 0

                return {
                    "total_aircraft": total_aircraft,
                    "total_flights": total_flights,
                    "total_airlines": total_airlines,
                    "models_seen": models_seen,
                    "photos_logged": photos_logged,
                    "total_countries": total_countries,
                    "orphaned_aircraft": orphaned_aircraft,
                    "airports_logged": airports_logged,
                }

        except Exception as e:
            logging.error(f"❌ Error fetching admin stats: {e}")
            return {
                "total_aircraft": 0,
                "total_flights": 0,
                "total_airlines": 0,
                "models_seen": 0,
                "photos_logged": 0,
                "total_countries": 0,
                "orphaned_aircraft": 0,
                "airports_logged": 0,
            }

    stats = _get_airtrack_stats()

    # -----------------------------
    # Backup file list
    # -----------------------------
    backup_dir = os.path.join(
        os.path.dirname(current_app.root_path),
        "app",
        "backups",
    )

    try:
        files = []

        if os.path.isdir(backup_dir):
            for f in os.listdir(backup_dir):
                if f.endswith(".sql"):
                    p = os.path.join(backup_dir, f)

                    files.append(
                        {
                            "name": f,
                            "modified": datetime.fromtimestamp(
                                os.path.getmtime(p)
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

        backup_files = sorted(
            files,
            key=lambda x: x["modified"],
            reverse=True,
        )

    except Exception as e:
        logging.error(f"❌ Error listing backup files: {e}")
        backup_files = []

    # -----------------------------
    # Role / feature flags
    # -----------------------------
    is_server = os.getenv('AIRTRACK_ROLE', 'client').lower() == 'server'

    show_commit_push = (
        is_server
        and 'admin_tools.git_commit' in current_app.view_functions
        and 'admin_tools.git_push' in current_app.view_functions
    )

    # -----------------------------
    # Safe endpoint URLs
    # -----------------------------
    airtrack_urls = {k: v for k, v in {
        "check_updates": _endpoint_url('admin_tools.check_updates'),
        "run_updater":   _endpoint_url('admin_tools.run_updater'),
        "git_commit":    _endpoint_url('admin_tools.git_commit'),
        "git_push":      _endpoint_url('admin_tools.git_push'),
        "git_pull":      _endpoint_url('admin_tools.git_pull'),
        "housekeeping":  _endpoint_url('admin_tools.housekeeping'),
        "logs":          _endpoint_url('admin_tools.logs'),
        "logs_tail":     _endpoint_url('admin_tools.logs_tail'),
    }.items() if v}

    # Applied app update version (client only — reads AIRTRACK_HOME/app_update_version.txt)
    app_update_version = None
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _home = _Path(os.environ.get('AIRTRACK_HOME') or (
            os.path.join(os.environ.get('ProgramData', 'C:/ProgramData'), 'AirTrack')
            if _sys.platform == 'win32' else '/airtrack_data'
        ))
        _vf = _home / 'app_update_version.txt'
        if _vf.exists():
            _v = _vf.read_text(encoding='utf-8').strip()
            if _v and _v != '0.0.0':
                app_update_version = _v
    except Exception:
        pass

    return render_template(
        'admin.html',
        stats=stats,
        backup_files=backup_files,
        show_commit_push=show_commit_push,
        airtrack_urls=airtrack_urls,
        is_server=is_server,
        app_update_version=app_update_version,
    )


@admin_bp.route('/settings', methods=['GET'])

def admin_settings():
    # Settings live in the admin.html modal — redirect there
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/save_settings', methods=['POST'])

def save_settings():
    try:
        data = request.get_json(silent=True) or {}
        first_name = (data.get("first_name") or request.form.get("first_name", "")).strip()
        last_name = (data.get("last_name") or request.form.get("last_name", "")).strip()
        callsign = (data.get("callsign") or request.form.get("callsign", "")).strip()

        for key, value in [
            ("FirstName", first_name),
            ("LastName", last_name),
            ("Callsign", callsign),
        ]:
            db.session.execute(
                text(
                    """
                    INSERT INTO app_settings (SettingKey, SettingValue)
                    VALUES (:key, :value)
                    ON DUPLICATE KEY UPDATE
                        SettingValue = VALUES(SettingValue)
                    """
                ),
                {"key": key, "value": value},
            )

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        current_app.logger.exception('save_settings failed')
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------------------------------------------------------------------
# Manual Aircraft Entry
# ---------------------------------------------------------------------------

@admin_bp.route('/manual_aircraft', methods=['GET', 'POST'])

def manual_aircraft():

    if request.method == 'POST':
        try:
            form = request.form.to_dict()

            # Clean empty fields
            raw_data = {k: v for k, v in form.items() if v.strip() != ""}

            if "registration" not in raw_data:
                flash("❌ Registration is required", "danger")
                return redirect(url_for('admin.manual_aircraft'))

            # Use your importer logic
            import_aircraft_row(db, raw_data)

            flash(f"✅ Aircraft {raw_data.get('registration')} saved successfully", "success")
            return redirect(url_for('admin.manual_aircraft'))

        except Exception as e:
            current_app.logger.exception("Manual aircraft entry failed")
            flash(f"❌ Error: {e}", "danger")
            return redirect(url_for('admin.manual_aircraft'))

    return render_template('manual_aircraft_entry.html')

@admin_bp.route('/update_app_settings', methods=['POST'])

def update_app_settings():

    try:
        data = request.get_json() or {}

        theme = (data.get("theme") or 'default').strip()
        timezone = (data.get("timezone") or '').strip()
        home_airport = (data.get("home_airport") or '').strip().upper()[:4]

        image_import_folder = (
            data.get("aircraft_image_import_folder")
            or '/app/static/uploads/aircraft_imports'
        ).strip()

        with db.engine.begin() as conn:
            for k, v in (
                ('timezone', timezone),
                ('home_airport', home_airport),
                ('Theme', theme),
                ('aircraft_image_import_folder', image_import_folder),
            ):
                conn.execute(
                    text(
                        """
                        INSERT INTO app_settings (SettingKey, SettingValue)
                        VALUES (:k, :v)
                        ON DUPLICATE KEY UPDATE
                            SettingValue = VALUES(SettingValue)
                        """
                    ),
                    {'k': k, 'v': v},
                )

        return jsonify({"success": True})

    except Exception as e:
        current_app.logger.exception('update_app_settings failed')
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/user_guide')

def user_guide():
    return render_template('user_guide.html')



@admin_bp.route('/woodland')
def woodland_roster():
    import re as _re, html as _html
    roster_path = str(Path(current_app.root_path) / 'woodland_roster.md')
    try:
        with open(roster_path, 'r', encoding='utf-8') as fh:
            raw = fh.read()

        def md_to_html(text):
            t = _html.escape(text)
            # Tables: match pipe-delimited blocks
            table_pat = _re.compile(r'((?:[^\n]*\|[^\n]*\n)+)', _re.MULTILINE)
            def render_table(m):
                rows = [r.strip() for r in m.group(0).strip().splitlines()]
                out = '<table>'
                header_done = False
                for row in rows:
                    if _re.match(r'^[\|\s\-:]+$', row):
                        continue
                    cells = [c.strip() for c in row.strip('|').split('|')]
                    if not header_done:
                        out += '<tr>' + ''.join('<th>' + c + '</th>' for c in cells) + '</tr>'
                        header_done = True
                    else:
                        out += '<tr>' + ''.join('<td>' + c + '</td>' for c in cells) + '</tr>'
                return out + '</table>'
            t = table_pat.sub(render_table, t)
            # Headings
            t = _re.sub(r'^#### (.+)$', r'<h4>\1</h4>', t, flags=_re.MULTILINE)
            t = _re.sub(r'^### (.+)$',  r'<h3>\1</h3>', t, flags=_re.MULTILINE)
            t = _re.sub(r'^## (.+)$',   r'<h2>\1</h2>', t, flags=_re.MULTILINE)
            t = _re.sub(r'^# (.+)$',    r'<h1>\1</h1>', t, flags=_re.MULTILINE)
            # HR
            t = _re.sub(r'^---+$', '<hr>', t, flags=_re.MULTILINE)
            # Bold, italic, inline code
            t = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
            t = _re.sub(r'\*(.+?)\*',     r'<em>\1</em>', t)
            t = _re.sub(r'`([^`]+)`',     r'<code>\1</code>', t)
            # Images: ![alt](src)
            t = _re.sub(r'!\[([^\]]+)\]\(([^)]+)\)', r'<img src="\2" alt="\1" class="critter-portrait">', t)
            # Unordered lists
            def render_list(m):
                items = _re.findall(r'^[-*] (.+)$', m.group(0), _re.MULTILINE)
                return '<ul>' + ''.join('<li>' + i + '</li>' for i in items) + '</ul>'
            t = _re.sub(r'(^[-*] .+\n?)+', render_list, t, flags=_re.MULTILINE)
            # Paragraphs
            paras = _re.split(r'\n{2,}', t)
            out = []
            for p in paras:
                p = p.strip()
                if not p:
                    continue
                if p.startswith('<'):
                    out.append(p)
                else:
                    out.append('<p>' + p.replace('\n', '<br>') + '</p>')
            return '\n'.join(out)

        content_html = md_to_html(raw)
    except Exception as e:
        content_html = '<p style="color:#cc4444">Could not load roster: ' + str(e) + '</p>'
    return render_template('admin_woodland.html', content=content_html)


# ---------------------------------------------------------------------------
# Modules page
# ---------------------------------------------------------------------------

@admin_bp.route('/modules')
def modules_page():
    modules_dir = Path(current_app.root_path) / 'modules'
    modules = []
    for d in sorted(modules_dir.iterdir()):
        if not d.is_dir() or d.name.startswith('_') or d.name == 'tools':
            continue
        meta_path = d / 'module.json'
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            meta['folder'] = d.name
            modules.append(meta)
        except Exception:
            continue
    return render_template('admin_modules.html', modules=modules)


@admin_bp.route('/modules/toggle', methods=['POST'])
def modules_toggle():
    folder   = request.form.get('folder', '').strip()
    enabled  = request.form.get('enabled') == '1'

    if not folder or '/' in folder or folder.startswith('.'):
        flash('Invalid module name.', 'danger')
        return redirect(url_for('admin.modules_page'))

    meta_path = Path(current_app.root_path) / 'modules' / folder / 'module.json'
    if not meta_path.exists():
        flash(f'Module {folder} not found.', 'danger')
        return redirect(url_for('admin.modules_page'))

    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        meta['enabled'] = enabled
        tmp = meta_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(meta, indent=2), encoding='utf-8')
        tmp.replace(meta_path)
        action = 'enabled' if enabled else 'disabled'
        flash(f"{meta.get('title', folder)} {action}. Restart required to take effect.", 'success')
    except Exception as e:
        flash(f'Could not update module: {e}', 'danger')

    return redirect(url_for('admin.modules_page'))
