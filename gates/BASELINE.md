# Windows Native Gates — Known-Good Baseline

**Tag:** `windows-gates-pass-marianne-001`  
**Branch:** `windows-native-gates`  
**Date:** 2026-06-04  
**Tested on:** Marianne's PC (192.168.0.130, Windows 10/11)

---

## What passed

| Gate | What it proved | Result |
|------|---------------|--------|
| Gate 1 | MariaDB 11.4 silent install, port 3307, service AirTrackDB | PASS |
| Gate 2 | PyInstaller --onedir + pywin32 service + Flask + Waitress | PASS |
| Gate 3 | Full stack: Gate 2 + MariaDB connection, schema, airtrack user | PASS |

Browser confirmed: `AirTrack OK — DB connected`

---

## Critical constraints (do not change without a gate retest)

### pywin32 must be pinned to 311
pywin32 306 has a Python 3.12 thread state bug. Windows SCM creates the service
thread without properly initializing the Python tstate. ANY heap allocation
(list, dict, string) crashes at python312.dll+0x73def with 0xc0000005.
pywin32 311 fixes it. Do not downgrade.

### Do NOT use --collect-binaries pywin32
This flag causes DLL conflicts in the PyInstaller bundle. The pywin32 DLLs
(pythoncom312.dll, pywintypes312.dll) are correctly pulled in by
--hidden-import pythoncom alone. Adding --collect-binaries creates
duplicate/conflicting copies and crashes.

### Flask must receive root_path explicitly
Flask(__name__) calls pkgutil.get_loader() in a frozen service context and
hangs (service 1053 timeout). Fix:

    root = os.path.dirname(sys.executable)  # when frozen
    app = Flask(__name__, root_path=root)

### Module-level servicemanager.LogInfoMsg calls are silently dropped
Any servicemanager.LogInfoMsg() at module level (before Initialize() is called)
is silently ignored. Only calls from within SvcDoRun() will appear in Event Viewer.

---

## Known-good build configuration

requirements.txt:
    flask==3.0.3
    waitress==3.0.0
    pywin32==311
    pyinstaller==6.3.0

PyInstaller flags (build.bat):
    --onedir
    --hidden-import encodings
    --collect-all encodings
    --hidden-import win32timezone
    --hidden-import win32service
    --hidden-import win32serviceutil
    --hidden-import win32event
    --hidden-import servicemanager
    --hidden-import pywintypes
    --hidden-import pythoncom
    --hidden-import waitress
    --hidden-import flask
    --hidden-import werkzeug

---

## Known-good MariaDB setup on Marianne's machine

- Install path: C:\Program Files\MariaDB 11.4\
- Data dir: C:\AirTrackData\
- my.ini: C:\AirTrackData\my.ini (port=3307)
- Service name: AirTrackDB (Automatic Delayed start)
- Root password: Gate1RootPass!
- App user: airtrack@localhost, password Gate1UserPass!
- Database: airtrack (utf8mb4)
- Schema: gates/gate3/schema.sql (998 lines, loaded 2026-06-04)

NOTE: MariaDB MSI may skip service registration if binaries already exist.
If AirTrackDB service is missing after installer runs, manually register:
    mysqld.exe --install AirTrackDB --defaults-file=C:\AirTrackData\my.ini

---

## airtrack.cfg (gate3 baseline)

[database]
uri=mysql+pymysql://airtrack:Gate1UserPass!@127.0.0.1:3307/airtrack?charset=utf8mb4
host=127.0.0.1
port=3307
name=airtrack
user=airtrack
password=Gate1UserPass!
[app]
secret_key=change-me-before-production
role=client

---

## Next phase: wire real AirTrack Client into Gate 3

Order of layers (one at a time, prove it, commit it):

1. Gate 3 skeleton  <-- current tag
2. Real Client config loading
3. Real Client static/templates
4. Real Client routes
5. Real Client DB models
6. Real Client feed/data paths
7. Installer / start menu / service polish

Architecture is frozen. No redesigns. No new subsystems without explicit decision.
