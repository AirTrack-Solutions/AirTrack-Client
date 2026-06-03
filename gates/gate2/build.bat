@echo off
REM Gate 2 build script — run on the BUILD machine (Python installed)
REM Output: dist\AirTrack\ — copy this folder to the clean test VM

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building PyInstaller bundle...
pyinstaller ^
  --onedir ^
  --name AirTrack ^
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
    echo.
    echo Copy dist\AirTrack\ to the clean test VM.
    echo Then on the test VM, open an admin command prompt and run:
    echo   AirTrack.exe install
    echo   AirTrack.exe start
    echo Then open a browser to http://localhost:5000
) else (
    echo BUILD FAILED — check output above
)
