@echo off
:: Gate 1 teardown — stop and uninstall MariaDB, remove data directory.
:: Run from an admin command prompt.

echo [1/3] Stopping service...
sc stop AirTrackDB
timeout /t 3 /nobreak >nul

echo [2/3] Uninstalling MariaDB...
msiexec /x mariadb-11.4.x-winx64.msi /quiet /norestart

echo [3/3] Removing data directory...
rmdir /s /q C:\AirTrackData\

echo Teardown complete.
