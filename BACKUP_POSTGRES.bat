@echo off
setlocal
cd /d "%~dp0"
if not exist "CONFIG_LOCAL.bat" (echo [ERROR] Falta CONFIG_LOCAL.bat.& pause & exit /b 1)
call CONFIG_LOCAL.bat
where pg_dump >nul 2>&1 || (echo [ERROR] pg_dump no esta en PATH. Instala PostgreSQL client tools.& pause & exit /b 1)
if not exist "backups" mkdir backups
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do set "D=%%a%%b%%c%%d"
set "T=%time::=-%"
set "T=%T: =0%"
set "OUT=backups\warehouse_%D%_%T:~0,8%.dump"
pg_dump --format=custom --file="%OUT%" "%WAREHOUSE_DATABASE_URL%"
if errorlevel 1 (echo [ERROR] Backup fallido.& pause & exit /b 1)
echo [OK] Backup: %OUT%
pause
