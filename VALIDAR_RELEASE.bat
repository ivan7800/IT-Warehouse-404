@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================================
echo   IT Warehouse 404 v3 - RELEASE GATE
echo ========================================================
echo.
if not exist "CONFIG_LOCAL.bat" (
  echo [FAIL] Falta CONFIG_LOCAL.bat.
  echo Copia CONFIG_EJEMPLO.bat, configura PostgreSQL y repite.
  pause
  exit /b 1
)
call CONFIG_LOCAL.bat
where python >nul 2>&1 || (echo [FAIL] Python no encontrado.& pause & exit /b 1)
python -c "import psycopg,qrcode; print('[PASS] Dependencias Python')" || (echo [FAIL] Dependencias. Ejecuta INSTALAR_DEPENDENCIAS.bat.& pause & exit /b 1)
python -m py_compile server.py db.py security.py scripts\*.py || (echo [FAIL] py_compile.& pause & exit /b 1)
echo [PASS] Sintaxis Python
python -m unittest tests.test_core -v || (echo [FAIL] Unit tests.& pause & exit /b 1)
python tests\static_checks.py || (echo [FAIL] Static checks.& pause & exit /b 1)
python -c "from db import connect; c=connect(); print('[PASS] PostgreSQL:',c.info.dbname); c.close()" || (echo [FAIL] Conexion PostgreSQL.& pause & exit /b 1)
python tests\postgres_smoke.py || (echo [FAIL] PostgreSQL smoke test.& pause & exit /b 1)
where pg_dump >nul 2>&1 || (echo [FAIL] pg_dump no esta en PATH.& pause & exit /b 1)
where pg_restore >nul 2>&1 || (echo [FAIL] pg_restore no esta en PATH.& pause & exit /b 1)
echo.
echo ========================================================
echo [PASS] RELEASE GATE AUTOMATIZADO SUPERADO
echo Pendiente manual: navegador Windows + movil HTTPS +
echo prueba de dos operadores simultaneos.
echo ========================================================
pause
exit /b 0
