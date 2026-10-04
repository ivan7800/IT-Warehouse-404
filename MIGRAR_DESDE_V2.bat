@echo off
setlocal
cd /d "%~dp0"
if not exist "CONFIG_LOCAL.bat" (echo [ERROR] Falta CONFIG_LOCAL.bat.& pause & exit /b 1)
call CONFIG_LOCAL.bat
set /p "OLDDB=Ruta completa a warehouse.db v2: "
python scripts\migrate_v2_sqlite.py "%OLDDB%"
pause
