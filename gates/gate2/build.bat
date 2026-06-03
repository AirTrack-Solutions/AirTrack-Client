@echo off
:: Gate 2 build — anchored to its own directory.
:: Cleans stale artifacts before every build.
cd /d "%~dp0"

echo [1/4] Cleaning stale build artifacts...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist AirTrack.spec del /q AirTrack.spec

echo [2/4] Installing dependencies...
pip install -r requirements.txt

echo [3/4] Building PyInstaller bundle...
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
  --hidden-import waitress ^
  --hidden-import flask ^
  --hidden-import werkzeug ^
  service.py

echo [4/4] Checking output...
if exist dist\AirTrack\AirTrack.exe (
    echo BUILD SUCCEEDED
    echo Copy dist\AirTrack\ to the test machine.
) else (
    echo BUILD FAILED — check output above
)
