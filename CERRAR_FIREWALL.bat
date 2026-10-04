@echo off
net session >nul 2>&1
if errorlevel 1 (powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
netsh advfirewall firewall delete rule name="IT Warehouse 404 v3"
pause
