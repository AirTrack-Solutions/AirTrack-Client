# AirTrack 1.0.0
# Copyright (c) 2025 Trevor ('Subhuti'). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

import json

import logging

import os

import gzip

import shutil

import time

import signal

import threading

import shlex

import subprocess

import html

from pathlib import Path

from datetime import datetime, timedelta

from flask import (
    Blueprint, flash, jsonify, redirect, render_template,
    request, send_file, url_for, current_app, Response, session
)


from sqlalchemy import text

from extensions import db

from utils.theme_scanner import scan_all

from utils.export_mobile_db import export_mobile_database

from utils.link_checker import append_to_whitelist

from security.guards import require_server

admin_tools_bp = Blueprint('admin_tools', __name__, url_prefix='/admin_tools')

# ====================== Utility Functions ======================

def _is_admin() -> bool:
    try:
        return session.get('is_admin', False) is True
    except Exception:
        return False


def _is_git_dir(p: Path) -> bool:
    g = p / '.git'
    return g.is_dir() or g.is_file()


def _run_cmd(cmd: str, cwd: Path | None = None):
    p = subprocess.Popen(
        shlex.split(cmd), cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    out, err = p.communicate()
    return p.returncode, (out or '').strip(), (err or '').strip()


def _repo_root() -> Path | None:
    env_path = os.getenv('AIRTRACK_REPO_DIR')
    if env_path:
        p = Path(env_path).resolve()
        if _is_git_dir(p):
            return p
    here = Path(__file__).resolve()
    for p in [here.parent] + list(here.parents):
        if _is_git_dir(p):
            return p
    root = Path(current_app.root_path).resolve()
    for p in [root] + list(root.parents):
        if _is_git_dir(p):
            return p
    return None


def _ok(**payload):
    return jsonify(payload), 200


def _err(msg, code=400, **extra):
    d = {"status": "error", "detail": msg}
    d.update(extra)
    return jsonify(d), code


def _ensure_identity(repo: Path):
    rc, name, _ = _run_cmd("git config user.name", cwd=repo)
    if rc != 0 or not name:
        _run_cmd('git config user.name "AirTrack HUD"', cwd=repo)
    rc, email, _ = _run_cmd('git config user.email', cwd=repo)
    if rc != 0 or not email:
        _run_cmd("git config user.email 'hud@example.com'", cwd=repo)

def _shutdown_enabled() -> bool:
    return os.getenv('AIRTRACK_ENABLE_SHUTDOWN', '0').lower() in {
        '1', 'true', 'yes', 'on'
    }


def _days_ago(n: int) -> float:
    return (datetime.now() - timedelta(days=n)).timestamp()


def _fmt_bytes(n: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _gzip_file(src: Path) -> tuple[int, int]:
    if src.suffix == '.gz' or not src.is_file():
        return (0, 0)
    gz = src.with_suffix(src.suffix + '.gz')
    if gz.exists():
        return (0, 0)
    old = src.stat().st_size
    with src.open('rb') as f_in, gzip.open(gz, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    new = gz.stat().st_size
    return (old, new)


def _delete_old_files(root: Path, older_than_ts: float, dry_run: bool) -> dict:
    res = {"files": 0, "bytes": 0, "paths": []}
    if not root.exists():
        return res
    for p in root.rglob('*'):
        try:
            if not p.is_file():
                continue
            st = p.stat()
            if st.st_mtime < older_than_ts:
                res['files'] += 1
                res['bytes'] += st.st_size
                res['paths'].append(str(p))
                if not dry_run:
                    p.unlink(missing_ok=True)
        except Exception:
            continue
    return res


def _rotate_logs(log_dir: Path, older_than_ts: float, dry_run: bool) -> dict:
    res = {"compressed": 0, "deleted": 0, "bytes_saved": 0}
    if not log_dir.exists():
        return res
    for p in log_dir.glob('*.log'):
        try:
            if p.stat().st_mtime < older_than_ts:
                old, new = (0, 0) if dry_run else _gzip_file(p)
                if not dry_run and old and new:
                    p.unlink(missing_ok=True)
                    res['compressed'] += 1
                    res['bytes_saved'] += max(0, old - new)
        except Exception:
            continue
    for gz in log_dir.glob('*.log.gz'):
        try:
            if gz.stat().st_mtime < _days_ago(90):
                if not dry_run:
                    size = gz.stat().st_size
                    gz.unlink(missing_ok=True)
                    res['deleted'] += 1
                    res['bytes_saved'] += size
        except Exception:
            continue
    return res

# ====================== Routes ======================


def test_airport():
    code = (request.args.get('code') or '').upper()
    with db.engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM airports WHERE ICAO = :c OR IATA = :c LIMIT 1"),
            {"c": code},
        ).mappings().fetchone()
    return jsonify({"code": code, "row_keys": list(row.keys()) if row else []})


@admin_tools_bp.route('/whitelist_link', methods=['POST'])

def whitelist_link():
    icao = (request.form.get('icao') or '').strip().upper()
    label = request.form.get('label')
    url = request.form.get('url')
    if not icao or not label or not url:
        flash("Missing required fields", 'danger')
        return redirect(url_for('admin_tools.broken_links'))
    try:
        whitelist_path = os.path.join('logs', 'link_whitelist.txt')
        append_to_whitelist(whitelist_path, icao, label, url)
        flash(f"✅ Whitelisted link for {icao} ({label})", 'success')
    except Exception as e:
        logging.error(f"❌ Whitelist error: {e}")
        flash("❌ Failed to whitelist link.", 'danger')
    return redirect(url_for('admin_tools.broken_links'))


@admin_tools_bp.route('/run_updater', methods=['GET', 'POST'])

def run_updater():

    if os.getenv('AIRTRACK_ROLE', 'client') != 'client':
        return _err("Updates are disabled on server installations.")

    try:
        from utils.airtrack_updater import run_full_update
        result = run_full_update()
        return _ok(**result)

    except Exception as e:
        return _err(f"❌ Updater failed: {e}")

@admin_tools_bp.route('/git_commit', methods=['POST'])
@require_server

def git_commit():
    repo = _repo_root()
    if not repo:
        return _err("❌ Repo root not found.")
    _ensure_identity(repo)

    data = request.get_json(silent=True) or {}
    msg = (data.get('message') or request.form.get('message') or '').strip()
    if not msg:
        return _err("⚠️ Commit message required.")

    try:
        _run_cmd("git add -A", cwd=repo)
        rc, out, err = _run_cmd(f'git commit -m "{msg}"', cwd=repo)
        if rc != 0:
            if "nothing to commit" in out or "nothing to commit" in err:
                return _ok(status='noop', detail='ℹ️ Nothing to commit.')
            return _err("❌ Git commit failed.", detail=err or out)
        return _ok(status='ok', detail='✅ Commit successful.')
    except Exception as e:
        return _err(f"❌ Commit failed: {e}")


@admin_tools_bp.route('/git_push', methods=['POST'])
@require_server

def git_push():
    """Push committed changes to remote."""
    repo = _repo_root()
    if not repo:
        return _err("❌ Repo root not found.")

    try:
        rc, out, err = _run_cmd("git push", cwd=repo)
        if rc != 0:
            return _err("❌ Git push failed.", detail=err or out)
        return _ok(status="ok", detail="✅ Push successful.")
    except Exception as e:
        return _err(f"❌ Push failed: {e}")


@admin_tools_bp.get("/themes")

def list_themes():
    themes = scan_all()
    return jsonify(themes)


@admin_tools_bp.post("/rescan_themes")

def rescan_themes():
    """Force a full theme rescan, bypassing the staleness check."""
    try:
        from utils.theme_scanner import scan_and_generate
        themes = scan_and_generate()
        return _ok(status="ok", count=len(themes))
    except Exception as e:
        logging.exception("rescan_themes failed")
        return _err(f"rescan failed: {e}")


@admin_tools_bp.route("/export_db_mobile")

def export_db_mobile():
    try:
        db_path = export_mobile_database()
        if not db_path or not os.path.isfile(db_path):
            raise ValueError("Mobile export file not found or invalid.")
        return send_file(
            db_path,
            as_attachment=True,
            download_name="airtrack_mobile.db",
            mimetype="application/octet-stream",
        )
    except Exception as e:
        logging.exception("❌ Mobile DB export failed")
        return _err(f"❌ Export failed: {e}")


@admin_tools_bp.route("/housekeeping", methods=["POST"])

def housekeeping():
    """
    AirTrack Housekeeping — available on both server and client.
    - Accepts JSON { dry_run: bool, retention_days: int }
    - No CSRF required for JSON API use
    - Returns strict JSON (never HTML)
    """

    # Load JSON safely
    data = request.get_json(silent=True) or {}

    # Accept JS-side naming
    dry_run = bool(data.get("dry_run"))
    keep_days = int(data.get("retention_days") or data.get("keep_days") or 30)

    if keep_days < 7:
        return _err("⚠️ Minimum keep period is 7 days.")

    cutoff_ts = _days_ago(keep_days)

    # Correct paths inside container
    logs_path = Path("/app/logs").resolve()
    backups_path = Path("/app/backups").resolve()
    static_export_path = Path("/app/static/export").resolve()

    # Perform operations
    deleted_backups = _delete_old_files(backups_path, cutoff_ts, dry_run)
    deleted_exports = _delete_old_files(static_export_path, cutoff_ts, dry_run)
    rotated_logs = _rotate_logs(logs_path, cutoff_ts, dry_run)

    # Success JSON
    return _ok(
        dry_run=dry_run,
        retention_days=keep_days,
        cutoff_timestamp=cutoff_ts,
        deleted_backups=deleted_backups,
        deleted_exports=deleted_exports,
        rotated_logs=rotated_logs,
    )


@admin_tools_bp.route("/shutdown", methods=["POST"])
@require_server

def shutdown():
    try:

        def _kill():
            time.sleep(0.5)
            os.kill(os.getppid(), signal.SIGTERM)
        threading.Thread(target=_kill).start()
        return _ok(status="success", detail="Server shutting down…")
    except Exception as e:
        return _err(f"Shutdown failed: {e}")


# ====================== Log Management Routes ======================

@admin_tools_bp.route("/logs")
@require_server

def logs():
    """List all available log files in /logs directory."""
    logs_dir = Path(current_app.root_path) / "logs"

    logging.warning(
        f"🧩 Checking logs dir: {logs_dir} "
        f"(exists={logs_dir.exists()})"
    )

    logs = []
    try:
        if logs_dir.exists():
            for p in sorted(logs_dir.glob("*")):
                if p.is_file():
                    stat = p.stat()
                    logs.append(
                        {
                            "name": p.name,
                            "size": _fmt_bytes(stat.st_size),
                            "modified": datetime
                            .fromtimestamp(stat.st_mtime)
                            .strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

                    logging.warning(
                        f"🪶 Found log file: {p.name} "
                        f"({stat.st_size} bytes)"
                    )
        else:
            logging.error(f"❌ Log directory not found: {logs_dir}")

        if not logs:
            logging.warning("⚠️ No log files found in logs_dir")

        return render_template("admin_logs.html", logs=logs)

    except Exception as e:
        logging.exception("❌ Failed to list logs")
        return _err(f"❌ Failed to list logs: {e}")


@admin_tools_bp.route("/logs_view/<path:filename>")
@require_server

def logs_view(filename):
    """Display a log file's contents in a browser."""
    logs_dir = Path(current_app.root_path) / "logs"
    file_path = logs_dir / filename

    if not file_path.exists() or not file_path.is_file():
        return f"❌ Log file not found: {filename}", 404

    try:
        with file_path.open(
            "r",
            encoding="utf-8",
            errors="replace",
        ) as f:
            content = f.read()

        escaped = html.escape(content)

        return Response(
            f"<pre style='font-size:12px'>{escaped}</pre>",
            mimetype="text/html",
        )

    except Exception as e:
        logging.exception(f"❌ Error reading log {filename}")
        return _err(f"❌ Failed to read log: {e}")


@admin_tools_bp.route("/logs_download/<path:filename>")
@require_server

def logs_download(filename):
    """Allow downloading a log file."""
    logs_dir = Path(current_app.root_path) / 'logs'
    file_path = logs_dir / filename
    if not file_path.exists() or not file_path.is_file():
        return f"❌ Log file not found: {filename}", 404

    try:
        return send_file(
            str(file_path),
            as_attachment=True,
            download_name=file_path.name,
            mimetype="text/plain"
        )
    except Exception as e:
        logging.exception(f"❌ Error sending log file {filename}")
        return _err(f"❌ Failed to download log: {e}")


@admin_tools_bp.route("/check_whitelist_links", methods=["POST"])
@require_server

def check_whitelist_links():
    """
    Recheck all whitelisted links and generate a report in /logs.
    """
    output_dir = os.path.join(current_app.root_path, 'logs')
    try:
        from utils.link_checker import check_whitelist_links as check_links
        filename = check_links(output_dir)
        flash(f"✅ Whitelist links checked. Report: {filename}", "success")
    except Exception as e:
        logging.exception("❌ Failed to check whitelist links")
        flash(f"❌ Failed to check whitelist links: {e}", "danger")
    return redirect(url_for("admin.admin_dashboard"))


@admin_tools_bp.get("/broken_links")
@require_server

def broken_links():
    """
    Show the whitelist/broken links management page.
    """
    whitelist_path = os.path.join('logs', 'link_whitelist.txt')
    whitelist = []
    try:
        if os.path.exists(whitelist_path):
            with open(whitelist_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) == 3:
                        icao, label, url = parts
                        whitelist.append({
                            "icao": icao,
                            "label": label,
                            "url": url,
                        })
    except Exception as e:
        logging.warning(f"⚠️ Could not read whitelist: {e}")

    return render_template("admin_broken_links.html", whitelist=whitelist)


@admin_tools_bp.route("/check_aircraft_images", methods=["POST"])
@require_server

def check_aircraft_images():
    """
    Check aircraft image links (from the Aircraft table) and write a report.
    """
    from utils.link_checker import check_url, normalize_url

    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        output_dir = os.path.join('logs')
        os.makedirs(output_dir, exist_ok=True)

        with db.engine.connect() as conn:
            results = conn.execute(
                text("SELECT Registration, Aircraft_Image FROM aircraft")
            ).fetchall()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"image_check_report_{timestamp}.txt"
        filepath = os.path.join(output_dir, filename)

        tasks = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            for registration, img in results:
                url = normalize_url(img)
                if url:
                    tasks.append(
                        executor.submit(
                            check_url,
                            registration,
                            registration,
                            url,
                            "Aircraft Image"
                        )
                    )

            with open(filepath, "w", encoding="utf-8") as f:
                f.write("Aircraft Image Link Report\n")
                f.write("=" * 40 + "\n\n")
                for future in as_completed(tasks):
                    icao, name, label, url, ok = future.result()
                    if ok:
                        f.write(f"[{icao}] ✅ OK: {url}\n")
                    else:
                        f.write(f"[{icao}] ❌ Broken: {url}\n")

        flash(f"✅ Aircraft image check complete. Report: {filename}", "success")

    except Exception as e:
        logging.exception("❌ Aircraft image check failed")
        flash(f"❌ Aircraft image check failed: {e}", "danger")

    return redirect(url_for("admin.admin_dashboard"))


@admin_tools_bp.get("/admin/protected/ping")
@require_server

def protected_ping():
    """Simple probe endpoint used by the Admin Cockpit to test server elevation."""
    return jsonify({"protected": True})


@admin_tools_bp.route("/update_municipality", methods=["POST"])

def update_municipality():
    """Quick-fix endpoint to correct the municipality/city field on an airport record."""
    data = request.get_json(silent=True) or {}
    icao = (data.get("icao") or "").strip().upper()
    city = (data.get("city") or "").strip()
    if not icao or not city:
        return _err("ICAO and city are required.")
    try:
        with db.engine.begin() as conn:
            result = conn.execute(
                text("UPDATE airports SET municipality = :city WHERE icao_code = :icao"),
                {"city": city, "icao": icao},
            )
        if result.rowcount == 0:
            return _err(f"No airport found with ICAO '{icao}'.", code=404)
        return _ok(status="ok", icao=icao, city=city)
    except Exception as e:
        logging.exception("❌ update_municipality failed")
        return _err(f"❌ Database error: {e}")


@admin_tools_bp.route("/check_updates", methods=["GET", "POST"])

def check_updates():
    try:
        from utils.airtrack_updater import check_for_updates
        result = check_for_updates()
        if result.get("error") and result.get("up_to_date"):
            return _err(result["error"])
        return _ok(
            status="ok",
            up_to_date=result["up_to_date"],
            local_version=result["local_version"],
            remote_version=result["remote_version"],
            files_needing_update=result["files_needing_update"],
        )
    except Exception as e:
        return _err(f"❌ Update check failed: {e}")
    