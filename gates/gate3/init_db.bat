@echo off
:: Wraps mysql.exe with shell redirection — Inno Setup [Run] cannot use <
"%ProgramFiles%\MariaDB 11.4\bin\mysql.exe" ^
  --port=3307 --host=127.0.0.1 --user=root --password=Gate1RootPass! ^
  < "%~dp0init_db.sql"
