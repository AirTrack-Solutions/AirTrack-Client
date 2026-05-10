# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC




"""
Airports resolver API.
Resolves ICAO/IATA to a readable label from your MariaDB 'airports' table.
Expected columns: ICAO, IATA, AirportName, municipality, iso_country, Country
"""
from flask import Blueprint, jsonify, request, current_app
import os
import pymysql
bp = Blueprint("airports_api", __name__, url_prefix="/api/airports")


def _db_conn():
    # Prefer Flask config, fall back to environment variables, then sensible defaults.
    host = current_app.config.get("DB_HOST") or os.getenv("DB_HOST", "localhost")
    port = int(current_app.config.get("DB_PORT") or os.getenv("DB_PORT", "3306"))
    user = current_app.config.get("DB_USER") or os.getenv("DB_USER", "airtrack")
    password = current_app.config.get("DB_PASSWORD") or os.getenv("DB_PASSWORD", "")
    db = current_app.config.get("DB_NAME") or os.getenv("DB_NAME", "airtrack")
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _fmt_display(row: dict) -> str:
    name = (row.get("AirportName") or "").strip()
    city = (row.get("municipality") or "").strip()
    country = (row.get("Country") or row.get("iso_country") or "").strip()
    iata = (row.get("IATA") or "").upper().strip()
    icao = (row.get("ICAO") or "").upper().strip()
    parts = [p for p in (name, city, country) if p]
    core = ", ".join(parts)
    if iata and icao:
        tail = f" ({iata} / {icao})"
    elif iata or icao:
        tail = f" ({iata or icao})"
    else:
        tail = ""
    return (core + tail) if core else (f"{iata} / {icao}".strip(" /"))


def _get_by_code(code: str):
    if not code:
        return None
    code = code.strip().upper()
    sql = """
        SELECT ICAO, IATA, AirportName, municipality, iso_country, Country
        FROM airports
        WHERE UPPER(ICAO)=%s OR UPPER(IATA)=%s
        LIMIT 1
    """
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (code, code))
            return cur.fetchone()
    code = (request.args.get("code") or "").strip().upper()
    if not code:
        return jsonify({"ok": False, "error": "Missing ?code="}), 400
    row = _get_by_code(code)
    if not row:
        return jsonify({"ok": True, "found": False, "code": code})
    return jsonify(
        {
            "ok": True,
            "found": True,
            "airport": {
                "icao": (row.get("ICAO") or "").upper(),
                "iata": (row.get("IATA") or "").upper(),
                "name": row.get("AirportName") or "",
                "city": row.get("municipality") or "",
                "country": row.get("Country") or row.get("iso_country") or "",
                "display": _fmt_display(row),
            },
        }
    )


@bp.route("/resolve", methods=["POST"])
def resolve():
    """
    Body: { "dep": "YSSY", "arr": "YMML" } OR
          { "codes": ["YSSY", "YMML", "BD", ...] }
    Returns: { ok, results: { CODE: {found, display, ...} } }
    """
    data = request.get_json(silent=True) or {}
    codes = []
    if isinstance(data.get("codes"), list):
        codes = [str(c).strip().upper() for c in data["codes"] if c]
    else:
        for key in ("dep", "arr", "alt"):
            v = data.get(key)
            if v:
                codes.append(str(v).strip().upper())
    # de-dupe preserving order
    seen, ordered = set(), []
    for c in codes:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)
    if not ordered:
        return jsonify({"ok": False, "error": "Provide 'codes' or 'dep/arr/alt'"}), 400
    out = {}
    for c in ordered:
        row = _get_by_code(c)
        if row:
            out[c] = {
                "found": True,
                "icao": (row.get("ICAO") or "").upper(),
                "iata": (row.get("IATA") or "").upper(),
                "name": row.get("AirportName") or "",
                "city": row.get("municipality") or "",
                "country": row.get("Country") or row.get("iso_country") or "",
                "display": _fmt_display(row),
            }
        else:
            out[c] = {"found": False}
    return jsonify({"ok": True, "results": out})
