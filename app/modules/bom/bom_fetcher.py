#!/usr/bin/env python3
"""
AirTrack BOM Module - Warning Feed Fetcher

Creates:
    weather_status.json
    weather_warnings.json
    bom.log
    cache/latest_feed.xml

Run once:
    python3 bom_fetcher.py --once

Run continuously:
    python3 bom_fetcher.py

This script intentionally avoids hardwired install paths.
It uses the directory it lives in as its module directory.
"""

from __future__ import annotations

import argparse
import email.utils
import json
import os
import sys
import time
import traceback
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional


MODULE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = MODULE_DIR / "bom_config.json"
STATUS_FILE = MODULE_DIR / "weather_status.json"
WARNINGS_FILE = MODULE_DIR / "weather_warnings.json"
LOG_FILE = MODULE_DIR / "bom.log"
CACHE_DIR = MODULE_DIR / "cache"
RAW_FEED_FILE = CACHE_DIR / "latest_feed.xml"


DEFAULT_CONFIG = {
    "region_label": "NSW / ACT",
    "feed_url": "https://www.bom.gov.au/fwo/IDZ00061.warnings_land_nsw.xml",
    "refresh_seconds": 300,
    "timeout_seconds": 20,
    "user_agent": "AirTrack-BOM-Module/0.1",
    "source_name": "Bureau of Meteorology",
    "source_url": "https://www.bom.gov.au/rss/",
    "kiosk_normal_title": "WX NORMAL",
    "kiosk_normal_summary": "No active BOM warnings",
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def now_local_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    line = f"[{now_local_string()}] {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def ensure_files() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        write_json(CONFIG_FILE, DEFAULT_CONFIG)
        log(f"Created default config: {CONFIG_FILE}")


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp_path, path)


def load_config() -> Dict[str, Any]:
    ensure_files()
    config = read_json(CONFIG_FILE, {})
    merged = DEFAULT_CONFIG.copy()
    if isinstance(config, dict):
        merged.update(config)
    return merged


