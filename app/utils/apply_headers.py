# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC



"""
Apply/refresh per-file license headers across the repo.

Behaviours:
- Removes existing top-of-file banners (license/copyright/SPDX/etc.)
- Inserts a unified AirTrack header using version/release info
- Preserves shebang lines (#!/usr/bin/env ...)
- Creates .bak backups when writing
- Skips JSON, binaries, minified assets, and (by default) .sql files
- Dry-run by default unless --write is given

Usage:

python app/utils/apply_headers.py \
    --release 300 \
    --version "AirTrack 1.0.0 'Wilbur'" \
    --owner 'Trevor (“Subhuti”)' \
    --year 2025 \
    --skip-glob 'data/**/*.sql' \
    --write
"""

import argparse
import fnmatch
import os
import re
from pathlib import Path
from typing import Tuple, List

# ---------------------------------------------------------------
# Defaults for Wilbur Release 300
# ---------------------------------------------------------------
DEFAULT_OWNER = "Trevor (“Subhuti”)"
DEFAULT_YEAR = "2025"
DEFAULT_VERSION = "AirTrack 1.0.0 'Wilbur'"
DEFAULT_RELEASE = "300"
LICENSE_ID = "LicenseRef-AirTrack-Proprietary-NC"

# ---------------------------------------------------------------
# Directories to skip
# ---------------------------------------------------------------
SKIP_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    ".cache",
    "site-packages",
    "migrations",
}

# ---------------------------------------------------------------
# Extensions to skip (binary or unsuitable)
# ---------------------------------------------------------------
SKIP_EXTS_BASE = {
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".pdf",
    ".zip",
    ".gz",
    ".xz",
    ".rar",
    ".7z",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".eot",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".webm",
    ".class",
    ".jar",
    ".pyc",
    ".pyo",
}

# Filenames to skip entirely
SKIP_FILES = {"LICENSE", "LICENSE.txt", "COPYING", "NOTICE"}

# Treat these as minified and skip
MINIFIED_PATTERNS = (".min.js", ".min.css")

# ---------------------------------------------------------------
# Comment style mapping
# ---------------------------------------------------------------
COMMENT_STYLE = {
    # Hash-style
    ".py": "hash",
    ".sh": "hash",
    ".bash": "hash",
    ".zsh": "hash",
    ".yml": "hash",
    ".yaml": "hash",
    ".toml": "hash",
    ".ini": "hash",
    ".cfg": "hash",
    ".conf": "hash",
    ".env": "hash",
    ".makefile": "hash",
    "makefile": "hash",
    "make": "hash",
    ".ps1": "hash",
    ".psm1": "hash",

    # C-style /* ... */
    ".js": "slashstar",
    ".mjs": "slashstar",
    ".ts": "slashstar",
    ".css": "slashstar",
    ".scss": "slashstar",
    ".less": "slashstar",
    ".c": "slashstar",
    ".h": "slashstar",
    ".cpp": "slashstar",
    ".hpp": "slashstar",

    # HTML-style <!-- ... -->
    ".html": "html",
    ".htm": "html",
    ".xml": "html",
    ".svg": "html",

    # Jinja-style
    ".jinja": "jinja",
    ".j2": "jinja",

    # Docker/Makefile
    "dockerfile": "hash",
    "makefile": "hash",
}

# ---------------------------------------------------------------
# Detect comment style
# ---------------------------------------------------------------


def detect_style(path: Path) -> str:
    name_lower = path.name.lower()
    ext_lower = path.suffix.lower()

    if name_lower in COMMENT_STYLE:
        return COMMENT_STYLE[name_lower]

    if ext_lower in COMMENT_STYLE:
        return COMMENT_STYLE[ext_lower]

    if name_lower == "dockerfile":
        return "hash"

    return ""


