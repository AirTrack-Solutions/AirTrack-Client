# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests


def clean_whitelist_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        lines = set(line.strip() for line in f if line.strip())
    with open(filepath, "w", encoding="utf-8") as f:
        for line in sorted(lines):
            f.write(line + "\n")


def check_url(icao, name, url, label):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, allow_redirects=True, timeout=5, headers=headers)
        return (icao, name, label, url, response.status_code < 400)
    except Exception:
        return (icao, name, label, url, False)


def load_whitelist(filepath):
    if not os.path.exists(filepath):
        return set()
    with open(filepath, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def append_to_whitelist(filepath, icao, label, url):
    entry = f"{icao}|{label}|{url}\n"
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(entry)
    key = f"{icao}|{label}|{url}"
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    with open(filepath, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip() != key:
                f.write(line)


def check_whitelist_links(output_dir, include_good=False, max_threads=10):
    whitelist_file = os.path.join(output_dir, "link_whitelist.txt")
    if not os.path.exists(whitelist_file):
        return None
    with open(whitelist_file, "r", encoding="utf-8") as f:
        entries = [line.strip().split("|") for line in f if line.strip()]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"whitelist_check_report_{timestamp}.txt"
    filepath = os.path.join(output_dir, filename)
    tasks = []
    with ThreadPoolExecutor(max_threads) as executor:
        for icao, label, url in entries:
            name = ""
            tasks.append(executor.submit(check_url, icao, name, url, label))
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("Whitelist Link Recheck Report\n")
            f.write("=" * 40 + "\n\n")
            for future in as_completed(tasks):
                icao, name, label, url, ok = future.result()
                if ok and include_good:
                    f.write(f"[{icao}] {name} — ✅ {label} OK: {url}\n")
                elif not ok:
                    f.write(f"[{icao}] {name} — ❌ Broken {label}: {url}\n")
    clean_whitelist_file(whitelist_file)
    return filename


def normalize_url(url):
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "http://" + url

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"airport_check_report_{timestamp}.txt"
    filepath = os.path.join(output_dir, filename)
    whitelist_file = os.path.join(output_dir, "link_whitelist.txt")
    whitelist = load_whitelist(whitelist_file)
    tasks = []

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        for row in results:
            try:
                icao, name, home_link, wiki_link = row
            except Exception:
                # skip malformed rows
                continue

            if home_link:
                normalized = normalize_url(home_link)
                if normalized:
                    key = f"{icao}|Website|{normalized}"
                    if key not in whitelist:
                        tasks.append(
                            executor.submit(
                                check_url, icao, name, normalized, "Website"
                            )
                        )

            if wiki_link:
                normalized = normalize_url(wiki_link)
                if normalized:
                    key = f"{icao}|Wikipedia|{normalized}"
                    if key not in whitelist:
                        tasks.append(
                            executor.submit(
                                check_url, icao, name, normalized, "Wikipedia"
                            )
                        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("Airport Link Checker Report\n")
        f.write("=" * 40 + "\n\n")
        for future in as_completed(tasks):
            icao, name, label, url, ok = future.result()
            if ok and include_good:
                f.write(f"[{icao}] {name} — ✅ {label} OK: {url}\n")
            elif not ok:
                f.write(f"[{icao}] {name} — ❌ Broken {label}: {url}\n")

    clean_whitelist_file(whitelist_file)
    return filename
