@echo off
:: Gate 2 build — run from anywhere; script anchors to its own directory.
cd /d "%~dp0"

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building PyInstaller bundle...
pyinstaller ^
  --onedir ^
  --name AirTrack ^
  --distpath dist ^
  --workpath build ^
  --specpath . ^
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

echo.
if exist dist\AirTrack\AirTrack.exe (
    echo BUILD SUCCEEDED
    echo Copy dist\AirTrack\ to the test machine.
) else (
    echo BUILD FAILED — check output above
)