# ---------------------------------------------------------------
# Detect top-of-file license blocks
# ---------------------------------------------------------------
HEADER_KEYWORDS = re.compile(
    r"(copyright|all rights reserved|spdx|license|licence|permission\s+is\s+hereby)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------
# Strip existing header
# ---------------------------------------------------------------


def strip_existing_banner(text: str, style: str) -> Tuple[str, bool]:
    original = text
    lines = text.splitlines(keepends=True)

    idx = 0
    shebang = ""

    # Preserve shebang
    if lines and lines[0].startswith("#!"):
        shebang = lines[0]
        idx = 1

    # Skip blank after shebang
    if idx < len(lines) and lines[idx].strip() == "":
        idx += 1

    def join(start):
        return shebang + "".join(lines[start:])

    # -----------------------------------------------------------
    # Slash-star block
    # -----------------------------------------------------------
    if style == "slashstar" and idx < len(lines) and lines[idx].lstrip().startswith("/*"):
        end = idx
        while end < len(lines):
            if "*/" in lines[end]:
                end += 1
                break
            end += 1
        block = "".join(lines[idx:end])
        if HEADER_KEYWORDS.search(block):
            text = join(end)
            if text.startswith("\n"):
                text = text[1:]
            return text, True

    # -----------------------------------------------------------
    # Hash or SQL dash-dash
    # -----------------------------------------------------------
    if style in ("hash", "dashdash"):
        prefix = "#" if style == "hash" else "--"
        end = idx
        while end < len(lines):
            s = lines[end].lstrip()
            if s.startswith(prefix) or s.strip() == "":
                end += 1
                continue
            break
        block = "".join(lines[idx:end])
        if HEADER_KEYWORDS.search(block):
            text = join(end)
            if text.startswith("\n"):
                text = text[1:]
            return text, True

    # -----------------------------------------------------------
    # HTML <!-- -->
    # -----------------------------------------------------------
    if style == "html" and idx < len(lines) and lines[idx].lstrip().startswith("<!--"):
        end = idx
        while end < len(lines):
            if "-->" in lines[end]:
                end += 1
                break
            end += 1
        block = "".join(lines[idx:end])
        if HEADER_KEYWORDS.search(block):
            text = join(end)
            if text.startswith("\n"):
                text = text[1:]
            return text, True

    # -----------------------------------------------------------
    # Jinja {# ... #}
    # -----------------------------------------------------------
    if style == "jinja" and idx < len(lines) and lines[idx].lstrip().startswith("{#"):
        end = idx
        while end < len(lines):
            if "#}" in lines[end]:
                end += 1
                break
            end += 1
        block = "".join(lines[idx:end])
        if HEADER_KEYWORDS.search(block):
            text = join(end)
            if text.startswith("\n"):
                text = text[1:]
            return text, True

    # -----------------------------------------------------------
    # Fallback — first 30 lines heuristic
    # -----------------------------------------------------------
    look = "".join(lines[idx: idx + 30])
    if HEADER_KEYWORDS.search(look):
        end = idx
        while end < len(lines):
            s = lines[end].strip()

            if s == "":
                end += 1
                continue

            if style == "hash" and (s.startswith("#") or s.startswith("REM ")):
                end += 1
                continue

            if style == "dashdash" and s.startswith("--"):
                end += 1
                continue

            if style == "slashstar" and s.startswith("/*"):
                while end < len(lines) and "*/" not in lines[end]:
                    end += 1
                end += 1
                continue

            if style == "html" and s.startswith("<!--"):
                while end < len(lines) and "-->" not in lines[end]:
                    end += 1
                end += 1
                continue

            if style == "jinja" and s.startswith("{#"):
                while end < len(lines) and "#}" not in lines[end]:
                    end += 1
                end += 1
                continue

            break

        candidate = "".join(lines[idx:end])
        if HEADER_KEYWORDS.search(candidate) and end > idx:
            text = join(end)
            if text.startswith("\n"):
                text = text[1:]
            return text, True

    return original, False

# ---------------------------------------------------------------
# Build new header
# ---------------------------------------------------------------


def make_header(style: str, owner: str, year: str, version: str, release: str) -> str:
    banner = [
        f"{version} — Release {release}",
        f"Copyright (c) {year} {owner}. All rights reserved.",
        f"SPDX-License-Identifier: {LICENSE_ID}",
    ]

    if style == "slashstar":
        body = "\n".join(f" * {x}" for x in banner)
        return f"/*\n{body}\n */\n\n"

    if style == "hash":
        body = "\n".join(f"# {x}" for x in banner)
        return f"{body}\n\n"

    if style == "dashdash":
        body = "\n".join(f"-- {x}" for x in banner)
        return f"{body}\n\n"

    if style == "html":
        body = "\n".join(f"  {x}" for x in banner)
        return f"<!--\n{body}\n-->\n\n"

    if style == "jinja":
        body = "\n".join(f"  {x}" for x in banner)
        return f"{{#\n{body}\n#}}\n\n"

    return ""

# ---------------------------------------------------------------
# Skip logic
# ---------------------------------------------------------------


def should_skip(path: Path, include_sql: bool, skip_globs: List[str]) -> bool:
    if path.name in SKIP_FILES:
        return True

    rel = str(path.as_posix())
    for pattern in skip_globs:
        if fnmatch.fnmatch(rel, pattern):
            return True

    ext = path.suffix.lower()
    if ext in SKIP_EXTS_BASE:
        return True

    if ext == ".sql" and not include_sql:
        return True

    name = path.name.lower()
    if any(name.endswith(p) for p in MINIFIED_PATTERNS):
        return True

    return False

# ---------------------------------------------------------------
# Process a single file
# ---------------------------------------------------------------


def process_file(
    path: Path,
    owner: str,
    year: str,
    version: str,
    release: str,
    write: bool,
    include_sql: bool,
    skip_globs: List[str],
):
    style = detect_style(path)
    if not style:
        return False, False, "unsupported"

    if should_skip(path, include_sql, skip_globs):
        return False, False, "skipped"

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, False, "binary?"
    except Exception as exc:
        return False, False, f"read_error:{exc}"

    shebang = ""
    body = text

    if text.startswith("#!"):
        nl = text.find("\n")
        if nl != -1:
            shebang = text[: nl + 1]
            body = text[nl + 1:]
        else:
            shebang = text
            body = ""

    stripped, removed = strip_existing_banner(body, style)
    header = make_header(style, owner, year, version, release)

    if not header:
        return False, removed, "no_header_style"

    new_text = f"{shebang}{header}{stripped}"

    if new_text == text:
        return False, removed, "no_change"

    if write:
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            try:
                bak.write_text(text, encoding="utf-8")
            except Exception:
                pass
        path.write_text(new_text, encoding="utf-8")

    return True, removed, "updated"

# ---------------------------------------------------------------
# Walk repository
# ---------------------------------------------------------------


def walk_repo(root: Path) -> List[Path]:
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".pytest_cache")
        ]
        for fn in filenames:
            files.append(Path(dirpath) / fn)
    return files

# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        description="Apply per-file license headers with version/release metadata."
    )

    ap.add_argument("--root", default=".", help="Root folder to process")
    ap.add_argument("--owner", default=DEFAULT_OWNER)
    ap.add_argument("--year", default=DEFAULT_YEAR)
    ap.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help="Version string, e.g. \"AirTrack 1.0.0 'Wilbur'\"",
    )
    ap.add_argument("--release", default=DEFAULT_RELEASE, help="Release number")
    ap.add_argument(
        "--write",
        action="store_true",
        help="Write changes (default is a dry run)",
    )
    ap.add_argument(
        "--include-sql",
        action="store_true",
        help="Include .sql files (default: excluded)",
    )
    ap.add_argument(
        "--skip-glob",
        action="append",
        default=[],
        help="Additional glob patterns to skip",
    )

    args = ap.parse_args()

    root = Path(args.root).resolve()
    paths = walk_repo(root)

    changed = removed_count = skipped = unsupported = 0

    for p in paths:
        changed_file, banner_removed, reason = process_file(
            p,
            args.owner,
            args.year,
            args.version,
            args.release,
            args.write,
            args.include_sql,
            args.skip_glob,
        )

        if reason in ("skipped", "binary?") or reason.startswith("read_error"):
            skipped += 1
            continue

        if reason == "unsupported":
            unsupported += 1
            continue

        if changed_file:
            changed += 1
            if banner_removed:
                removed_count += 1
                print(f"[UPDATED/REPLACED] {p}")
            else:
                print(f"[UPDATED]          {p}")

    print("\nSummary:")
    print(f"  Changed:     {changed}")
    print(f"  Removed old: {removed_count}")
    print(f"  Skipped:     {skipped}")
    print(f"  Unsupported: {unsupported}")

    if not args.write:
        print("\nDry run only. Re-run with --write to apply changes.")


if __name__ == "__main__":
    main()