def fetch_url(url: str, timeout: int, user_agent: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(unescape(value).replace("\r", " ").replace("\n", " ").split())


def child_text(element: ET.Element, tag_name: str) -> str:
    child = element.find(tag_name)
    if child is None:
        return ""
    return clean_text(child.text)


def parse_rfc822_datetime(value: str) -> Optional[str]:
    if not value:
        return None

    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        return None


def classify_warning(title: str, description: str) -> Dict[str, str]:
    text = f"{title} {description}".upper()

    if any(word in text for word in ["EMERGENCY", "TSUNAMI", "CYCLONE WARNING"]):
        return {"status": "emergency", "level": "red", "label": "WX EMERGENCY"}

    if any(word in text for word in [
        "SEVERE THUNDERSTORM",
        "SEVERE WEATHER",
        "FLOOD WARNING",
        "MAJOR FLOOD",
        "EXTREME FIRE",
        "CATASTROPHIC",
    ]):
        return {"status": "severe", "level": "red", "label": "WX SEVERE"}

    if any(word in text for word in [
        "WARNING",
        "WATCH",
        "FLOOD",
        "FIRE WEATHER",
        "DAMAGING",
        "STRONG WIND",
        "GALE",
    ]):
        return {"status": "warning", "level": "amber", "label": "WX WARNING"}

    return {"status": "advisory", "level": "amber", "label": "WX ADVISORY"}


def warning_rank(status: str) -> int:
    ranks = {
        "normal": 0,
        "advisory": 1,
        "warning": 2,
        "severe": 3,
        "emergency": 4,
    }
    return ranks.get(status, 0)


def parse_rss(xml_bytes: bytes, config: Dict[str, Any]) -> Dict[str, Any]:
    root = ET.fromstring(xml_bytes)

    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS channel element not found.")

    feed_title = child_text(channel, "title")
    feed_description = child_text(channel, "description")
    feed_link = child_text(channel, "link")
    feed_pub_date = child_text(channel, "pubDate")

    warnings: List[Dict[str, Any]] = []

    for item in channel.findall("item"):
        title = child_text(item, "title")
        description = child_text(item, "description")
        link = child_text(item, "link")
        guid = child_text(item, "guid")
        pub_date = child_text(item, "pubDate")

        classification = classify_warning(title, description)

        warnings.append({
            "id": guid or link or title,
            "title": title,
            "summary": description,
            "link": link,
            "published": pub_date,
            "published_utc": parse_rfc822_datetime(pub_date),
            "status": classification["status"],
            "level": classification["level"],
            "label": classification["label"],
            "source": config.get("source_name", "Bureau of Meteorology"),
        })

    warnings.sort(
        key=lambda item: (
            warning_rank(str(item.get("status", "normal"))),
            str(item.get("published_utc") or ""),
        ),
        reverse=True,
    )

    return {
        "ok": True,
        "region": config.get("region_label", ""),
        "source": config.get("source_name", "Bureau of Meteorology"),
        "source_url": config.get("source_url", ""),
        "feed_url": config.get("feed_url", ""),
        "feed_title": feed_title,
        "feed_description": feed_description,
        "feed_link": feed_link,
        "feed_published": feed_pub_date,
        "feed_published_utc": parse_rfc822_datetime(feed_pub_date),
        "updated": now_local_string(),
        "updated_utc": now_utc_iso(),
        "count": len(warnings),
        "items": warnings,
    }


def build_status(warnings_payload: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    items = warnings_payload.get("items", [])
    if not isinstance(items, list):
        items = []

    if not items:
        return {
            "ok": True,
            "status": "normal",
            "level": "green",
            "label": "WX",
            "title": config.get("kiosk_normal_title", "WX NORMAL"),
            "summary": config.get("kiosk_normal_summary", "No active BOM warnings"),
            "region": config.get("region_label", ""),
            "updated": now_local_string(),
            "updated_utc": now_utc_iso(),
            "count": 0,
            "source": config.get("source_name", "Bureau of Meteorology"),
            "source_url": config.get("source_url", ""),
            "top_warning": None,
        }

    top = items[0]
    status = str(top.get("status") or "warning")
    level = str(top.get("level") or "amber")
    title = str(top.get("label") or "WX WARNING")
    summary = str(top.get("title") or "Active BOM warning")

    return {
        "ok": True,
        "status": status,
        "level": level,
        "label": "WX",
        "title": title,
        "summary": summary,
        "region": config.get("region_label", ""),
        "updated": now_local_string(),
        "updated_utc": now_utc_iso(),
        "count": len(items),
        "source": config.get("source_name", "Bureau of Meteorology"),
        "source_url": config.get("source_url", ""),
        "top_warning": top,
    }


def build_error_status(error_message: str, config: Dict[str, Any]) -> Dict[str, Any]:
    previous = read_json(STATUS_FILE, {})
    if isinstance(previous, dict) and previous.get("ok") is True:
        previous["stale"] = True
        previous["last_error"] = error_message
        previous["error_updated"] = now_local_string()
        previous["error_updated_utc"] = now_utc_iso()
        return previous

    return {
        "ok": False,
        "status": "error",
        "level": "red",
        "label": "WX",
        "title": "WX ERROR",
        "summary": error_message,
        "region": config.get("region_label", ""),
        "updated": now_local_string(),
        "updated_utc": now_utc_iso(),
        "count": 0,
        "source": config.get("source_name", "Bureau of Meteorology"),
        "source_url": config.get("source_url", ""),
        "top_warning": None,
    }


def run_once() -> bool:
    config = load_config()
    feed_url = str(config.get("feed_url") or "").strip()

    if not feed_url:
        message = "No feed_url configured in bom_config.json."
        write_json(STATUS_FILE, build_error_status(message, config))
        log(message)
        return False

    try:
        timeout = int(config.get("timeout_seconds", 20))
        user_agent = str(config.get("user_agent", "AirTrack-BOM-Module/0.1"))

        log(f"Fetching BOM feed for {config.get('region_label', 'configured region')}")
        xml_bytes = fetch_url(feed_url, timeout, user_agent)

        RAW_FEED_FILE.write_bytes(xml_bytes)

        warnings_payload = parse_rss(xml_bytes, config)
        status_payload = build_status(warnings_payload, config)

        write_json(WARNINGS_FILE, warnings_payload)
        write_json(STATUS_FILE, status_payload)

        log(
            "Updated weather files: "
            f"{warnings_payload.get('count', 0)} warnings, "
            f"status={status_payload.get('status')}"
        )
        return True

    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        write_json(STATUS_FILE, build_error_status(message, config))
        log(f"ERROR: {message}")
        log(traceback.format_exc())
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="AirTrack BOM warning feed fetcher")
    parser.add_argument("--once", action="store_true", help="Fetch once, write JSON files, then exit.")
    args = parser.parse_args()

    config = load_config()

    if args.once:
        return 0 if run_once() else 1

    refresh_seconds = int(config.get("refresh_seconds", 300))
    if refresh_seconds < 60:
        refresh_seconds = 60

    log(f"Starting BOM fetch loop, refresh_seconds={refresh_seconds}")

    while True:
        run_once()
        time.sleep(refresh_seconds)


if __name__ == "__main__":
    sys.exit(main())
