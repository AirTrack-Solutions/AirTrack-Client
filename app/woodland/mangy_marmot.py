"""
AirTrack - Mangy Marmot
woodland/mangy_marmot.py v0.2

Capability delivery agent. Runs on a schedule inside the AirTrack client.

Responsibilities:
  1. Fetch warehouse manifest from Wombat (required_core_packages).
  2. Scan installed capabilities from $AIRTRACK_HOME/capabilities/.
  3. Report installed_capabilities to Wombat.
  4. For each missing required core package - run the full HTTP delivery cycle:
       request pickup → retrieve package → verify signature + SHA-256 → install → confirm.

Environment:
  WOMBAT_URL              URL of Wombat API server (e.g. http://192.168.0.201:5200)
  AIRTRACK_HOME           Root data directory (capabilities, downloads, staging, etc.)
  AIRTRACK_CUSTOMER_ID    Customer identifier registered in the Wombat warehouse
  AIRTRACK_LICENSE_KEY    License key (sent in reports; optional for core delivery)
"""

from __future__ import annotations

import base64
import hashlib
import io
import importlib.util
import json
import logging
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

WOMBAT_URL       = os.getenv("WOMBAT_URL", "").rstrip("/")
_default_home = (
    Path(os.environ.get("ProgramData", "C:/ProgramData")) / "AirTrack"
    if sys.platform == "win32"
    else Path("/airtrack_data")
)
AIRTRACK_HOME    = Path(os.getenv("AIRTRACK_HOME", str(_default_home)))
CUSTOMER_ID      = os.getenv("AIRTRACK_CUSTOMER_ID", "")
LICENSE_KEY      = os.getenv("AIRTRACK_LICENSE_KEY", "")
WOMBAT_TIMEOUT   = int(os.getenv("WOMBAT_TIMEOUT", "30"))

CAPABILITIES_DIR = AIRTRACK_HOME / "capabilities"
DOWNLOADS_DIR    = AIRTRACK_HOME / "downloads"
STAGING_DIR      = AIRTRACK_HOME / "staging"
STATUS_DIR       = AIRTRACK_HOME / "status" / "capabilities"
CORE_DIR         = AIRTRACK_HOME / "core"
PUBLIC_KEY_PATH  = CORE_DIR / "airtrack_solutions.pub"
LOG_DIR              = AIRTRACK_HOME / "logs"
REGISTRIES_INCOMING  = AIRTRACK_HOME / "registries" / "incoming"
REGISTRIES_INSTALLED  = AIRTRACK_HOME / "registries" / "installed"
UPDATE_SCHEDULE_PATH  = AIRTRACK_HOME / "registry_update_schedule.json"
REGISTRIES_MANIFESTS = AIRTRACK_HOME / "registries" / "manifests"

# Public key source from git repo (copied to AIRTRACK_HOME on first run)
_REPO_PUBLIC_KEY = Path(__file__).resolve().parent.parent / "core" / "airtrack_solutions.pub"
_REPO_INSTALLER  = Path(__file__).resolve().parent.parent / "core" / "package_installer.py"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger("mangy_marmot")


def _log(msg: str) -> None:
    log.info(msg)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / "mangy_marmot.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{_now_iso()} {msg}\n")
    except Exception:
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Bootstrap: seed AIRTRACK_HOME/core/ from repo on first run
# ---------------------------------------------------------------------------

