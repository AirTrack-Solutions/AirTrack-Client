# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

# security/server_webauthn.py
# Standalone blueprint for 'server' WebAuthn login (status + register + login)

from flask import Blueprint, request, session, jsonify
import os
import pathlib
import json
import time

from webauthn import (
    generate_registration_options,
    options_to_json,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    UserVerificationRequirement,
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    RegistrationCredential,
    AuthenticationCredential,
)

# ---- Configuration via env ----

SERVER_SESSION_TTL = int(
    os.environ.get("AIRTRACK_SERVER_TTL", "300")
)  # seconds (default 5 min)

CRED_STORE = pathlib.Path(
    os.environ.get("AIRTRACK_SERVER_CRED_STORE", "app_data/server_creds.json")
)

RP_NAME = os.environ.get("AIRTRACK_RP_NAME", "AirTrack")
# RP_ID must equal the host you browse with (e.g., 'localhost')
RP_ID = os.environ.get("AIRTRACK_RP_ID")  # if None, infer from request.host

server_webauthn = Blueprint("server_webauthn", __name__)

# Ensure storage path exists (and file too)
CRED_STORE.parent.mkdir(parents=True, exist_ok=True)
if not CRED_STORE.exists():
    CRED_STORE.write_text(json.dumps({"credentials": []}, indent=2))

# ---- Helpers ----


def _now() -> int:
    return int(time.time())


def _get_rp_id() -> str:
    if RP_ID:
        return RP_ID
    # Strip port if present
    return request.host.split(":")[0]


def _load_creds() -> dict:
    try:
        return json.loads(CRED_STORE.read_text())
    except Exception:
        return {"credentials": []}


def _save_creds(data: dict):
    tmp = CRED_STORE.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2))
        tmp.rename(CRED_STORE)
    except Exception as e:
        print(f"Failed to save credentials: {e}")


def _grant_server():
    session["server"] = {
        "exp": _now() + SERVER_SESSION_TTL
    }

# ---- Public: status + logout ----


def status():
    s = session.get("server")
    if not s or s.get("exp", 0) < _now():
        session.pop("server", None)
        return jsonify({"ok": True, "is_server": False, "expires_in": 0})
    expires_in = max(0, s["exp"] - _now())
    return jsonify({"ok": True, "is_server": True, "expires_in": expires_in})


@server_webauthn.route("/server_auth/logout", methods=["POST"])
def logout():
    session.pop("server", None)
    return jsonify({"ok": True})

# ---- Registration (do this ONCE per key; disabled by default) ----


@server_webauthn.route("/server_auth/register/begin", methods=["POST"])
def register_begin():
    allow = os.environ.get("AIRTRACK_ALLOW_REGISTER", "false").lower() == "true"
    if not allow:
        return jsonify({"ok": False, "error": "Registration disabled"}), 403

    rp = PublicKeyCredentialRpEntity(id=_get_rp_id(), name=RP_NAME)
    user = PublicKeyCredentialUserEntity(
        id=os.urandom(32), name="trevor", display_name="Trevor"
    )

    selection = AuthenticatorSelectionCriteria(
        authenticator_attachment=AuthenticatorAttachment.CROSS_PLATFORM,
        resident_key="preferred",
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    opts = generate_registration_options(
        rp=rp,
        user=user,
        authenticator_selection=selection,
        attestation="none",
    )

    session["webauthn_register_chal"] = opts.challenge
    session["webauthn_register_user_id"] = bytes_to_base64url(user.id)

    return jsonify({"ok": True, "options": json.loads(options_to_json(opts))})


@server_webauthn.route("/server_auth/register/finish", methods=["POST"])
def register_finish():
    allow = os.environ.get("AIRTRACK_ALLOW_REGISTER", "false").lower() == "true"
    if not allow:
        return jsonify({"ok": False, "error": "Registration disabled"}), 403

    body = request.get_json(force=True)
    cred = RegistrationCredential.parse_raw(json.dumps(body.get("credential")))

    verification = verify_registration_response(
        credential=cred,
        expected_challenge=session.get("webauthn_register_chal"),
        expected_rp_id=_get_rp_id(),
        expected_origin=f"{request.scheme}://{request.host}",
        require_user_verification=True,
    )

    data = _load_creds()
    data.setdefault("credentials", []).append({
        "credential_id": bytes_to_base64url(verification.credential_id),
        "public_key": bytes_to_base64url(verification.credential_public_key),
        "sign_count": verification.sign_count,
        "user_handle": session.get("webauthn_register_user_id", ""),
        "label": body.get("label") or f"Key-{len(data['credentials'])+1}",
        "added": _now(),
    })

    _save_creds(data)
    session.pop("webauthn_register_chal", None)
    session.pop("webauthn_register_user_id", None)
    return jsonify({"ok": True})

# ---- Login (used by the silent hotkey) ----


@server_webauthn.route("/server_auth/login/begin", methods=["POST"])
def login_begin():
    data = _load_creds()
    creds = data.get("credentials", [])
    if not creds:
        return jsonify({"ok": False, "error": "No credentials registered"}), 404

    opts = generate_authentication_options(
        rp_id=_get_rp_id(),
        user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=[
            {
                "id": base64url_to_bytes(c["credential_id"]),
                "transports": ["usb", "nfc", "ble", "internal"],
                "type": "public-key",
            }
            for c in creds
        ],
    )

    session["webauthn_login_chal"] = opts.challenge
    return jsonify({"ok": True, "options": json.loads(options_to_json(opts))})


@server_webauthn.route("/server_auth/login/finish", methods=["POST"])
def login_finish():
    body = request.get_json(force=True)
    cred = AuthenticationCredential.parse_raw(json.dumps(body.get("credential")))

    store = _load_creds()
    creds = store.get("credentials", [])
    by_id = {c["credential_id"]: c for c in creds}
    submitted_id = bytes_to_base64url(cred.raw_id)
    reg = by_id.get(submitted_id)

    if not reg:
        return jsonify({"ok": False, "error": "Unknown credential"}), 403

    verification = verify_authentication_response(
        credential=cred,
        expected_challenge=session.get("webauthn_login_chal"),
        expected_rp_id=_get_rp_id(),
        expected_origin=f"{request.scheme}://{request.host}",
        credential_public_key=base64url_to_bytes(reg["public_key"]),
        credential_current_sign_count=reg.get("sign_count", 0),
        require_user_verification=True,
    )

    reg["sign_count"] = verification.new_sign_count
    _save_creds(store)
    session.pop("webauthn_login_chal", None)
    _grant_server()

    return jsonify({"ok": True, "expires_in": SERVER_SESSION_TTL})

