"""
Human-readable NOTAM summaries.

The raw NOTAM remains the source of truth. This module produces plain-English
summaries and expanded detail text for display surfaces (Logbook, Kiosk, Aria).

make_summary()     → short one-liner for card display (≤ 120 chars)
make_detail_text() → full expanded text for the detail panel
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Comprehensive abbreviation dictionary (AU NOTAM context)
# ---------------------------------------------------------------------------

# Applied as whole-word replacements, longest first to avoid partial matches.
_ABBR: dict[str, str] = {
    # Infrastructure
    "RWY":        "Runway",
    "TWY":        "Taxiway",
    "TWYS":       "Taxiways",
    "APRON":      "Apron",
    "ARP":        "aerodrome reference point",
    "AD":         "Aerodrome",
    "THR":        "threshold",
    "DSPLCD":     "displaced",
    "TDZ":        "touchdown zone",
    "STOPWAY":    "stopway",

    # Status
    "CLSD":       "closed",
    "U/S":        "unserviceable",
    "OTS":        "out of service",
    "AVBL":       "available",
    "NOT TO STD": "not to standard",
    "UNSERVICEABLE": "unserviceable",
    "ERECTED":    "erected",
    "DEACTIVATED": "deactivated",
    "ACT":        "active",
    "DEACT":      "deactivated",

    # Lighting
    "LGT":        "lights",
    "LTS":        "lights",
    "CL":         "centreline",
    "SFL":        "sequenced flashing lights",
    "PAPI":       "precision approach path indicator",
    "VASIS":      "visual approach slope indicator",
    "ALS":        "approach lighting system",
    "HIRL":       "high-intensity runway lights",
    "MIRL":       "medium-intensity runway lights",
    "LIRL":       "low-intensity runway lights",
    "REL":        "runway edge lights",
    "THL":        "threshold lights",
    "TDZL":       "touchdown zone lights",

    # Navigation aids
    "NDB":        "non-directional beacon",
    "VOR":        "VOR",
    "ILS":        "instrument landing system",
    "DME":        "distance measuring equipment",
    "LOC":        "localiser",
    "GP":         "glidepath",
    "GNSS":       "GPS/GNSS",
    "GPS":        "GPS",
    "TACAN":      "TACAN",
    "NAVAID":     "navigation aid",

    # Procedures / routes
    "APCH":       "approach",
    "DEP":        "departure",
    "ARR":        "arrival",
    "SID":        "standard instrument departure",
    "STAR":       "standard terminal arrival route",
    "RNAV":       "RNAV",
    "RNP":        "RNP",
    "PROC":       "procedure",
    "IAP":        "instrument approach procedure",

    # Airspace
    "CTR":        "control zone",
    "CTA":        "control area",
    "FIR":        "flight information region",
    "TMA":        "terminal control area",
    "RESTRICTED": "restricted",
    "PROHIB":     "prohibited",
    "RESTR":      "restriction",
    "ATS":        "air traffic service",
    "ATC":        "air traffic control",
    "MIL":        "military",

    # Obstacles / construction
    "OBST":       "obstacle",
    "CONST":      "construction",
    "EQPT":       "equipment",
    "EQUIP":      "equipment",
    "CRANE":      "crane",
    "TOWER":      "tower",
    "MAST":       "mast",

    # Position / measurement
    "PSN":        "position",
    "BRG":        "bearing",
    "MAG":        "magnetic",
    "AMSL":       "above mean sea level",
    "AGL":        "above ground level",
    "FM":         "from",
    "BTN":        "between",
    "BTW":        "between",
    "ABV":        "above",
    "BLW":        "below",
    "NM":         "nautical miles",
    "FT":         "ft",
    "M":          "m",

    # Services / comms
    "FREQ":       "frequency",
    "UHF":        "UHF",
    "VHF":        "VHF",
    "HF":         "HF",
    "OPR":        "operating",
    "SVC":        "service",
    "OPS":        "operations",

    # Aircraft
    "ACFT":       "aircraft",
    "WINGSPAN":   "wingspan",
    "MAX":        "max",
    "PERM":       "permanently",

    # Work / activity
    "WIP":        "works in progress",
    "MOWP":       "method of working plan",
    "SUBJ":       "subject to",
    "PPR":        "prior permission required",
    "AMD":        "amended",
    "AMDT":       "amendment",
    "CTC":        "contact",
    "MAINT":      "maintenance",
    "FLW":        "following",
    "WI":         "within",
    "EXC":        "except",
    "PH":         "public holidays",
    "HR":         "hours",
    "HRS":        "hours",
    "MON":        "Mon",
    "TUE":        "Tue",
    "WED":        "Wed",
    "THU":        "Thu",
    "FRI":        "Fri",
    "SAT":        "Sat",
    "SUN":        "Sun",
    "TEL":        "Tel",
    "EST":        "est.",
    "APRX":       "approximately",
    "AUTH":       "authorised",
    "UNAUTHORISED": "not authorised",
    "OPN":        "open",

    # Common phrase fragments
    "N/S":        "north/south",
    "E/W":        "east/west",
    "CLG":        "closing",
}

# Phrases replaced as full strings (before word-level substitution)
_PHRASES: list[tuple[str, str]] = [
    ("NOT TO STD",             "not to standard"),
    ("DUE WIP",                "due to works in progress"),
    ("U/S",                    "unserviceable"),
    ("CLSD DUE",               "closed due to"),
    ("REFER TO METHOD OF WORKING PLAN", "see working plan"),
    ("REFER TO MOWP",          "see working plan"),
]


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def _clean_raw(text: str) -> str:
    """Collapse whitespace and strip bracketed technical prefixes."""
    text = text.strip()
    # Remove leading [US DOD PROCEDURAL NOTAM] style tags
    text = re.sub(r"^\[.*?\]\s*", "", text)
    # Collapse whitespace / newlines
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _expand(text: str) -> str:
    """Apply phrase and abbreviation expansion to raw NOTAM text."""
    # Phase 1: multi-word phrase substitution
    result = text.upper()
    for phrase, replacement in _PHRASES:
        result = result.replace(phrase, replacement.upper())

    # Phase 2: whole-word abbreviation expansion
    # Sort by length descending to avoid partial replacements
    for abbr in sorted(_ABBR, key=len, reverse=True):
        pattern = r"\b" + re.escape(abbr) + r"\b"
        result = re.sub(pattern, _ABBR[abbr], result, flags=re.IGNORECASE)

    # Phase 3: title-case the result (aviation text is all-caps)
    result = _title_case(result)
    return result.strip()


def _title_case(text: str) -> str:
    """Smarter title-casing: lowercase prepositions and conjunctions."""
    _lower = {"a","an","the","and","or","but","of","to","at","in","on",
               "by","for","with","due","between","from","above","below","near"}
    words = text.split()
    out = []
    for i, w in enumerate(words):
        if i == 0:
            out.append(w.capitalize())
        elif w.lower() in _lower:
            out.append(w.lower())
        elif w.isupper() and len(w) <= 4:
            # Keep short all-caps acronyms (ILS, VOR, NDB, etc.) as-is
            out.append(w)
        elif w.isupper() and any(c.isdigit() for c in w):
            # Keep alphanumeric unit codes (371KHZ, 5NM, 1200FT, A10) as-is
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


# ---------------------------------------------------------------------------
# Summary extraction helpers
# ---------------------------------------------------------------------------

def _first_sentence(text: str, max_len: int = 120) -> str:
    """
    Extract the first meaningful sentence or clause from expanded text.
    Splits on period, semicolon, or the word 'Only' / 'Refer'.
    """
    # Split at sentence boundaries
    parts = re.split(r"[.;]|\bOnly\b|\bRefer\b", text, maxsplit=1, flags=re.IGNORECASE)
    first = parts[0].strip() if parts else text.strip()
    if len(first) > max_len:
        # Trim to last complete word within limit
        trimmed = first[:max_len].rsplit(" ", 1)[0]
        return trimmed + "…"
    return first


def _extract_runway(text: str) -> str | None:
    """Pull RWY designation from text, e.g. '07/25' or '34L'."""
    m = re.search(r"\bRWY\s+([0-3]?\d[LRC]?(?:/[0-3]?\d[LRC]?)?)\b", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_taxiway(text: str) -> str | None:
    """Pull taxiway identifier, e.g. 'Taxiway G', 'TWY B2'."""
    m = re.search(r"\bTWY\s+([A-Z][A-Z0-9]*)\b", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_freq(text: str) -> str | None:
    """Extract a radio frequency from text."""
    m = re.search(r"\b(\d{3}(?:\.\d+)?)\s*(?:MHZ|KHZ)?\b", text, re.IGNORECASE)
    return m.group(1) + " MHz" if m else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def make_summary(record: dict, max_length: int = 120) -> str:
    """
    Produce a one-line plain-English summary of a NOTAM for card display.
    """
    text_raw = _clean_raw(record.get("text_raw") or "")
    category = record.get("category", "other")
    icao = record.get("primary_icao") or "Unknown"

    if not text_raw:
        return f"{icao}: NOTAM (no detail available)"

    text_upper = text_raw.upper()

    # --- Category-specific extraction ---

    if category == "runway_closure":
        rwy = _extract_runway(text_upper)
        if rwy:
            if "CLSD" in text_upper or "CLOSED" in text_upper:
                base = f"Runway {rwy} closed"
            elif "OBST" in text_upper or "CRANE" in text_upper:
                base = f"Obstacle near Runway {rwy}"
            else:
                base = f"Runway {rwy} restriction"
        else:
            base = "Runway restriction"
        expanded = _expand(text_raw)
        first = _first_sentence(expanded, max_length)
        # If the expanded sentence already mentions the runway, it's more
        # informative on its own — don't double up with the base prefix.
        if first and rwy and rwy in first:
            return first[:max_length]
        if first and first.upper() != base.upper():
            return f"{base} — {first[:max_length - len(base) - 4]}"[:max_length]
        return base

    if category == "taxiway_closure":
        twy = _extract_taxiway(text_upper)
        expanded = _expand(text_raw)
        first = _first_sentence(expanded, max_length)
        return first or (f"Taxiway {twy} restriction" if twy else "Taxiway restriction")

    if category == "navaid_outage":
        freq = _extract_freq(text_raw)
        expanded = _expand(text_raw)
        first = _first_sentence(expanded, max_length)
        return first or (f"Navigation aid unserviceable — {freq}" if freq else "Navigation aid outage")

    if category == "gps_interference":
        return f"{icao}: GPS/GNSS interference — check NOTAMs before flight"

    if category == "obstacle_warning":
        expanded = _expand(text_raw)
        return _first_sentence(expanded, max_length)

    if category == "lighting":
        expanded = _expand(text_raw)
        return _first_sentence(expanded, max_length)

    if category == "airport_maintenance":
        expanded = _expand(text_raw)
        return _first_sentence(expanded, max_length)

    if category == "airspace_restriction":
        expanded = _expand(text_raw)
        first = _first_sentence(expanded, max_length)
        return first or f"{icao}: Airspace restriction"

    if category == "military_activity":
        expanded = _expand(text_raw)
        return _first_sentence(expanded, max_length)

    if category == "weather_related":
        expanded = _expand(text_raw)
        return _first_sentence(expanded, max_length)

    if category == "procedural_change":
        expanded = _expand(text_raw)
        return _first_sentence(expanded, max_length)

    # Default: just expand and show first sentence
    expanded = _expand(text_raw)
    return _first_sentence(expanded, max_length)


def make_detail_text(record: dict) -> str:
    """
    Produce a fully expanded, readable version of the NOTAM for the detail panel.
    """
    text_raw = _clean_raw(record.get("text_raw") or "")
    if not text_raw:
        return "(No detail text available)"
    return _expand(text_raw)


def expand_abbreviations(text: str) -> str:
    """Public helper — expand abbreviations in any text string."""
    return _expand(text)
