# 404 QA REPORT — IT Warehouse 404 v3.0.0

## Resumen
La v3 transforma la aplicación local v2.1 en una arquitectura central multiusuario PostgreSQL, preservando las reglas de integridad de inventario y eliminando la suplantación manual del operador.

## COMPROBADO en este entorno
- `py_compile` de servidor, DB, seguridad y scripts: PASS.
- `node --check static/app.js`: PASS.
- 4 pruebas unitarias de hashing/sesiones/máquina de estados: PASS.
- IDs HTML duplicados: 0.
- referencias DOM JS ausentes: 0.
- campo editable `operator`: eliminado.
- presencia de CSRF, roles y scanner móvil: PASS estático.
- secretos reales incrustados: no se han añadido.

## PENDIENTE DE PRUEBA REAL
- Conexión PostgreSQL y ejecución del schema.
- login contra PostgreSQL real.
- concurrencia real con dos clientes simultáneos.
- backup/restore con `pg_dump` / `pg_restore` en Windows.
- cámara móvil por HTTPS con certificado confiable.

Motivo: el entorno de construcción no dispone de PostgreSQL ni acceso a PyPI; no fue posible instalar `psycopg`/`qrcode` para levantar la integración completa.

## Gate
**RC / PRE-STABLE** hasta ejecutar `tests/postgres_smoke.py` y una prueba de aceptación en Windows + PostgreSQL + móvil.


## Hardening adicional de cierre
- Capacidad de ubicación bloqueada con `FOR UPDATE` también en altas y movimientos para evitar carreras.
- Protección contra desactivar/degradar al último administrador activo.
- `audit_log` protegido por triggers append-only contra UPDATE/DELETE.
- `tests/postgres_smoke.py` ampliado para validar triggers, constraints e índices críticos.
- `VALIDAR_RELEASE.bat` añadido como gate reproducible en Windows.

## Gate actual
**RELEASE CANDIDATE**. Todo lo ejecutable sin PostgreSQL real en este entorno pasa. La etiqueta **STABLE** debe reservarse para una instalación que supere `VALIDAR_RELEASE.bat` y la aceptación manual de concurrencia + móvil HTTPS.
