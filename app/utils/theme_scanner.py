# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC




# utils/theme_scanner.py
# AirTrack 1.0.0 'Wilbur' — Release 300
from __future__ import annotations

import datetime

import json

import os

import tempfile

from pathlib import Path
# NEW: file lock so multiple workers don't regenerate at once
import fcntl

BASE_DIR = Path(__file__).resolve().parent.parent  # /app

STATIC_DIR = Path(os.environ.get('AIRTRACK_STATIC_DIR', '/app/static')).resolve()

THEMES_DIR = STATIC_DIR / 'themes'

CSS_DIR = STATIC_DIR / 'css'

THEMES_JSON = THEMES_DIR / 'themes.json'

THEMES_CSS = CSS_DIR / 'themes.css'

# lock file lives alongside outputs
LOCKFILE = THEMES_DIR / '.themesgen.lock'

IMG_EXTS = {'.png', '.jpg', '.jpeg', '.webp'}

# ---------- helpers for staleness ----------


def _latest_theme_asset_mtime() -> int:
    latest = 0
    if THEMES_DIR.exists():
        for p in THEMES_DIR.iterdir():
            try:
                if p.is_file() and p.suffix.lower() in IMG_EXTS:
                    latest = max(latest, int(p.stat().st_mtime))
            except Exception:
                pass
    return latest


def _outputs_mtime() -> int:
    mts = []
    for p in (THEMES_JSON, THEMES_CSS):
        if p.exists():
            try:
                mts.append(int(p.stat().st_mtime))
            except Exception:
                pass
    # if either output is missing, force a rescan
    return min(mts) if mts else 0


def scan_if_stale() -> bool:
    """Regenerate themes.json/css if any asset is newer than our outputs."""
    try:
        latest_in = _latest_theme_asset_mtime()
        latest_out = _outputs_mtime()
        if latest_out == 0 or latest_in > latest_out:
            scan_and_generate()
            return True
    except Exception:
        # never break requests because of theme scanning
        pass
    return False


def _exists_any(path_stem: Path) -> Path | None:
    for ext in IMG_EXTS:
        p = path_stem.with_suffix(ext)
        if p.exists():
            return p
    return None


def _mtime_version(p: Path) -> int:
    try:
        return int(p.stat().st_mtime)
    except Exception:
        return int(datetime.datetime.now().timestamp())
# ---------- locking helpers ----------


def _acquire_lock() -> int | None:
    """
    Acquire an exclusive lock across processes.
    Returns an OS fd you must close, or None if locking isn't possible.
    """
    try:
        THEMES_DIR.mkdir(parents=True, exist_ok=True)
        fd = os.open(LOCKFILE, os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd
    except Exception:
        # If we can't lock (exotic FS), just continue without it.
        return None


def _release_lock(fd: int | None):
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        try:
            os.close(fd)
        except Exception:
            pass
# ---------- main scan ----------


def scan_and_generate() -> list[dict]:
    # Ensure directories exist (idempotent)
    THEMES_DIR.mkdir(parents=True, exist_ok=True)
    CSS_DIR.mkdir(parents=True, exist_ok=True)

    # Acquire inter-process lock so only one worker writes files
    lock_fd = _acquire_lock()

    try:
        # If another worker just generated while we waited, bail early
        try:
            latest_in = _latest_theme_asset_mtime()
            latest_out = _outputs_mtime()

            if (
                latest_out
                and latest_in <= latest_out
                and THEMES_JSON.exists()
                and THEMES_CSS.exists()
            ):
                return []

        except Exception:
            pass

        themes: list[dict] = []
        css_rules: list[str] = []

        css_rules.append(
            """
.background{
position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:-1;
background-size:cover; background-position:center; background-repeat:no-repeat;
}""".strip()
        )

        candidates = [
            p
            for p in THEMES_DIR.iterdir()
            if p.is_file()
            and p.suffix.lower() in IMG_EXTS
            and p.name.endswith("_cockpit" + p.suffix)
        ]

        candidates.sort(key=lambda p: p.stem.replace("_cockpit", "").lower())
        missing: list[str] = []

        for cockpit in candidates:
            theme_key = cockpit.stem.replace("_cockpit", "")
            thumb = _exists_any(THEMES_DIR / f"{theme_key}_thumb")
            bg = _exists_any(THEMES_DIR / f"{theme_key}_background")

            if not thumb or not bg:
                m = []
                if not thumb:
                    m.append("thumb")
                if not bg:
                    m.append("background")
                missing.append(f"{theme_key} (missing: {', '.join(m)})")
                continue

            display = theme_key.replace("_", " ").strip().capitalize()
            v_cockpit = _mtime_version(cockpit)
            v_bg = _mtime_version(bg)
            v_thumb = _mtime_version(thumb)

            themes.append(
                {
                    "key": theme_key,
                    "value": theme_key,
                    "label": display,
                    "name": display,
                    "thumb_url": f"/static/themes/{thumb.name}?v={v_thumb}",
                    "cockpit_url": f"/static/themes/{cockpit.name}?v={v_cockpit}",
                    "background_url": f"/static/themes/{bg.name}?v={v_bg}",
                }
            )

            css_rules.append(
                f"""
.theme-{theme_key} .admin-background {{
background-image:url('/static/themes/{cockpit.name}?v={v_cockpit}');
background-size:cover; background-position:center; background-repeat:no-repeat;
}}""".strip()
            )

            css_rules.append(
                f"""
.theme-{theme_key} .background {{
background-image:url('/static/themes/{bg.name}?v={v_bg}');
background-size:cover; background-position:center; background-repeat:no-repeat;
}}""".strip()
            )

        # ---- write themes.json atomically ----
        with tempfile.NamedTemporaryFile(
            "w",
            dir=str(THEMES_DIR),
            delete=False,
            suffix=".json.tmp",
            encoding="utf-8",
        ) as jf:
            json.dump(themes, jf, indent=2, ensure_ascii=False)
            tmp_json = Path(jf.name)

        os.replace(tmp_json, THEMES_JSON)

        # ---- write themes.css atomically ----
        with tempfile.NamedTemporaryFile(
            "w",
            dir=str(CSS_DIR),
            delete=False,
            suffix=".css.tmp",
            encoding="utf-8",
        ) as cf:
            timestamp = datetime.datetime.now().isoformat()
            cf.write(f"/* Auto-generated on {timestamp} */\n")
            cf.write("\n\n".join(css_rules) + "\n")
            tmp_css = Path(cf.name)

        os.replace(tmp_css, THEMES_CSS)

        print(
            f"✅ Generated {THEMES_JSON.name} "
            f"({len(themes)} themes) and {THEMES_CSS.name}"
        )

        if missing:
            print("⚠️ Skipped incomplete theme sets:")
            for m in missing:
                print(f"   - {m}")

        return themes

    finally:
        _release_lock(lock_fd)


def scan_all() -> list[dict]:
    return scan_and_generate()


if __name__ == "__main__":
    scan_and_generate()
