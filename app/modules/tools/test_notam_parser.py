#!/usr/bin/env python3
"""
Standalone NOTAM parser smoke test.

Run from project root:
    python3 tools/test_notam_parser.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.modules.notams.normalizer import normalize_many


def main() -> int:
    sample_path = ROOT / "app" / "modules" / "notams" / "data" / "sample_notams.txt"
    raw = sample_path.read_text(encoding="utf-8")

    records = normalize_many(raw, source="test", home_icaos={"YSSY", "YSBK"})

    print(json.dumps(records, indent=2, default=str))

    if not records:
        print("No records parsed", file=sys.stderr)
        return 1

    print(f"\nParsed {len(records)} NOTAM record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
