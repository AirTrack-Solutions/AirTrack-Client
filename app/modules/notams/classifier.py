"""
NOTAM classifier.

This layer assigns AirTrack category/severity from parsed NOTAM fields.
It does not mutate raw NOTAM source text.
"""

from __future__ import annotations

from datetime import datetime, timezone


CRITICAL_KEYWORDS = {
    "CLOSED",
    "CLSD",
    "PROHIBITED",
    "SUSPENDED",
    "EMERGENCY",
    "UNSERVICEABLE",
    "U/S",
}

SIGNIFICANT_KEYWORDS = {
    "RESTRICTED",
    "LIMITED",
    "REDUCED",
    "CAUTION",
    "OUTAGE",
}

INFO_KEYWORDS = {
    "ADMINISTRATIVE",
    "AMENDED",
    "PROCEDURE CHANGE",
}


def classify_record(record: dict, home_icaos: set[str] | None = None) -> dict:
    """
    Classify and assign severity.

    severity   = operational seriousness by nature (independent of timing)
    active_now = whether the NOTAM is currently in force

    home_icaos:
        Optional set of ICAO locations the installation cares most about.
    """
    home_icaos = home_icaos or set()

    text = (record.get("text_raw") or "").upper()
    q_subject = (record.get("q_subject") or "").upper()
    q_condition = (record.get("q_condition") or "").upper()
    q_code = (record.get("q_code") or "").upper()
    scope = (record.get("q_scope") or "").upper()
    traffic = (record.get("q_traffic") or "").upper()
    primary_icao = (record.get("primary_icao") or "").upper()

    category = _category_from_q_and_text(q_subject, q_condition, q_code, text)
    severity = _severity_from_record(
        category=category,
        text=text,
        q_condition=q_condition,
        scope=scope,
        traffic=traffic,
        primary_icao=primary_icao,
        home_icaos=home_icaos,
    )
    active_now = _is_active_now(record)

    result = dict(record)
    result["category"] = category
    result["severity"] = severity
    result["active_now"] = active_now
    return result


def _category_from_q_and_text(q_subject: str, q_condition: str, q_code: str, text: str) -> str:
    if "GPS" in text or "GNSS" in text:
        return "gps_interference"

    if "BIRD" in text:
        return "bird_activity"

    if q_subject == "MR" or "RWY" in text:
        if q_condition in {"LC", "CC"} or "CLSD" in text or "CLOSED" in text:
            return "runway_closure"
        return "airport_maintenance"

    if "TWY" in text or "TAXIWAY" in text:
        return "taxiway_closure"

    if q_subject.startswith("R") or q_code.startswith("R"):
        return "airspace_restriction"

    if q_subject.startswith("N") or any(token in text for token in ("ILS", "VOR", "NDB", "DME", "TACAN")):
        return "navaid_outage"

    if q_subject.startswith("O") or any(token in text for token in ("CRANE", "OBST", "TOWER", "MAST")):
        return "obstacle_warning"

    if q_subject.startswith("W") or any(token in text for token in ("SIGMET", "AIRMET", "TURB", "ICE", "CB", "TS")):
        return "weather_related"

    if q_subject.startswith("D") or "MIL" in text or "MILITARY" in text:
        return "military_activity"

    if q_subject.startswith("L") or "LGT" in text or "LIGHT" in text:
        return "lighting"

    if "FUEL" in text:
        return "fuel_services"

    if q_subject.startswith("P") or q_subject.startswith("A"):
        return "procedural_change"

    return "other"


def _severity_from_record(
    *,
    category: str,
    text: str,
    q_condition: str,
    scope: str,
    traffic: str,
    primary_icao: str,
    home_icaos: set[str],
) -> str:
    """
    Severity reflects operational seriousness by nature.
    Timing (active_now) is a separate dimension — never downgrade here for date.
    """
    local = primary_icao in home_icaos if primary_icao else False

    if category == "runway_closure" and "A" in scope:
        return "CRITICAL"

    if category == "airspace_restriction" and traffic in {"I", "IV"} and local:
        return "CRITICAL"

    if category == "gps_interference" and local:
        return "CRITICAL"

    if category == "navaid_outage" and any(token in text for token in ("ILS", "VOR", "DME")):
        return "SIGNIFICANT"

    if any(keyword in text for keyword in CRITICAL_KEYWORDS):
        if category in {"runway_closure", "navaid_outage", "airspace_restriction"}:
            return "CRITICAL"
        return "SIGNIFICANT"

    if category in {"airspace_restriction", "military_activity", "weather_related"}:
        return "SIGNIFICANT"

    if any(keyword in text for keyword in SIGNIFICANT_KEYWORDS):
        return "SIGNIFICANT"

    if any(keyword in text for keyword in INFO_KEYWORDS):
        return "INFORMATIONAL"

    if category in {"taxiway_closure", "lighting", "bird_activity", "airport_maintenance"}:
        return "MINOR"

    if category in {"procedural_change", "fuel_services"}:
        return "INFORMATIONAL"

    return "MINOR"


def _is_active_now(record: dict) -> bool:
    now = datetime.now(timezone.utc)
    start = record.get("effective_from")
    end = record.get("effective_to")
    is_permanent = bool(record.get("is_permanent"))

    if start and now < start:
        return False
    if not is_permanent and end and now > end:
        return False
    return True
