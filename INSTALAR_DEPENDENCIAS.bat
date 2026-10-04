@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>&1 || (echo [ERROR] Python 3 no encontrado.& pause & exit /b 1)
python -m pip install -r requirements.txt
if errorlevel 1 (echo [ERROR] Fallo instalando dependencias.& pause & exit /b 1)
echo [OK] Dependencias instaladas.
pause
