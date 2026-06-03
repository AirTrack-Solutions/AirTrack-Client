@echo off
:: Gate 3 build — run on Trevor's Windows laptop (admin not required for build)
pip install -r requirements.txt
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
  --hidden-import pymysql ^
  service.py
echo.
echo Build complete. Bundle is in dist\AirTrack\
