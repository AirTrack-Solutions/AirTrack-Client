"""
AirTrack Capability Package Installer
package_installer.py v0.9

AirTrack Core component.
Capabilities do not install themselves.

v0.9 additions:
    - After successful healthcheck, write capability heartbeat to
      $AIRTRACK_HOME/status/capabilities/<name>.json
    - Heartbeat fields: capability, version, status, last_successful_run, source
    - Heartbeat is only written on full success (validation + install + healthcheck)

v0.8 additions:
    - After install, execute the installed healthcheck.py from the capability directory
    - Healthcheck runs as a subprocess with a 10-second timeout
    - Healthcheck: Passed on exit 0; Healthcheck: Failed on non-zero exit or exception
    - Failed healthcheck does not mark the install as healthy; installer exits 1
    - Install is not rolled back on healthcheck failure (recovery deferred to v0.9+)

v0.7 additions:
    - Install staged package into $AIRTRACK_HOME/capabilities/<name>/
    - Back up existing capability directory before replacement
    - Backup path: $AIRTRACK_HOME/backups/capabilities/<name>/<timestamp>/
    - If no existing capability directory, record Backup: Not required
    - Staging is always cleaned (wiped + recreated) before extraction
    - Install reads from staging, not directly from ZIP
    - Does not register scheduler tasks or run healthcheck

v0.6 retained:
    - After all validation gates pass, extract payload files to staging directory
    - Staging path: $AIRTRACK_HOME/staging/<name>-<version>/
    - Existing staging directory for the same package/version is wiped and recreated
    - Extracts: manifest.json, entrypoint, healthcheck, scheduler, checksums.sha256, signature.sig

v0.5 retained:
    - Stage 0: Verify Ed25519 signature (signature.sig) against checksums.sha256
    - Public key loaded from $AIRTRACK_HOME/core/airtrack_solutions.pub
    - signature.sig must be present; package is rejected if missing or invalid
    - Requires: cryptography library (pip install cryptography)
    - Signature verification runs before checksum verification; both must pass

v0.4 retained:
    - Read and verify checksums.sha256
    - checksums.sha256 must be present
    - All listed files must exist in ZIP and match their SHA-256
    - All ZIP files (except checksums.sha256 and signature.sig) must be listed
    - Fail cleanly on missing file, missing checksum entry, or hash mismatch

v0.3 retained:
    - Parse compatible_airtrack_versions and compare against AIRTRACK_VERSION

v0.2 retained:
    - Validate files referenced in manifest exist inside the ZIP

v0.1 retained:
    - Open package, read manifest.json, validate required fields, report result

Still cannot:
    - Register scheduler tasks
    - Monitor heartbeat
    - Rollback on failed healthcheck
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.exceptions import InvalidSignature
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

# ---------------------------------------------------------------------------
# AirTrack environment
# All paths are derived from AIRTRACK_HOME.
# Never hardcode /home/trevor or /home/airtrack — this runs on multiple hosts.
#
# Required env vars:
#   AIRTRACK_HOME       Root AirTrack directory (e.g. /home/airtrack/AirTrack)
#   AIRTRACK_VERSION    Running AirTrack version (e.g. 1.0.0)
#                       Temporary until Core version service exists.
# ---------------------------------------------------------------------------

def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Error: {name} environment variable is not set.")
        sys.exit(1)
    return value


AIRTRACK_HOME    = Path(_require_env("AIRTRACK_HOME"))
AIRTRACK_VERSION = os.environ.get("AIRTRACK_VERSION", "1.0.0")

CAPABILITIES_DIR = AIRTRACK_HOME / "capabilities"
CONFIG_DIR       = AIRTRACK_HOME / "config"
RECOVERY_DIR     = AIRTRACK_HOME / "recovery"
DIAGNOSTICS_DIR  = AIRTRACK_HOME / "diagnostics"
STAGING_DIR      = AIRTRACK_HOME / "staging"
BACKUPS_DIR      = AIRTRACK_HOME / "backups" / "capabilities"
STATUS_DIR       = AIRTRACK_HOME / "status" / "capabilities"
PUBLIC_KEY_PATH  = AIRTRACK_HOME / "core" / "airtrack_solutions.pub"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_MANIFEST_FIELDS = [
    "type",
    "name",
    "version",
    "entrypoint",
    "healthcheck",
    "scheduler",
    "compatible_airtrack_versions",
]

REQUIRED_FILE_FIELDS = [
    "entrypoint",
    "healthcheck",
    "scheduler",
]

CHECKSUMS_FILENAME  = "checksums.sha256"
SIGNATURE_FILENAME  = "signature.sig"

# Files that are exempt from checksum coverage.
# checksums.sha256 cannot list itself (chicken-and-egg).
# signature.sig covers checksums.sha256, so it is exempt from checksum coverage.
CHECKSUM_EXEMPT = {CHECKSUMS_FILENAME, SIGNATURE_FILENAME}


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    valid: bool
    package_name: Optional[str] = None
    package_version: Optional[str] = None
    compatible: Optional[bool] = None
    missing_manifest_fields: List[str] = field(default_factory=list)
    missing_package_files: List[str] = field(default_factory=list)
    checksum_errors: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    staging_path: Optional[str] = None
    staged_files: List[str] = field(default_factory=list)
    backup_required: Optional[bool] = None
    backup_path: Optional[str] = None
    install_path: Optional[str] = None
    healthcheck_passed: Optional[bool] = None
    healthcheck_error: Optional[str] = None
    heartbeat_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Semver parsing
# ---------------------------------------------------------------------------

VERSION_RE    = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
CONSTRAINT_RE = re.compile(r"^\s*(>=|<=|>|<|==)\s*(\d+\.\d+\.\d+)\s*$")

OPERATORS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">":  lambda a, b: a > b,
    "<":  lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


def parse_version(version_str: str) -> Tuple[int, int, int]:
    m = VERSION_RE.match(version_str.strip())
    if not m:
        raise ValueError(f"Invalid version format: '{version_str}' (expected major.minor.patch)")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def check_compatibility(constraint_str: str, airtrack_version: str) -> Tuple[bool, Optional[str]]:
    try:
        running = parse_version(airtrack_version)
    except ValueError as exc:
        return False, f"AIRTRACK_VERSION is invalid: {exc}"

    constraints = constraint_str.split(",")
    for raw in constraints:
        m = CONSTRAINT_RE.match(raw)
        if not m:
            return False, f"Unrecognised version constraint: '{raw.strip()}'"
        operator = m.group(1)
        try:
            required = parse_version(m.group(2))
        except ValueError as exc:
            return False, str(exc)
        if not OPERATORS[operator](running, required):
            return False, None

    return True, None


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def load_public_key() -> "Ed25519PublicKey":
    if not PUBLIC_KEY_PATH.exists():
        raise FileNotFoundError(f"Public key not found: {PUBLIC_KEY_PATH}")
    pem = PUBLIC_KEY_PATH.read_bytes()
    return load_pem_public_key(pem)


def verify_signature(zf: zipfile.ZipFile) -> Optional[str]:
    """
    Verify signature.sig against checksums.sha256.
    Returns an error string on failure, or None on success.
    """
    if not _CRYPTO_AVAILABLE:
        return "cryptography library is not installed; signature verification unavailable"

    zip_names = zf.namelist()

    if SIGNATURE_FILENAME not in zip_names:
        return f"{SIGNATURE_FILENAME} is missing from package"

    if CHECKSUMS_FILENAME not in zip_names:
        return f"{CHECKSUMS_FILENAME} is missing from package (required for signature verification)"

    try:
        public_key = load_public_key()
    except FileNotFoundError as exc:
        return str(exc)
    except Exception as exc:
        return f"Failed to load public key: {exc}"

    signature = zf.read(SIGNATURE_FILENAME)
    checksums_data = zf.read(CHECKSUMS_FILENAME)

    try:
        public_key.verify(signature, checksums_data)
    except InvalidSignature:
        return "Signature verification failed"
    except Exception as exc:
        return f"Signature verification error: {exc}"

    return None  # success


# ---------------------------------------------------------------------------
# Checksum verification
# ---------------------------------------------------------------------------

def parse_checksums(raw: bytes) -> Dict[str, str]:
    """
    Parse checksums.sha256 content.
    Format: '<sha256>  <filename>' per line (two spaces, matching sha256sum output).
    Returns {filename: expected_hex_digest}.
    """
    entries: Dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)   # split on any whitespace, max 2 parts
        if len(parts) != 2:
            raise ValueError(f"Malformed checksums line: '{line}'")
        digest, filename = parts[0], parts[1].strip()
        if len(digest) != 64 or not all(c in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError(f"Invalid SHA-256 digest for '{filename}': '{digest}'")
        entries[filename] = digest.lower()
    return entries


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_checksums(zf: zipfile.ZipFile) -> List[str]:
    """
    Verify checksums.sha256 against ZIP contents.
    Returns a list of error strings (empty = all good).
    """
    errors: List[str] = []
    zip_names = set(zf.namelist())

    if CHECKSUMS_FILENAME not in zip_names:
        return [f"{CHECKSUMS_FILENAME} is missing from package"]

    try:
        raw = zf.read(CHECKSUMS_FILENAME)
        expected = parse_checksums(raw)
    except ValueError as exc:
        return [f"{CHECKSUMS_FILENAME} is malformed: {exc}"]

    for filename, expected_digest in expected.items():
        if filename not in zip_names:
            errors.append(f"Checksum listed for missing file: {filename}")
            continue
        actual_digest = sha256_of(zf.read(filename))
        if actual_digest != expected_digest:
            errors.append(f"Checksum mismatch: {filename}")

    for filename in zip_names:
        if filename in CHECKSUM_EXEMPT:
            continue
        if filename not in expected:
            errors.append(f"Unlisted file in package: {filename}")

    return errors


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------

def stage_package(zf: zipfile.ZipFile, manifest: dict) -> tuple:
    """
    Extract payload files into a clean staging directory.
    Returns (staging_path, staged_files) on success.
    Raises on any I/O failure.

    Staging path: $AIRTRACK_HOME/staging/<name>-<version>/
    Only files present in the ZIP are extracted; missing optional files are skipped.
    """
    name    = manifest["name"]
    version = manifest["version"]
    dest    = STAGING_DIR / f"{name}-{version}"

    # Wipe and recreate staging directory for this package/version
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    # Determine which files to extract:
    # always: manifest.json, checksums.sha256, signature.sig
    # from manifest: entrypoint, healthcheck, scheduler
    payload_files = {"manifest.json", CHECKSUMS_FILENAME, SIGNATURE_FILENAME}
    for field_name in REQUIRED_FILE_FIELDS:
        filename = manifest.get(field_name)
        if filename:
            payload_files.add(filename)

    zip_names = set(zf.namelist())
    staged: list = []
    for filename in sorted(payload_files):
        if filename not in zip_names:
            continue  # optional file absent — skip
        data = zf.read(filename)
        (dest / filename).write_bytes(data)
        staged.append(filename)

    return str(dest), staged



# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

def install_package(staging_dir: Path, manifest: dict) -> tuple:
    """
    Install a staged package into its final capability directory.

    Steps:
      1. Determine capability path: $AIRTRACK_HOME/capabilities/<name>/
      2. If it exists, back it up to $AIRTRACK_HOME/backups/capabilities/<name>/<timestamp>/
      3. Remove the existing capability directory.
      4. Copy staging directory into capability path.

    Returns (backup_required, backup_path_or_none, install_path).
    Raises on any I/O failure.

    Does not:
      - Register scheduler tasks
      - Run healthcheck
      - Remove backups
      - Touch diagnostics or other directories
    """
    import datetime

    name         = manifest["name"].lower()
    cap_dir      = CAPABILITIES_DIR / name
    backup_path  = None
    backup_req   = cap_dir.exists()

    if backup_req:
        timestamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dest = BACKUPS_DIR / name / timestamp
        backup_dest.parent.mkdir(parents=True, exist_ok=True)
        # Handle collision (two installs in the same second)
        counter = 0
        while backup_dest.exists():
            counter += 1
            backup_dest = BACKUPS_DIR / name / f"{timestamp}_{counter}"
        shutil.copytree(cap_dir, backup_dest)
        backup_path = str(backup_dest)
        # Write backup metadata so callers can annotate (e.g. with request_id)
        import json as _json
        _meta = {
            "capability":  name,
            "version":     manifest.get("version", "unknown"),
            "backed_up_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        }
        (backup_dest / "_backup_meta.json").write_text(_json.dumps(_meta, indent=2))
        shutil.rmtree(cap_dir)

    shutil.copytree(staging_dir, cap_dir)
    return backup_req, backup_path, str(cap_dir)


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------

HEALTHCHECK_TIMEOUT = 10  # seconds

def run_healthcheck(install_dir: Path, manifest: dict) -> tuple:
    """
    Execute the installed healthcheck from its capability directory.

    Runs: python3 <healthcheck_file>
    Working directory: install_dir
    Timeout: HEALTHCHECK_TIMEOUT seconds

    Returns (passed: bool, error: Optional[str]).
    """
    healthcheck_file = manifest.get("healthcheck")
    if not healthcheck_file:
        return False, "No healthcheck defined in manifest"

    healthcheck_path = install_dir / healthcheck_file
    if not healthcheck_path.exists():
        return False, f"Healthcheck file not found: {healthcheck_path}"

    try:
        result = subprocess.run(
            [sys.executable, str(healthcheck_path)],
            cwd=str(install_dir),
            timeout=HEALTHCHECK_TIMEOUT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True, None
        stderr = result.stderr.strip() or result.stdout.strip()
        return False, f"Healthcheck exited {result.returncode}" + (f": {stderr}" if stderr else "")
    except subprocess.TimeoutExpired:
        return False, f"Healthcheck timed out after {HEALTHCHECK_TIMEOUT}s"
    except Exception as exc:
        return False, f"Healthcheck raised exception: {exc}"


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

def write_heartbeat(manifest: dict) -> str:
    """
    Write a capability status/heartbeat file to STATUS_DIR/<name>.json.
    Only called after validation, install, and healthcheck all pass.
    Returns the path written.
    """
    name    = manifest["name"].lower()
    version = manifest.get("version", "unknown")
    dest    = STATUS_DIR / f"{name}.json"

    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "capability":          name,
        "version":             version,
        "status":              "healthy",
        "last_successful_run": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source":              "package_installer",
    }

    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(dest)
    return str(dest)


# ---------------------------------------------------------------------------
# Package validation
# ---------------------------------------------------------------------------

def open_package(package_path: Path) -> zipfile.ZipFile:
    if not package_path.exists():
        raise FileNotFoundError(f"Package not found: {package_path}")
    if not zipfile.is_zipfile(package_path):
        raise ValueError(f"Not a valid ZIP archive: {package_path}")
    return zipfile.ZipFile(package_path, "r")


def read_manifest(zf: zipfile.ZipFile) -> dict:
    if "manifest.json" not in zf.namelist():
        raise ValueError("manifest.json not found in package")
    with zf.open("manifest.json") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifest.json is not valid JSON: {exc}") from exc


def validate_manifest_fields(manifest: dict) -> List[str]:
    return [f for f in REQUIRED_MANIFEST_FIELDS if f not in manifest]


def validate_package_files(manifest: dict, zip_names: List[str]) -> List[str]:
    missing = []
    for field_name in REQUIRED_FILE_FIELDS:
        filename = manifest.get(field_name)
        if filename and filename not in zip_names:
            missing.append(filename)
    return missing


def validate_package(package_path: Path) -> ValidationResult:
    try:
        zf = open_package(package_path)
    except (FileNotFoundError, ValueError) as exc:
        return ValidationResult(valid=False, errors=[str(exc)])

    try:
        manifest = read_manifest(zf)
        zip_names = zf.namelist()
    except ValueError as exc:
        zf.close()
        return ValidationResult(valid=False, errors=[str(exc)])

    # Stage 1: manifest fields present
    missing_fields = validate_manifest_fields(manifest)
    if missing_fields:
        zf.close()
        return ValidationResult(valid=False, missing_manifest_fields=missing_fields)

    # Stage 2: referenced files exist in ZIP
    missing_files = validate_package_files(manifest, zip_names)
    if missing_files:
        zf.close()
        return ValidationResult(
            valid=False,
            package_name=manifest.get("name"),
            package_version=manifest.get("version"),
            missing_package_files=missing_files,
        )

    # Stage 3: version compatibility
    constraint_str = manifest.get("compatible_airtrack_versions", "")
    compatible, parse_error = check_compatibility(constraint_str, AIRTRACK_VERSION)
    if parse_error:
        zf.close()
        return ValidationResult(
            valid=False,
            package_name=manifest.get("name"),
            package_version=manifest.get("version"),
            errors=[parse_error],
        )
    if not compatible:
        zf.close()
        return ValidationResult(
            valid=False,
            package_name=manifest.get("name"),
            package_version=manifest.get("version"),
            compatible=False,
            errors=[f"Package is not compatible with AirTrack {AIRTRACK_VERSION}"],
        )

    # Stage 0 (runs here — signature covers checksums, must verify before checksums):
    sig_error = verify_signature(zf)
    if sig_error:
        zf.close()
        return ValidationResult(
            valid=False,
            package_name=manifest.get("name"),
            package_version=manifest.get("version"),
            compatible=True,
            errors=[sig_error],
        )

    # Stage 4: checksum verification
    checksum_errors = validate_checksums(zf)

    if checksum_errors:
        zf.close()
        return ValidationResult(
            valid=False,
            package_name=manifest.get("name"),
            package_version=manifest.get("version"),
            compatible=True,
            checksum_errors=checksum_errors,
        )

    # Stage 5: extract to staging (zf must still be open)
    try:
        staging_path, staged_files = stage_package(zf, manifest)
    except Exception as exc:
        return ValidationResult(
            valid=False,
            package_name=manifest.get("name"),
            package_version=manifest.get("version"),
            compatible=True,
            errors=[f"Staging failed: {exc}"],
        )
    finally:
        zf.close()

    # Stage 6: install from staging to capabilities/
    staging_dir = Path(staging_path)
    try:
        backup_req, backup_path, install_path = install_package(staging_dir, manifest)
    except Exception as exc:
        return ValidationResult(
            valid=False,
            package_name=manifest.get("name"),
            package_version=manifest.get("version"),
            compatible=True,
            staging_path=staging_path,
            errors=[f"Install failed: {exc}"],
        )

    # Stage 7: run healthcheck from installed capability directory
    install_dir = Path(install_path)
    hc_passed, hc_error = run_healthcheck(install_dir, manifest)

    if not hc_passed:
        return ValidationResult(
            valid=False,
            package_name=manifest.get("name"),
            package_version=manifest.get("version"),
            compatible=True,
            staging_path=staging_path,
            staged_files=staged_files,
            backup_required=backup_req,
            backup_path=backup_path,
            install_path=install_path,
            healthcheck_passed=False,
            healthcheck_error=hc_error,
        )

    # Stage 8: write heartbeat
    try:
        heartbeat_path = write_heartbeat(manifest)
    except Exception as exc:
        return ValidationResult(
            valid=False,
            package_name=manifest.get("name"),
            package_version=manifest.get("version"),
            compatible=True,
            staging_path=staging_path,
            staged_files=staged_files,
            backup_required=backup_req,
            backup_path=backup_path,
            install_path=install_path,
            healthcheck_passed=True,
            errors=[f"Heartbeat write failed: {exc}"],
        )

    return ValidationResult(
        valid=True,
        package_name=manifest.get("name"),
        package_version=manifest.get("version"),
        compatible=True,
        staging_path=staging_path,
        staged_files=staged_files,
        backup_required=backup_req,
        backup_path=backup_path,
        install_path=install_path,
        healthcheck_passed=True,
        heartbeat_path=heartbeat_path,
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_result(result: ValidationResult) -> None:
    if not result.valid:
        # If install completed but healthcheck failed, show install context first
        if result.install_path:
            print(f"Install:    Complete")
            print(f"Installed:  {result.install_path}")
        else:
            print("Package Invalid")
        for err in result.errors:
            print(f"Error:          {err}")
        for f in result.missing_manifest_fields:
            print(f"Missing field:  {f}")
        for f in result.missing_package_files:
            print(f"Missing file:   {f}")
        for err in result.checksum_errors:
            print(f"Error:          {err}")
        if result.healthcheck_passed is False:
            print(f"Healthcheck: Failed")
            if result.healthcheck_error:
                print(f"Error:       {result.healthcheck_error}")
        return

    print(f"Package:    {result.package_name}")
    print(f"Version:    {result.package_version}")
    print(f"Compatible: Yes")
    print(f"Manifest:   Valid")
    print(f"Files:      Valid")
    print(f"Checksums:  Valid")
    print(f"Signature:  Valid")
    print(f"Staging:    Complete")
    if result.backup_required:
        print(f"Backup:     Complete")
        print(f"Backed up:  {result.backup_path}")
    else:
        print(f"Backup:     Not required")
    print(f"Install:    Complete")
    print(f"Installed:  {result.install_path}")
    if result.healthcheck_passed:
        print(f"Healthcheck: Passed")
    else:
        print(f"Healthcheck: Failed")
        if result.healthcheck_error:
            print(f"Error:       {result.healthcheck_error}")
    if result.heartbeat_path:
        print(f"Heartbeat:   Written")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: package_installer.py <package.zip>")
        return 1

    package_path = Path(sys.argv[1])
    result = validate_package(package_path)
    print_result(result)
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
