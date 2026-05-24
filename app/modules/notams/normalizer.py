"""
NOTAM normalizer.

Combines parser + classifier + humanizer into one import-ready pipeline.
"""

from __future__ import annotations

from .classifier import classify_record
from .humanizer import make_detail_text, make_summary
from .parser import parse_notam, split_notam_blocks


def normalize_notam(raw_text: str, source: str = "manual", home_icaos: set[str] | None = None) -> dict:
    parsed = parse_notam(raw_text, source=source)
    record = classify_record(parsed.record, home_icaos=home_icaos)

    record["summary"] = make_summary(record)
    record["detail_text"] = make_detail_text(record)
    record["_parse_errors"] = parsed.errors

    return record


def normalize_many(raw: str, source: str = "manual", home_icaos: set[str] | None = None) -> list[dict]:
    blocks = split_notam_blocks(raw)
    return [normalize_notam(block, source=source, home_icaos=home_icaos) for block in blocks]
