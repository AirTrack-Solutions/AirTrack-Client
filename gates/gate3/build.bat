@echo off
:: AirTrack Windows — PyInstaller build
:: Run from gates\gate3\ on Trevor's Windows laptop.
:: Output: gates\gate3\dist\AirTrack\

:: Move to repo root so 'app' package is resolvable
cd /d "%~dp0..\.."

pip install -r gates\gate3\requirements.txt

pyinstaller ^
  --onedir ^
  --name AirTrack ^
  --paths app ^
  --add-data "app\templates;app\templates" ^
  --add-data "app\static;app\static" ^
  --add-data "app\migrations;app\migrations" ^
  --add-data "app\scripts\airports.csv;app\scripts" ^
  --add-data "app\core\airtrack_solutions.pub;app\core" ^
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
  --distpath gates\gate3\dist ^
  --workpath gates\gate3\build ^
  --specpath gates\gate3 ^
  gates\gate3\service.py

echo.
echo Build complete. Bundle: gates\gate3\dist\AirTrack\
