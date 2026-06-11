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
from urllib.error import URLError
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
REGISTRIES_INSTALLED = AIRTRACK_HOME / "registries" / "installed"
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

    # Extract INSERT statements only - safer than executing the full dump
    inserts = re.findall(r"INSERT INTO.*?;", sql_content, re.DOTALL)
    if not inserts:
        raise RuntimeError(f"No INSERT statements found in {sql_file}")

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
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"DELETE FROM `{table_name}`")
                for stmt in inserts:
                    cursor.execute(stmt)
            conn.commit()
            _log(f"Registry '{registry_name}': imported {len(inserts)} INSERT block(s) into `{table_name}`")
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

    # Registry delivery
    required_registries      = wh_manifest.get("required_registries", [])
    installed_registries     = _scan_installed_registries()
    installed_registry_names = {r["name"] for r in installed_registries}
    missing_registries       = [r for r in required_registries if r not in installed_registry_names]
    delivered_registries     = []

    if required_registries:
        _log(f"Registries - Required: {required_registries} | Installed: {sorted(installed_registry_names) or 'none'} | Missing: {missing_registries}")
        for reg in missing_registries:
            if _deliver_registry(reg):
                delivered_registries.append(reg)

    _log(f"Finished. Delivered: {(delivered + delivered_registries) or 'none'}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()
