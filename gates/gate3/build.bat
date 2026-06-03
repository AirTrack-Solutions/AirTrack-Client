@echo off
:: AirTrack Windows — PyInstaller build
:: Run from anywhere — all paths are relative to this script's location.
:: Output: gates\gate3\dist\AirTrack\

set GATE3=%~dp0
set REPO=%~dp0..\..\

pip install -r "%GATE3%requirements.txt"

pyinstaller ^
  --onedir ^
  --name AirTrack ^
  --paths "%REPO%app" ^
  --add-data "%REPO%app\templates;app\templates" ^
  --add-data "%REPO%app\static;app\static" ^
  --add-data "%REPO%app\migrations;app\migrations" ^
  --add-data "%REPO%app\scripts\airports.csv;app\scripts" ^
  --add-data "%REPO%app\core\airtrack_solutions.pub;app\core" ^
  --hidden-import win32timezone ^
  --hidden-import win32service ^
  --hidden-import win32serviceutil ^
  --hidden-import win32event ^
  --hidden-import servicemanager ^
  --hidden-import pywintypes ^
  --hidden-import waitress ^
  --hidden-import pymysql ^
  --hidden-import flask ^
  --hidden-import werkzeug ^
  --hidden-import sqlalchemy ^
  --hidden-import flask_sqlalchemy ^
  --hidden-import flask_wtf ^
  --hidden-import pytz ^
  --hidden-import cryptography ^
  --hidden-import webauthn ^
  --hidden-import apscheduler ^
  --hidden-import stripe ^
  --hidden-import paramiko ^
  --distpath "%GATE3%dist" ^
  --workpath "%GATE3%build" ^
  --specpath "%GATE3%" ^
  "%GATE3%service.py"

echo.
echo Build complete. Bundle: %GATE3%dist\AirTrack\
