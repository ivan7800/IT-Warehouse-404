@echo off
setlocal
cd /d "%~dp0"
if not exist "CONFIG_LOCAL.bat" (echo [ERROR] Crea CONFIG_LOCAL.bat a partir de CONFIG_EJEMPLO.bat.& pause & exit /b 1)
call CONFIG_LOCAL.bat
python scripts\init_db.py || (pause & exit /b 1)
python scripts\create_admin.py
pause
