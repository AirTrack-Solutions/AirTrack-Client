@echo off
:: Step 1: Create database and application user
"%ProgramFiles%\MariaDB 11.4\bin\mysql.exe" ^
  --port=3307 --host=127.0.0.1 --user=root --password=Gate1RootPass! ^
  < "%~dp0init_db.sql"

if %ERRORLEVEL% neq 0 (
    echo FAIL: init_db.sql returned %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

:: Step 2: Load full AirTrack schema into airtrack database
"%ProgramFiles%\MariaDB 11.4\bin\mysql.exe" ^
  --port=3307 --host=127.0.0.1 --user=root --password=Gate1RootPass! ^
  airtrack ^
  < "%~dp0schema.sql"

if %ERRORLEVEL% neq 0 (
    echo FAIL: schema.sql returned %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo Database and schema initialised.
