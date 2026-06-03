@echo off
:: Gate 2 build — build 008
:: Explicitly removes markupsafe._speedups.pyd after bundling so MarkupSafe
:: falls back to its pure-Python _native implementation.
cd /d "%~dp0"

echo [1/5] Cleaning stale build artifacts...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist AirTrack.spec del /q AirTrack.spec

echo [2/5] Installing dependencies...
pip install -r requirements.txt

echo [3/5] Building PyInstaller bundle...
python -m PyInstaller ^
  --onedir ^
  --name AirTrack ^
  --distpath dist ^
  --workpath build ^
  --specpath . ^
  --hidden-import encodings ^
  --collect-all encodings ^
  --hidden-import win32timezone ^
  --hidden-import win32service ^
  --hidden-import win32serviceutil ^
  --hidden-import win32event ^
  --hidden-import servicemanager ^
  --hidden-import pywintypes ^
  --hidden-import pythoncom ^
  --collect-binaries pywin32 ^
  --hidden-import waitress ^
  --hidden-import flask ^
  --hidden-import werkzeug ^
  service.py

echo [4/5] Removing markupsafe C extension (force pure-Python fallback)...
del /q "dist\AirTrack\_internal\markupsafe\_speedups.cp312-win_amd64.pyd" 2>nul
echo     Done (file absent is also OK).

echo [5/5] Checking output...
if exist dist\AirTrack\AirTrack.exe (
    echo BUILD SUCCEEDED
    echo Copy dist\AirTrack\ to the test machine.
) else (
    echo BUILD FAILED — check output above
)
