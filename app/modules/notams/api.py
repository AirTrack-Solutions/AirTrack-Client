"""
NOTAM API blueprint.

This is a safe scaffold. Database access is intentionally isolated so it can
be wired to the existing AirTrack Logbook db/session conventions later.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from .normalizer import normalize_many

notams_api_bp = Blueprint("notams_api", __name__, url_prefix="/api/notams")


@notams_api_bp.get("/health")
def health():
    return jsonify({
        "module": "notams",
        "status": "available",
        "implemented": "scaffold",
    })


@notams_api_bp.post("/import")
def import_notams():
    """
    Manual import endpoint.

    For this scaffold, it parses and returns normalized records but does not
    write to the database yet. Wiring DB insert comes next.
    """
    payload = request.get_json(silent=True) or {}
    raw = payload.get("raw", "")
    source = payload.get("source", "manual")
    home_icaos = set(payload.get("home_icaos", []))

    if not raw.strip():
        return jsonify({
            "imported": 0,
            "skipped_duplicates": 0,
            "parse_errors": 1,
            "low_confidence": 0,
            "error": "No raw NOTAM text supplied",
        }), 400

    records = normalize_many(raw, source=source, home_icaos=home_icaos)

    low_confidence = sum(1 for r in records if r.get("parse_confidence") == "LOW")
    parse_errors = sum(1 for r in records if r.get("_parse_errors"))

    return jsonify({
        "imported": len(records),
        "skipped_duplicates": 0,
        "parse_errors": parse_errors,
        "low_confidence": low_confidence,
        "notam_ids": [r.get("notam_id") for r in records],
        "records": records,
    })


@notams_api_bp.get("/critical")
def critical():
    return jsonify({
        "count": 0,
        "notams": [],
        "note": "DB-backed critical endpoint not wired yet.",
    })


@notams_api_bp.get("/live")
def live():
    return jsonify({
        "count": 0,
        "notams": [],
        "note": "DB-backed live endpoint not wired yet.",
    })


@notams_api_bp.get("/statistics")
def statistics():
    return jsonify({
        "period_days": int(request.args.get("days", 30)),
        "total": 0,
        "by_severity": {
            "CRITICAL": 0,
            "SIGNIFICANT": 0,
            "MINOR": 0,
            "INFORMATIONAL": 0,
        },
        "by_category": {},
        "note": "Goblin-backed statistics not wired yet.",
    })
