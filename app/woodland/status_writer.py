# AirTrack Solutions — Woodland Atomic Status Writer
# Copyright (c) 2025 AirTrack Solutions (ABN 70 472 536 433). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary

"""
Atomic JSON status writer for AirTrack woodland critters.

Purpose:
    Prevent partially-written JSON files from appearing in:
        app/woodland/status/*.json

Why:
    ATC reads these files live. If a critter writes directly to its .json file
    and is interrupted mid-write, ATC sees malformed JSON and marks that critter
    red. This helper writes to a temporary file first, fsyncs it, then atomically
    replaces the real status file.

Typical use:
    from app.woodland.status_writer import write_status

    write_status(
        "slothful_seth",
        status="ok",
        last_action="Mozambique: error backoff — skipping this pass",
        expected_interval_seconds=60,
    )
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# Resolve status dir relative to this file so it works regardless of volume mount layout.
# Falls back to WOODLAND_STATUS_DIR env var if set (for custom deployments).
DEFAULT_STATUS_DIR = Path(
    os.getenv(
        "WOODLAND_STATUS_DIR",
        str(Path(__file__).resolve().parent / "status"),
    )
)

# Log dir: one level up from woodland/, i.e. /app/logs/ inside the container.
# Critters that write to a central log (scheduler.log, stdout) rather than their own
# {slug}.log still touch this file on every status write — so the readiness page
# shows YES for log_file as soon as the critter has actually run.
DEFAULT_LOG_DIR = Path(
    os.getenv(
        "WOODLAND_LOG_DIR",
        str(Path(__file__).resolve().parents[1] / "logs"),
    )
)


def _now_iso() -> str:
    """
    Return a timezone-aware ISO timestamp.

    Uses the system timezone when available. In Docker, this is usually UTC
    unless TZ is configured.
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _normalise_payload(
    name: str,
    status: str = "ok",
    enabled: bool = True,
    last_action: str = "Status updated",
    expected_interval_seconds: Optional[int] = None,
    last_error: Optional[str] = None,
    consecutive_failures: int = 0,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the standard woodland status payload.

    Existing critters may add extra fields via ``extra``. Core fields are kept
    stable so ATC, Dr. Healing, and Ledger Goblin can read them consistently.
    """
    now = _now_iso()

    payload: Dict[str, Any] = {
        "name": name,
        "enabled": bool(enabled),
        "status": status,
        "last_run": now,
        "last_success": now if status.lower() in {"ok", "healthy", "idle", "running", "success", "warning"} else None,
        "last_error": last_error,
        "consecutive_failures": int(consecutive_failures or 0),
        "expected_interval_seconds": expected_interval_seconds,
        "next_expected_run": None,
        "last_action": last_action,
        "version": 1,
    }

    if expected_interval_seconds:
        try:
            from datetime import timedelta

            next_run = datetime.now().astimezone() + timedelta(seconds=int(expected_interval_seconds))
            payload["next_expected_run"] = next_run.isoformat(timespec="seconds")
        except Exception:
            payload["next_expected_run"] = None

    if extra:
        payload.update(extra)

    return payload


def atomic_write_json(path: str | Path, data: Dict[str, Any]) -> Path:
    """
    Atomically write JSON to ``path``.

    Steps:
        1. Ensure parent directory exists.
        2. Write complete JSON to a temp file in the same directory.
        3. Flush and fsync the temp file.
        4. os.replace(temp, final) so readers never see a half-written file.
        5. fsync the directory when supported.

    Returns:
        Path to the final file.
    """
    final_path = Path(path)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    temp_name = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(final_path.parent),
            prefix=f".{final_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temp_name, final_path)
        os.chmod(final_path, 0o644)  # ensure world-readable regardless of runner's umask

        try:
            dir_fd = os.open(str(final_path.parent), os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            # Some filesystems/mounts do not support directory fsync.
            pass

        return final_path

    except Exception:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except Exception:
                pass
        raise


def _touch_log(name: str, log_dir: Path) -> None:
    """
    Ensure {name}.log exists in log_dir.

    Creates an empty file if absent; if the file already exists (critters that
    manage their own log) this is a no-op — open()+close() with 'a' updates
    mtime without truncating content.

    Failures are silently swallowed: a missing log marker should never crash a
    critter that is otherwise running fine.
    """
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{name}.log"
        with log_path.open("a"):
            pass  # open in append mode: creates if absent, leaves content intact
    except Exception:
        pass


def write_status(
    name: str,
    last_action: str = "Status updated",
    status: str = "ok",
    enabled: bool = True,
    expected_interval_seconds: Optional[int] = None,
    last_error: Optional[str] = None,
    consecutive_failures: int = 0,
    status_dir: str | Path | None = None,
    log_dir: str | Path | None = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Write a standard woodland status file atomically.

    Also touches {name}.log in the logs directory so the ATC readiness page
    shows YES for log_file even for critters whose output goes to a central log
    (scheduler.log, stdout) rather than a dedicated file.

    Args:
        name:
            Critter slug, for example ``slothful_seth``.
        status:
            Usually ``ok``, ``warning``, or ``error``.
        enabled:
            Whether the critter is enabled.
        last_action:
            Human-readable summary for ATC cards.
        expected_interval_seconds:
            Optional scheduler cadence. ATC currently does not mark stale based
            on age, but Dr. Healing can use this later.
        last_error:
            Last error message, if any.
        consecutive_failures:
            Failure count.
        status_dir:
            Override output directory. Defaults to WOODLAND_STATUS_DIR or
            the status/ dir next to status_writer.py.
        log_dir:
            Override log directory. Defaults to WOODLAND_LOG_DIR or
            the logs/ dir one level above status_writer.py.
        extra:
            Optional extra fields to merge into the payload.

    Returns:
        Path to the written JSON file.
    """
    safe_name = name.strip().replace(" ", "_").lower()
    if not safe_name:
        raise ValueError("Status name cannot be empty.")

    directory = Path(status_dir) if status_dir else DEFAULT_STATUS_DIR
    payload = _normalise_payload(
        name=safe_name,
        status=status,
        enabled=enabled,
        last_action=last_action,
        expected_interval_seconds=expected_interval_seconds,
        last_error=last_error,
        consecutive_failures=consecutive_failures,
        extra=extra,
    )

    result = atomic_write_json(directory / f"{safe_name}.json", payload)

    # Touch the critter's log file. No-op if it already has content.
    _log_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    _touch_log(safe_name, _log_dir)

    return result


def write_ok(
    name: str,
    last_action: str,
    expected_interval_seconds: Optional[int] = None,
    status_dir: str | Path | None = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Convenience wrapper for successful critter runs."""
    return write_status(
        name=name,
        status="ok",
        enabled=True,
        last_action=last_action,
        expected_interval_seconds=expected_interval_seconds,
        last_error=None,
        consecutive_failures=0,
        status_dir=status_dir,
        extra=extra,
    )


def write_warning(
    name: str,
    last_action: str,
    expected_interval_seconds: Optional[int] = None,
    status_dir: str | Path | None = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Convenience wrapper for warning/degraded critter states."""
    return write_status(
        name=name,
        status="warning",
        enabled=True,
        last_action=last_action,
        expected_interval_seconds=expected_interval_seconds,
        last_error=None,
        consecutive_failures=0,
        status_dir=status_dir,
        extra=extra,
    )


def write_error(
    name: str,
    last_action: str,
    error: str,
    expected_interval_seconds: Optional[int] = None,
    consecutive_failures: int = 1,
    status_dir: str | Path | None = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Convenience wrapper for failed critter runs."""
    return write_status(
        name=name,
        status="error",
        enabled=True,
        last_action=last_action,
        expected_interval_seconds=expected_interval_seconds,
        last_error=error,
        consecutive_failures=consecutive_failures,
        status_dir=status_dir,
        extra=extra,
    )


if __name__ == "__main__":
    # Tiny manual smoke test:
    # python status_writer.py
    written = write_ok(
        "status_writer_test",
        "Atomic status writer smoke test completed",
        expected_interval_seconds=300,
    )
    print(f"Wrote {written}")
