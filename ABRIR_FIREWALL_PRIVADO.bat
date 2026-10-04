@echo off
setlocal
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
  echo Solicitando permisos de administrador...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
if exist CONFIG_LOCAL.bat call CONFIG_LOCAL.bat
if "%WAREHOUSE_PORT%"=="" set "WAREHOUSE_PORT=8765"
netsh advfirewall firewall delete rule name="IT Warehouse 404 v3" >nul 2>&1
netsh advfirewall firewall add rule name="IT Warehouse 404 v3" dir=in action=allow protocol=TCP localport=%WAREHOUSE_PORT% profile=private
if errorlevel 1 (echo [ERROR] No se pudo crear la regla.& pause & exit /b 1)
echo [OK] Puerto %WAREHOUSE_PORT% permitido SOLO en perfil de red privada.
pause
