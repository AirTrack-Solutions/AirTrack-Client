#!/usr/bin/env python3
# AirTrack Client Module
# app/modules/meerkat/meerkat_client.py
#
# Meerkat — optional, opt-in/opt-out installation check-in.
#
# Handles:
#   - generating and persisting a stable meerkat_id for this install
#   - registering with Wombat (POST /api/meerkat/register) when enabled
#   - deregistering with Wombat (POST /api/meerkat/deregister) when disabled
#
# Never raises out of register()/deregister() — callers get back a plain
# dict with an "ok" flag and a human-readable "message", so a Wombat
# outage never blocks the admin toggle. Matches the existing urllib POST
# pattern used by app/core/app_updater.py's rollback reporting.
#
# SAFE FOR CLIENT DISTRIBUTION.

from __future__ import annotations

import json
import os
import uuid
import urllib.error as _urlerr
import urllib.request as _req
from pathlib import Path
from typing import Any, Dict

STATE_FILE = Path(__file__).resolve().parent / "state.json"


def _read_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(state: Dict[str, Any]) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def get_or_create_meerkat_id() -> str:
    """
    Returns this install's stable meerkat_id, generating and persisting a
    new one the first time it's needed. Once created it never changes,
    so opt-out/opt-in cycles always refer to the same installation record
    on Wombat.
    """
    state = _read_state()
    meerkat_id = state.get("meerkat_id")
    if meerkat_id:
        return meerkat_id

    meerkat_id = f"meerkat-{uuid.uuid4()}"
    state["meerkat_id"] = meerkat_id
    _write_state(state)
    return meerkat_id


def _get_customer_id() -> str:
    return os.environ.get("AIRTRACK_CUSTOMER_ID", "")


def _get_wombat_url() -> str:
    return os.environ.get("WOMBAT_URL", "").rstrip("/")


def _get_license_id() -> str:
    try:
        from config.license import load_license
        return load_license().license_id
    except Exception:
        return ""


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST a JSON payload to Wombat. Never raises.

    Distinguishes two different failure shapes, since they mean very
    different things to whoever reads the flash message:
      - Wombat was reached and responded with an error (HTTPError, e.g. a
        404 "unknown customer_id" or a 403 licence mismatch) - Wombat's own
        error message is surfaced as-is. Retrying won't help; something
        about the request itself is wrong (usually provisioning).
      - Wombat genuinely couldn't be reached at all (timeout, connection
        refused, DNS failure, etc.) - reported as "Could not reach Wombat".
        Retrying once Wombat is back up may well help.
    """
    wombat_url = _get_wombat_url()
    if not wombat_url:
        return {"ok": False, "message": "WOMBAT_URL not configured — cannot reach Wombat."}

    try:
        r = _req.Request(
            f"{wombat_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "AirTrack-Client/1.0"},
            method="POST",
        )
        with _req.urlopen(r, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8") or "{}")
        return body if isinstance(body, dict) else {"ok": True}
    except _urlerr.HTTPError as exc:
        # Wombat responded - just not with success. Surface its own message
        # if it sent one (our endpoints return {"ok": false, "error": "..."}),
        # otherwise fall back to the raw HTTP status.
        try:
            body = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            body = {}
        message = body.get("error") or body.get("message") or f"HTTP {exc.code}: {exc.reason}"
        return {"ok": False, "message": f"Wombat rejected the request: {message}"}
    except Exception as exc:
        return {"ok": False, "message": f"Could not reach Wombat: {exc}"}


def register() -> Dict[str, Any]:
    """
    Register (or re-register) this installation with Wombat.
    Returns {"ok": bool, "message": str, "meerkat_id": str}.

    On success, also resets this install's heartbeat sequence_number to 0
    in state.json. Section 5.1's schema documents sequence_number as
    "monotonically increasing per install, resets only on reinstall/
    re-register" — this is the one place a genuine re-register happens
    (modules_consent() in admin_routes.py calls register() on every
    opt-in, including toggling back on after an earlier opt-out, not
    just a first-time install), so this is where the reset belongs. Only
    resets on success — a rejected or unreachable registration attempt
    hasn't actually re-registered anything, so the counter is left alone.
    See woodland/meerkat.py's _next_sequence_number() for the counter
    itself; both read/write the same state.json.
    """
    customer_id = _get_customer_id()
    license_id = _get_license_id()

    if not customer_id:
        return {"ok": False, "message": "AIRTRACK_CUSTOMER_ID not configured — cannot register with Wombat."}
    if not license_id:
        return {"ok": False, "message": "No licence found — cannot register with Wombat."}

    meerkat_id = get_or_create_meerkat_id()
    result = _post(
        "/api/meerkat/register",
        {"customer_id": customer_id, "meerkat_id": meerkat_id, "license_id": license_id},
    )
    result.setdefault("meerkat_id", meerkat_id)
    if result.get("ok"):
        result.setdefault("message", "Registered with Wombat.")
        state = _read_state()
        state["sequence_number"] = 0
        _write_state(state)
    return result


def deregister() -> Dict[str, Any]:
    """
    Deregister (opt out) this installation with Wombat.
    Returns {"ok": bool, "message": str, "meerkat_id": str}.

    Fail-open by design: callers should disable Meerkat locally regardless
    of what this returns. If Wombat couldn't be reached, that's logged as a
    warning by the caller — opting out is never blocked by a network issue.
    """
    customer_id = _get_customer_id()
    license_id = _get_license_id()
    state = _read_state()
    meerkat_id = state.get("meerkat_id")

    if not meerkat_id:
        # Never registered in the first place — nothing to tell Wombat.
        return {"ok": True, "message": "Not previously registered with Wombat — nothing to deregister."}

    if not customer_id or not license_id:
        return {
            "ok": False,
            "message": "AIRTRACK_CUSTOMER_ID or licence not configured — could not notify Wombat.",
            "meerkat_id": meerkat_id,
        }

    result = _post(
        "/api/meerkat/deregister",
        {"customer_id": customer_id, "meerkat_id": meerkat_id, "license_id": license_id},
    )
    result.setdefault("meerkat_id", meerkat_id)
    if result.get("ok"):
        result.setdefault("message", "Deregistered with Wombat.")
    return result
