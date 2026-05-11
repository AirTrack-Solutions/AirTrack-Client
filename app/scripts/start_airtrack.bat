@echo off
setlocal
cd /d "%~dp0"

echo.
echo  ============================================
echo   AirTrack Windows
echo  ============================================
echo.
echo  Starting AirTrack...
echo.

docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERROR: Could not start AirTrack.
    echo  Make sure Docker Desktop is running, then try again.
    echo.
    pause
    exit /b 1
)

echo.
echo  AirTrack is running!
echo  Opening http://localhost:5000 in your browser...
echo.
timeout /t 3 /nobreak >nul
start http://localhost:5000
