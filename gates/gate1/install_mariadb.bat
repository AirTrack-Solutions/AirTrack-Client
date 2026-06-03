@echo off
:: Gate 1 — Silent MariaDB install
:: Run from an admin command prompt in the gates\gate1\ folder.
:: Place mariadb-11.4.x-winx64.msi in the same folder before running.

set MSI=mariadb-11.4.x-winx64.msi
set DATADIR=C:\AirTrackData\

echo [1/4] Installing MariaDB...
msiexec /i %MSI% /quiet /norestart ^
  SERVICENAME=AirTrackDB ^
  PORT=3307 ^
  PASSWORD=Gate1RootPass! ^
  ALLOWREMOTEMACHINE=0 ^
  BUFFERPOOLSIZE=64 ^
  DATADIR=%DATADIR%

if %ERRORLEVEL% neq 0 (
    echo FAIL: msiexec returned %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
echo [1/4] Install complete.

echo [2/4] Waiting for service to start...
timeout /t 5 /nobreak >nul
sc query AirTrackDB | findstr /i "RUNNING" >nul
if %ERRORLEVEL% neq 0 (
    echo FAIL: AirTrackDB service not running.
    exit /b 1
)
echo [2/4] Service running.

echo [3/4] Initialising database and user...
"C:\Program Files\MariaDB 11.4\bin\mysql.exe" ^
  --port=3307 --host=127.0.0.1 --user=root --password=Gate1RootPass! ^
  < init_db.sql

if %ERRORLEVEL% neq 0 (
    echo FAIL: init_db.sql returned %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
echo [3/4] Database and user created.

echo [4/4] Running verification...
python verify.py
if %ERRORLEVEL% neq 0 (
    echo FAIL: verify.py returned %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo.
echo Gate 1 PASS.
