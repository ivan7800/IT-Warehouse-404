@echo off
setlocal
cd /d "%~dp0"
if not exist "CONFIG_LOCAL.bat" (echo [ERROR] Falta CONFIG_LOCAL.bat.& pause & exit /b 1)
call CONFIG_LOCAL.bat
where pg_restore >nul 2>&1 || (echo [ERROR] pg_restore no esta en PATH.& pause & exit /b 1)
set /p "DUMP=Ruta completa al .dump: "
if not exist "%DUMP%" (echo [ERROR] No existe el dump.& pause & exit /b 1)
echo ADVERTENCIA: restaurar puede sobrescribir datos de la BBDD destino.
set /p "OK=Escribe RESTAURAR para continuar: "
if /I not "%OK%"=="RESTAURAR" exit /b 2
pg_restore --clean --if-exists --no-owner --dbname="%WAREHOUSE_DATABASE_URL%" "%DUMP%"
if errorlevel 1 (echo [ERROR] Restauracion con incidencias. Revisa salida.& pause & exit /b 1)
echo [OK] Restauracion completada.
pause
