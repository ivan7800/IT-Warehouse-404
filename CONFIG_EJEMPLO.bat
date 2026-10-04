@echo off
REM Copia este archivo como CONFIG_LOCAL.bat y cambia la contraseña.
set "WAREHOUSE_DATABASE_URL=postgresql://warehouse:CAMBIA_ESTA_CLAVE@127.0.0.1:5432/warehouse404"
set "WAREHOUSE_HOST=0.0.0.0"
set "WAREHOUSE_PORT=8765"
set "WAREHOUSE_COOKIE_SECURE=0"
set "WAREHOUSE_SESSION_HOURS=12"
REM Para cámara móvil en LAN, configura HTTPS con certificado confiable:
REM set "WAREHOUSE_TLS_CERT=C:\ruta\warehouse-cert.pem"
REM set "WAREHOUSE_TLS_KEY=C:\ruta\warehouse-key.pem"