def _bootstrap_core() -> None:
    CORE_DIR.mkdir(parents=True, exist_ok=True)
    if not PUBLIC_KEY_PATH.exists() and _REPO_PUBLIC_KEY.exists():
        shutil.copy2(_REPO_PUBLIC_KEY, PUBLIC_KEY_PATH)
        _log(f"Bootstrapped public key → {PUBLIC_KEY_PATH}")
    installer_path = CORE_DIR / "package_installer.py"
    if not installer_path.exists() and _REPO_INSTALLER.exists():
        shutil.copy2(_REPO_INSTALLER, installer_path)
        _log(f"Bootstrapped package_installer → {installer_path}")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(path: str) -> dict:
    req = Request(f"{WOMBAT_URL}{path}", headers={"User-Agent": "AirTrack-MangyMarmot/0.1"})
    with urlopen(req, timeout=WOMBAT_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req  = Request(
        f"{WOMBAT_URL}{path}", data=data,
        headers={"Content-Type": "application/json", "User-Agent": "AirTrack-MangyMarmot/0.1"},
        method="POST",
    )
    with urlopen(req, timeout=WOMBAT_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Capability inventory
# ---------------------------------------------------------------------------

def _scan_installed() -> list[dict]:
    if not CAPABILITIES_DIR.exists():
        return []
    installed = []
    for cap_dir in sorted(CAPABILITIES_DIR.iterdir()):
        if not cap_dir.is_dir():
            continue
        manifest_path = cap_dir / "manifest.json"
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            installed.append({"name": cap_dir.name, "version": m.get("version", "unknown")})
        except Exception:
            installed.append({"name": cap_dir.name, "version": "unknown"})
    return installed


# ---------------------------------------------------------------------------
# Package verification (SHA-256 + Ed25519)
# ---------------------------------------------------------------------------

def _verify_package(zip_bytes: bytes, expected_sha256: str) -> str | None:
    actual_sha = hashlib.sha256(zip_bytes).hexdigest()
    if actual_sha != expected_sha256:
        return f"SHA-256 mismatch: expected {expected_sha256[:16]}…, got {actual_sha[:16]}…"

    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        return "cryptography library not installed"

    if not PUBLIC_KEY_PATH.exists():
        return f"Public key not found: {PUBLIC_KEY_PATH}"

    try:
        pub = load_pem_public_key(PUBLIC_KEY_PATH.read_bytes())
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            checksums_data = zf.read("checksums.sha256")
            signature      = zf.read("signature.sig")
            pub.verify(signature, checksums_data)
    except InvalidSignature:
        return "Ed25519 signature verification failed"
    except Exception as exc:
        return f"Package verification error: {exc}"

    return None


# ---------------------------------------------------------------------------
# Install via package_installer
# ---------------------------------------------------------------------------

def _install_package(package_path: Path) -> None:
    installer_path = CORE_DIR / "package_installer.py"
    if not installer_path.exists():
        raise FileNotFoundError(f"package_installer.py not found at {installer_path}")

    os.environ["AIRTRACK_HOME"] = str(AIRTRACK_HOME)
    os.environ.setdefault("AIRTRACK_VERSION", "1.0.0")

    spec   = importlib.util.spec_from_file_location("package_installer", installer_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["package_installer"] = module
    spec.loader.exec_module(module)

    result = module.validate_package(package_path)
    if not result.valid:
        parts = list(result.errors or [])
        if getattr(result, "healthcheck_error", None):
            parts.append(f"Healthcheck: {result.healthcheck_error}")
        errs = "; ".join(parts)
        raise RuntimeError(f"Install failed: {errs}")
    _log(f"Install: '{result.package_name}' v{result.package_version} installed")


# ---------------------------------------------------------------------------
# Delivery cycle
# ---------------------------------------------------------------------------

def _deliver(capability: str) -> bool:
    _log(f"Delivery: starting for '{capability}'")

    try:
        manifest = _get(f"/api/wombat/manifest/{CUSTOMER_ID}")
    except Exception as exc:
        _log(f"Delivery: manifest fetch failed - {exc}"); return False

    if manifest.get("error"):
        _log(f"Delivery: manifest error - {manifest['error']}"); return False

    matching = [d for d in manifest.get("deliveries", []) if d.get("capability") == capability]
    if not matching:
        _log(f"Delivery: no dispatched delivery for '{capability}' - requesting from warehouse")
        try:
            cap_req = _post("/api/wombat/request-capability", {
                "customer_id": CUSTOMER_ID,
                "capability":  capability,
            })
        except Exception as exc:
            _log(f"Delivery: request-capability failed - {exc}"); return False
        if cap_req.get("status") != "dispatched":
            _log(f"Delivery: request-capability returned '{cap_req.get('status')}' - {cap_req.get('note', cap_req.get('error', ''))}"); return False
        # Re-fetch manifest so we have the freshly dispatched delivery
        try:
            manifest = _get(f"/api/wombat/manifest/{CUSTOMER_ID}")
        except Exception as exc:
            _log(f"Delivery: manifest re-fetch failed - {exc}"); return False
        matching = [d for d in manifest.get("deliveries", []) if d.get("capability") == capability]
        if not matching:
            _log(f"Delivery: warehouse dispatched but manifest not yet updated - will retry"); return False

    delivery   = matching[0]
    request_id = delivery["request_id"]
    pkg_sha    = delivery["package_sha256"]
    _log(f"Delivery: request_id={request_id}")

    try:
        pickup = _post("/api/wombat/request-pickup", {"customer_id": CUSTOMER_ID, "request_id": request_id})
    except Exception as exc:
        _log(f"Delivery: request-pickup failed - {exc}"); return False
    if not pickup.get("allowed"):
        _log(f"Delivery: pickup not allowed - {pickup.get('error')}"); return False

    token = pickup["pickup_token"]

    try:
        retrieval = _post("/api/wombat/retrieve-package", {"customer_id": CUSTOMER_ID, "token": token})
    except Exception as exc:
        _log(f"Delivery: retrieve failed - {exc}"); return False
    if not retrieval.get("ok"):
        _log(f"Delivery: retrieve error - {retrieval.get('error')}"); return False

    zip_bytes = base64.b64decode(retrieval["package_bytes"])

    dl_dir = DOWNLOADS_DIR / request_id
    dl_dir.mkdir(parents=True, exist_ok=True)
    package_path = dl_dir / "package.zip"
    package_path.write_bytes(zip_bytes)
    _log(f"Delivery: saved {len(zip_bytes)} bytes")

    err = _verify_package(zip_bytes, pkg_sha)
    if err:
        _log(f"Delivery: verification failed - {err}")
        package_path.unlink(missing_ok=True)
        return False
    _log("Delivery: signature + SHA-256 verified")

    try:
        _install_package(package_path)
    except Exception as exc:
        _log(f"Delivery: install error - {exc}"); return False

    try:
        confirm = _post("/api/wombat/confirm-pickup", {
            "customer_id":     CUSTOMER_ID,
            "token":           token,
            "received_sha256": hashlib.sha256(zip_bytes).hexdigest(),
        })
        _log(f"Delivery: confirmed - {confirm.get('status', confirm.get('error'))}")
    except Exception as exc:
        _log(f"Delivery: confirm failed (non-fatal) - {exc}")

    return True




# ---------------------------------------------------------------------------
# Registry update scheduler — jittered delivery to prevent thundering herd
# ---------------------------------------------------------------------------

def _load_update_schedule() -> dict:
    try:
        return json.loads(UPDATE_SCHEDULE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_update_schedule(schedule: dict) -> None:
    UPDATE_SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = UPDATE_SCHEDULE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    tmp.replace(UPDATE_SCHEDULE_PATH)


def _schedule_registry_update(slug: str, target_version: str, window_hours: int) -> str:
    """
    Calculate and persist a jittered update time for slug→target_version.
    Returns the ISO scheduled_at string.
    Uses a deterministic hash of (customer_id, slug, version) so the same
    client always gets the same offset for a given release.
    """
    import hashlib as _hl
    from datetime import timedelta as _td
    seed_str  = f"{CUSTOMER_ID}:{slug}:{target_version}"
    seed_int  = int(_hl.sha256(seed_str.encode()).hexdigest(), 16)
    delay_min = seed_int % max(1, window_hours * 60)
    from datetime import datetime as _dt2, timezone as _tz2
    scheduled = _dt2.now(_tz2.utc) + _td(minutes=delay_min)
    scheduled_iso = scheduled.isoformat(timespec="seconds")
    schedule = _load_update_schedule()
    schedule[slug] = {
        "target_version": target_version,
        "scheduled_at":   scheduled_iso,
        "window_hours":   window_hours,
    }
    _save_update_schedule(schedule)
    _log(f"Registry update scheduled: {slug} → {target_version} at {scheduled_iso} "
         f"(+{delay_min}min, window={window_hours}h)")
    return scheduled_iso


def _get_scheduled_update(slug: str, target_version: str):
    """
    Return the scheduled_at datetime for (slug, target_version) or None if
    not yet scheduled or already superseded by a different target_version.
    """
    from datetime import datetime as _dt
    schedule = _load_update_schedule()
    entry = schedule.get(slug)
    if not entry or entry.get("target_version") != target_version:
        return None
    try:
        return _dt.fromisoformat(entry["scheduled_at"])
    except Exception:
        return None


def _clear_scheduled_update(slug: str) -> None:
    schedule = _load_update_schedule()
    if slug in schedule:
        del schedule[slug]
        _save_update_schedule(schedule)


# ---------------------------------------------------------------------------
# Registry inventory
# ---------------------------------------------------------------------------

def _scan_installed_registries() -> list[dict]:
    """Return list of installed registries from REGISTRIES_INSTALLED/."""
    if not REGISTRIES_INSTALLED.exists():
        return []
    installed = []
    for reg_dir in sorted(REGISTRIES_INSTALLED.iterdir()):
        if not reg_dir.is_dir():
            continue
        manifest_path = reg_dir / "installed.json"
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            installed.append({"name": reg_dir.name, "version": m.get("version", "unknown")})
        except Exception:
            installed.append({"name": reg_dir.name, "version": "unknown"})
    return installed


# ---------------------------------------------------------------------------
# Registry installation
# ---------------------------------------------------------------------------

def _install_registry(package_path: Path, registry_name: str) -> None:
    """Extract SQL from registry package and import into MariaDB."""
    import re
    import zipfile as _zf

    with _zf.ZipFile(package_path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        sql_file = manifest.get("sql_file", "registry.sql")
        sql_content = zf.read(sql_file).decode("utf-8")

    table_name = manifest.get("table_name", registry_name)

    # Split SQL into individual statements by line.
    # One statement per line is guaranteed by the Wombat package generator.
    # We do NOT use regex here — semicolons can appear inside string values
    # and a regex cannot distinguish them from statement terminators.
    inserts = [
        line.strip() for line in sql_content.splitlines()
        if line.strip() and not line.strip().startswith("--") and not line.strip().startswith("#")
    ]
    if not inserts:
        raise RuntimeError(f"No SQL statements found in {sql_file}")

    # Parse DB connection from DATABASE_URI env var
    try:
        import pymysql
        from urllib.parse import urlparse
        db_uri = os.environ.get("DATABASE_URI", "")
        if db_uri:
            # mysql+pymysql://user:pass@host:port/dbname?...
            parsed = urlparse(db_uri.replace("mysql+pymysql://", "mysql://"))
            host     = parsed.hostname or "127.0.0.1"
            port     = parsed.port or 3306
            user     = parsed.username or "airtrack"
            password = parsed.password or ""
            database = (parsed.path or "/airtrack").lstrip("/")
        else:
            host_port = os.environ.get("DB_HOST", "127.0.0.1:3306").split(":")
            host     = host_port[0]
            port     = int(host_port[1]) if len(host_port) > 1 else 3306
            user     = os.environ.get("DB_USER", "airtrack")
            password = os.environ.get("DB_PASSWORD", "")
            database = os.environ.get("DB_NAME", "airtrack")

        conn = pymysql.connect(
            host=host, port=int(port), user=user, password=password,
            database=database, charset="utf8mb4",
            connect_timeout=10,
        )
        merge_mode = manifest.get("merge", False)
        try:
            with conn.cursor() as cursor:
                if not merge_mode:
                    cursor.execute(f"DELETE FROM `{table_name}`")
                for stmt in inserts:
                    cursor.execute(stmt)
            conn.commit()
            mode_label = "merged" if merge_mode else "replaced"
            _log(f"Registry '{registry_name}': {mode_label} {len(inserts)} row(s) into `{table_name}`")
        finally:
            conn.close()
    except Exception as exc:
        raise RuntimeError(f"DB import failed: {exc}")

    # Write installed manifest
    installed_dir = REGISTRIES_INSTALLED / registry_name
    installed_dir.mkdir(parents=True, exist_ok=True)
    installed_manifest = {
        "name":         registry_name,
        "version":      manifest.get("version", "1.0.0"),
        "table_name":   table_name,
        "installed_at": _now_iso(),
    }
    (installed_dir / "installed.json").write_text(
        json.dumps(installed_manifest, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Registry delivery cycle
# ---------------------------------------------------------------------------

def _deliver_registry(registry: str) -> bool:
    _log(f"Registry delivery: starting for '{registry}'")

    try:
        manifest = _get(f"/api/wombat/manifest/{CUSTOMER_ID}")
    except HTTPError as exc:
        if exc.code == 404:
            _log(f"Registry delivery: customer ID '{CUSTOMER_ID}' not recognised by Wombat — provision via ATC before Marmot can deliver"); return False
        _log(f"Registry delivery: manifest fetch failed - {exc}"); return False
    except Exception as exc:
        _log(f"Registry delivery: manifest fetch failed - {exc}"); return False

    if manifest.get("error"):
        _log(f"Registry delivery: manifest error - {manifest['error']}"); return False

    matching = [d for d in manifest.get("deliveries", []) if d.get("capability") == registry]
    if not matching:
        _log(f"Registry delivery: no dispatched delivery for '{registry}' - requesting")
        try:
            reg_req = _post("/api/wombat/request-registry", {
                "customer_id": CUSTOMER_ID,
                "registry":    registry,
            })
        except Exception as exc:
            _log(f"Registry delivery: request-registry failed - {exc}"); return False
        if reg_req.get("status") != "dispatched":
            _log(f"Registry delivery: request returned '{reg_req.get('status')}' - {reg_req.get('note', reg_req.get('error', ''))}"); return False
        try:
            manifest = _get(f"/api/wombat/manifest/{CUSTOMER_ID}")
        except Exception as exc:
            _log(f"Registry delivery: manifest re-fetch failed - {exc}"); return False
        matching = [d for d in manifest.get("deliveries", []) if d.get("capability") == registry]
        if not matching:
            _log(f"Registry delivery: dispatched but manifest not yet updated - will retry"); return False

    delivery   = matching[0]
    request_id = delivery["request_id"]
    pkg_sha    = delivery["package_sha256"]
    _log(f"Registry delivery: request_id={request_id}")

    try:
        pickup = _post("/api/wombat/request-pickup", {"customer_id": CUSTOMER_ID, "request_id": request_id})
    except Exception as exc:
        _log(f"Registry delivery: request-pickup failed - {exc}"); return False
    if not pickup.get("allowed"):
        _log(f"Registry delivery: pickup not allowed - {pickup.get('error')}"); return False

    token = pickup["pickup_token"]

    try:
        retrieval = _post("/api/wombat/retrieve-package", {"customer_id": CUSTOMER_ID, "token": token})
    except Exception as exc:
        _log(f"Registry delivery: retrieve failed - {exc}"); return False
    if not retrieval.get("ok"):
        _log(f"Registry delivery: retrieve error - {retrieval.get('error')}"); return False

    zip_bytes = base64.b64decode(retrieval["package_bytes"])

    dl_dir = DOWNLOADS_DIR / request_id
    dl_dir.mkdir(parents=True, exist_ok=True)
    package_path = dl_dir / "package.zip"
    package_path.write_bytes(zip_bytes)
    _log(f"Registry delivery: saved {len(zip_bytes)} bytes")

    err = _verify_package(zip_bytes, pkg_sha)
    if err:
        _log(f"Registry delivery: verification failed - {err}")
        package_path.unlink(missing_ok=True)
        return False
    _log("Registry delivery: signature + SHA-256 verified")

    try:
        _install_registry(package_path, registry)
    except Exception as exc:
        _log(f"Registry delivery: install error - {exc}"); return False

    try:
        confirm = _post("/api/wombat/confirm-pickup", {
            "customer_id":     CUSTOMER_ID,
            "token":           token,
            "received_sha256": hashlib.sha256(zip_bytes).hexdigest(),
        })
        _log(f"Registry delivery: confirmed - {confirm.get('status', confirm.get('error'))}")
    except Exception as exc:
        _log(f"Registry delivery: confirm failed (non-fatal) - {exc}")

    return True


# ---------------------------------------------------------------------------
# Registry delivery preferences
# ---------------------------------------------------------------------------

def _get_registry_pref() -> str:
    """Read registry_updates preference from app_settings DB. Returns 'automatic', 'ask', or 'never'."""
    try:
        import pymysql as _pym
        from urllib.parse import urlparse as _up
        db_uri = os.environ.get("DATABASE_URI", "")
        if db_uri:
            parsed = _up(db_uri.replace("mysql+pymysql://", "mysql://"))
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 3306
            user = parsed.username or "airtrack"
            password = parsed.password or ""
            database = (parsed.path or "/airtrack").lstrip("/")
        else:
            hp = os.environ.get("DB_HOST", "127.0.0.1:3306").split(":")
            host = hp[0]; port = int(hp[1]) if len(hp) > 1 else 3306
            user = os.environ.get("DB_USER", "airtrack")
            password = os.environ.get("DB_PASSWORD", "")
            database = os.environ.get("DB_NAME", "airtrack")
        conn = _pym.connect(host=host, port=int(port), user=user, password=password,
                            database=database, charset="utf8mb4", connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT SettingValue FROM app_settings WHERE SettingKey='registry_updates' LIMIT 1")
                row = cur.fetchone()
                return row[0] if row else "automatic"
        finally:
            conn.close()
    except Exception:
        return "automatic"


def _read_pending_registries() -> list:
    pending_path = REGISTRIES_MANIFESTS / "pending.json"
    try:
        if pending_path.exists():
            return json.loads(pending_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _write_pending_registries(names: list) -> None:
    REGISTRIES_MANIFESTS.mkdir(parents=True, exist_ok=True)
    pending_path = REGISTRIES_MANIFESTS / "pending.json"
    try:
        existing = _read_pending_registries()
        merged = list(dict.fromkeys(existing + names))  # dedup, preserve order
        pending_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        _log(f"Pending registries queued for approval: {merged}")
    except Exception as exc:
        _log(f"Failed to write pending registries: {exc}")


def _remove_from_pending(registry: str) -> None:
    pending_path = REGISTRIES_MANIFESTS / "pending.json"
    try:
        if pending_path.exists():
            existing = _read_pending_registries()
            updated = [r for r in existing if r != registry]
            pending_path.write_text(json.dumps(updated, indent=2), encoding="utf-8")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _report(installed: list[dict], missing: list[str], delivered: list[str]) -> None:
    if not WOMBAT_URL:
        return
    try:
        _post("/api/wombat/report", {
            "customer_id":            CUSTOMER_ID,
            "license_key":            LICENSE_KEY,
            "reported_at":            _now_iso(),
            "installed_capabilities": installed,
            "missing_capabilities":   missing,
            "delivered_this_cycle":   delivered,
        })
    except Exception as exc:
        _log(f"Report: failed - {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _log("Mangy Marmot starting.")

    for d in (CAPABILITIES_DIR, DOWNLOADS_DIR, STAGING_DIR, STATUS_DIR, CORE_DIR, LOG_DIR,
               REGISTRIES_INCOMING, REGISTRIES_INSTALLED, REGISTRIES_MANIFESTS):
        d.mkdir(parents=True, exist_ok=True)

    _bootstrap_core()

    if not WOMBAT_URL:
        _log("WOMBAT_URL not set - standing by."); return
    if not CUSTOMER_ID:
        _log("AIRTRACK_CUSTOMER_ID not set - standing by."); return

    try:
        wh_manifest = _get("/api/wombat/manifest")
    except Exception as exc:
        _log(f"Warehouse manifest unavailable - {exc}"); return

    if wh_manifest.get("embargo_active"):
        _log("Embargo active - standing by."); return

    required        = wh_manifest.get("required_core_packages", [])
    installed       = _scan_installed()
    installed_names = {c["name"] for c in installed}
    missing         = [p for p in required if p not in installed_names]
    delivered       = []

    _log(f"Required: {required} | Installed: {sorted(installed_names) or 'none'} | Missing: {missing}")

    for pkg in missing:
        if _deliver(pkg):
            delivered.append(pkg)

    installed = _scan_installed()
    _report(installed, missing, delivered)

    # Registry delivery — merge warehouse required_registries (e.g. airports_ref, always
    # delivered to every customer) with customer-specific entitlements.
    wh_required_registries: list[str] = wh_manifest.get("required_registries", [])
    required_registries: list[str] = list(wh_required_registries)
    if CUSTOMER_ID:
        try:
            cust_manifest = _get(f"/api/wombat/manifest/{CUSTOMER_ID}")
            for cap in cust_manifest.get("deliveries", []):
                slug = cap.get("capability", "")
                if slug and slug not in required_registries:
                    required_registries.append(slug)
        except Exception as exc:
            _log(f"Registry manifest unavailable - {exc}")
    # Fetch available versions + update window from Wombat
    try:
        _avail_resp = _get("/api/wombat/available-registries")
        available_registry_versions = {r["slug"]: r["version"] for r in _avail_resp.get("registries", [])}
        update_window_hours = int(_avail_resp.get("update_window_hours", 24))
    except Exception as _avail_exc:
        _log(f"Registries: could not fetch available versions - {_avail_exc}")
        available_registry_versions = {}
        update_window_hours = 24

    installed_registries     = _scan_installed_registries()
    installed_registry_map   = {r["name"]: r["version"] for r in installed_registries}
    installed_registry_names = set(installed_registry_map.keys())
    outdated_registries      = [
        r for r in required_registries
        if r in installed_registry_names
        and r in available_registry_versions
        and installed_registry_map.get(r, "unknown") != "unknown"
        and installed_registry_map.get(r) != available_registry_versions[r]
    ]
    missing_registries       = [r for r in required_registries if r not in installed_registry_names]
    needs_delivery           = missing_registries + outdated_registries
    delivered_registries     = []

    if required_registries:
        _log(f"Registries - Required: {required_registries} | Installed: {sorted(installed_registry_names) or 'none'} | Missing: {missing_registries} | Outdated: {outdated_registries}")
        registry_pref = _get_registry_pref()
        if registry_pref == "never":
            _log("Registries: registry_updates=never — skipping all delivery")
        elif registry_pref == "ask":
            if needs_delivery:
                _write_pending_registries(needs_delivery)
                _log(f"Registries: registry_updates=ask — {len(needs_delivery)} queued for user approval")
        else:  # automatic
            from datetime import datetime as _dt, timezone as _tz
            _now = _dt.now(_tz.utc)
            for reg in needs_delivery:
                if reg in outdated_registries:
                    # Version update — apply jitter to spread load
                    target_ver = available_registry_versions.get(reg, "")
                    scheduled  = _get_scheduled_update(reg, target_ver)
                    if scheduled is None:
                        # First time we've seen this update — schedule it
                        _schedule_registry_update(reg, target_ver, update_window_hours)
                        continue
                    if _now < (scheduled.replace(tzinfo=_tz.utc) if scheduled.tzinfo is None else scheduled):
                        _log(f"Registry update {reg} → {target_ver}: scheduled for {scheduled.isoformat()}, waiting")
                        continue
                    # Scheduled time has passed — deliver
                    _log(f"Registry update {reg} → {target_ver}: scheduled time reached, delivering")
                if _deliver_registry(reg):
                    delivered_registries.append(reg)
                    _remove_from_pending(reg)
                    _clear_scheduled_update(reg)

    # Country auto-request: if app_settings.country maps to a registry not yet
    # installed or already in required_registries, self-request it from Wombat.
    # Keep COUNTRY_REGISTRY_MAP in sync with ATC installer.py.
    COUNTRY_REGISTRY_MAP = {"AU": "australia"}
    try:
        import pymysql as _pym2
        from urllib.parse import urlparse as _up2
        _db_uri = os.environ.get("DATABASE_URI", "")
        if _db_uri:
            _parsed2 = _up2(_db_uri.replace("mysql+pymysql://", "mysql://"))
            _host2 = _parsed2.hostname or "127.0.0.1"
            _port2 = _parsed2.port or 3306
            _user2 = _parsed2.username or "airtrack"
            _pass2 = _parsed2.password or ""
            _db2   = (_parsed2.path or "/airtrack").lstrip("/")
        else:
            _hp2 = os.environ.get("DB_HOST", "127.0.0.1:3306").split(":")
            _host2 = _hp2[0]; _port2 = int(_hp2[1]) if len(_hp2) > 1 else 3306
            _user2 = os.environ.get("DB_USER", "airtrack")
            _pass2 = os.environ.get("DB_PASSWORD", "")
            _db2   = os.environ.get("DB_NAME", "airtrack")
        _conn2 = _pym2.connect(host=_host2, port=int(_port2), user=_user2,
                               password=_pass2, database=_db2,
                               charset="utf8mb4", connect_timeout=5)
        try:
            with _conn2.cursor() as _cur2:
                _cur2.execute("SELECT SettingValue FROM app_settings WHERE SettingKey='country' LIMIT 1")
                _row2 = _cur2.fetchone()
                _country = (_row2[0] if _row2 else "").strip().upper()
        finally:
            _conn2.close()
        if _country and _country in COUNTRY_REGISTRY_MAP:
            _mapped = COUNTRY_REGISTRY_MAP[_country]
            _mapped_installed_version = installed_registry_map.get(_mapped)
            _mapped_avail_version     = available_registry_versions.get(_mapped)
            _mapped_outdated          = (
                _mapped in installed_registry_names
                and _mapped_installed_version and _mapped_installed_version != "unknown"
                and _mapped_avail_version
                and _mapped_installed_version != _mapped_avail_version
            )
            if (_mapped not in installed_registry_names and _mapped not in required_registries) or _mapped_outdated:
                registry_pref = _get_registry_pref()
                if registry_pref == "never":
                    _log(f"Country {_country} maps to registry '{_mapped}' — skipped (registry_updates=never)")
                elif registry_pref == "ask":
                    _write_pending_registries([_mapped])
                    _log(f"Country {_country} maps to registry '{_mapped}' — queued for user approval")
                else:
                    _log(f"Country {_country} maps to registry '{_mapped}' — auto-requesting")
                    if _deliver_registry(_mapped):
                        delivered_registries.append(_mapped)
                        _remove_from_pending(_mapped)
    except Exception as _exc:
        _log(f"Country registry auto-request failed: {_exc}")

    _log(f"Finished. Delivered: {(delivered + delivered_registries) or 'none'}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()
