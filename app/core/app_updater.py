"""
AirTrack — App Updater
app/core/app_updater.py  v0.1

Applies app update packages (templates + static) without a full PyInstaller rebuild.
Called by Mangy Marmot after a verified update package is downloaded from Wombat.

Package structure (signed zip):
    manifest.json      — {type: "app_update", version: "...", description: "..."}
    templates/         — full app/templates/ tree
    static/            — full app/static/ tree
    checksums.sha256   — sha256 of manifest.json + each content file
    signature.sig      — Ed25519 signature over checksums.sha256

Install root:
    Frozen  (PyInstaller --onedir): C:\\AirTrack\\_internal\\
    Dev     (unfrozen):             repo root (three levels above this file)
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _get_install_root() -> Path:
    """
    Frozen:  C:\\AirTrack\\_internal\\  (files live at _internal/app/templates/ etc.)
    Dev:     repo root (this file is at app/core/app_updater.py)
    """
    if getattr(sys, "frozen", False):
        # sys.executable = C:\AirTrack\AirTrack.exe
        return Path(sys.executable).parent / "_internal"
    # app/core/app_updater.py -> app/core -> app -> repo_root
    return Path(__file__).resolve().parent.parent.parent


def _get_airtrack_home() -> Path:
    env = os.environ.get("AIRTRACK_HOME", "")
    if env:
        return Path(env)
    if sys.platform == "win32":
        return Path(os.environ.get("ProgramData", "C:/ProgramData")) / "AirTrack"
    return Path("/airtrack_data")


_VERSION_FILE = "app_update_version.txt"
_SERVICE_NAME = os.environ.get("AIRTRACK_SERVICE_NAME", "AirTrackClient")


# ---------------------------------------------------------------------------
# Version tracking
# ---------------------------------------------------------------------------

def get_applied_version(home: "Path | None" = None) -> str:
    """Return the version of the last applied app update, or '0.0.0' if none."""
    h  = home or _get_airtrack_home()
    vf = h / _VERSION_FILE
    try:
        v = vf.read_text(encoding="utf-8").strip()
        return v if v else "0.0.0"
    except Exception:
        return "0.0.0"


def _write_applied_version(version: str, home: Path) -> None:
    vf  = home / _VERSION_FILE
    tmp = vf.with_suffix(".tmp")
    tmp.write_text(version, encoding="utf-8")
    tmp.replace(vf)


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify(zip_bytes: bytes, expected_sha256: str, pub_key_path: Path) -> "str | None":
    """Return an error string on failure, or None on success."""
    import hashlib
    actual = hashlib.sha256(zip_bytes).hexdigest()
    if actual != expected_sha256:
        return (
            f"SHA-256 mismatch: expected {expected_sha256[:16]}..., "
            f"got {actual[:16]}..."
        )

    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        return "cryptography library not installed"

    if not pub_key_path.exists():
        return f"Public key not found: {pub_key_path}"

    try:
        pub = load_pem_public_key(pub_key_path.read_bytes())
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            checksums_data = zf.read("checksums.sha256")
            signature      = zf.read("signature.sig")
            pub.verify(signature, checksums_data)
    except InvalidSignature:
        return "Ed25519 signature verification failed"
    except Exception as exc:
        return f"Verification error: {exc}"

    return None


# ---------------------------------------------------------------------------
# Apply update
# ---------------------------------------------------------------------------

def apply_app_update(
    zip_bytes: bytes,
    version: str,
    expected_sha256: str,
    home: "Path | None" = None,
    log_fn=None,
) -> None:
    """
    Verify, extract, and install the update package.

    Templates and static files are written to:
        {install_root}/app/templates/
        {install_root}/app/static/

    Version is recorded in AIRTRACK_HOME/app_update_version.txt.
    On Windows the service is restarted via a detached PowerShell process.

    Raises RuntimeError on any failure -- caller should log and abort.
    """

    def _log(msg: str) -> None:
        if log_fn:
            log_fn(msg)

    h = home or _get_airtrack_home()

    # Locate public key (bootstrapped by Marmot on first run)
    pub_key = h / "core" / "airtrack_solutions.pub"

    # --- Verify ---
    err = _verify(zip_bytes, expected_sha256, pub_key)
    if err:
        raise RuntimeError(f"Package verification failed: {err}")
    _log("App update: signature + SHA-256 verified")

    # --- Read manifest from zip ---
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        try:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Cannot read manifest.json from package: {exc}")

        if manifest.get("type") != "app_update":
            raise RuntimeError(
                f"Package type is '{manifest.get('type')}', expected 'app_update'"
            )

        # Collect content entries (templates/ and static/ only)
        names = [
            n for n in zf.namelist()
            if n.startswith("templates/") or n.startswith("static/")
        ]
        if not names:
            raise RuntimeError("Package contains no templates/ or static/ entries")

        install_root = _get_install_root()
        app_root     = install_root / "app"
        _log(f"App update: installing {len(names)} files -> {app_root}")

        # Extract to temp dir, then move per-file (avoids partial-write corruption)
        with tempfile.TemporaryDirectory(prefix="airtrack_upd_") as tmp_str:
            tmp = Path(tmp_str)
            zf.extractall(tmp, members=names)

            src_templates = tmp / "templates"
            dst_templates = app_root / "templates"
            if src_templates.is_dir():
                dst_templates.mkdir(parents=True, exist_ok=True)
                _replace_tree(src_templates, dst_templates)

            src_static = tmp / "static"
            dst_static = app_root / "static"
            if src_static.is_dir():
                dst_static.mkdir(parents=True, exist_ok=True)
                _replace_tree(src_static, dst_static)

    # --- Record applied version ---
    _write_applied_version(version, h)
    _log(f"App update: applied version {version}")

    # --- Schedule service restart (Windows only) ---
    if sys.platform == "win32":
        _schedule_restart(_log)
    else:
        _log("App update: non-Windows host -- restart service manually to pick up changes")


def _replace_tree(src: Path, dst: Path) -> None:
    """Recursively copy src -> dst, overwriting files atomically."""
    for item in src.rglob("*"):
        if item.is_file():
            rel    = item.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write to .tmp then rename -- avoids half-written files
            tmp_target = target.with_suffix(target.suffix + ".tmp")
            shutil.copy2(item, tmp_target)
            tmp_target.replace(target)


def _schedule_restart(log_fn) -> None:
    """
    Launch a detached PowerShell that sleeps 5 s then restarts the service.
    The current Marmot run finishes normally; PS handles the restart.
    """
    DETACHED_PROCESS         = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    try:
        import subprocess
        cmd = f"Start-Sleep 5; Restart-Service {_SERVICE_NAME} -Force"
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", cmd],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        log_fn(f"App update: restart scheduled (service: {_SERVICE_NAME})")
    except Exception as exc:
        log_fn(f"App update: WARNING -- could not schedule restart: {exc}")
