@echo off
setlocal
cd /d "%~dp0"
echo === IT Warehouse 404 v3 diagnostico ===
where python >nul 2>&1 && python --version || echo [FALTA] Python
where psql >nul 2>&1 && psql --version || echo [AVISO] psql no esta en PATH
if exist CONFIG_LOCAL.bat (echo [OK] CONFIG_LOCAL.bat existe) else echo [FALTA] CONFIG_LOCAL.bat
python -c "import psycopg,qrcode; print('[OK] psycopg y qrcode disponibles')" 2>nul || echo [FALTA] Ejecuta INSTALAR_DEPENDENCIAS.bat
if exist CONFIG_LOCAL.bat (
  call CONFIG_LOCAL.bat
  python -c "from db import connect; c=connect(); print('[OK] PostgreSQL conectado:', c.info.dbname); c.close()" 2>nul || echo [ERROR] No conecta a PostgreSQL
)
pause
