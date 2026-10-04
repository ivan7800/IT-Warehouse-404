@echo off
setlocal
cd /d "%~dp0"
if not exist "CONFIG_LOCAL.bat" (echo [ERROR] Falta CONFIG_LOCAL.bat. Copia CONFIG_EJEMPLO.bat y configura PostgreSQL.& pause & exit /b 1)
call CONFIG_LOCAL.bat
python server.py
if errorlevel 1 pause
