# CHANGELOG

## 3.0.0 — 2026-10-04

### Added
- PostgreSQL central y esquema multiusuario.
- Usuarios, roles y administración de cuentas.
- Sesiones, CSRF y PBKDF2-SHA256.
- Auditoría por operador/IP/acción/entidad.
- Bloqueo transaccional de movimientos concurrentes.
- QR para material y ubicaciones.
- Escáner móvil con cámara + fallback manual.
- Migración desde SQLite v2.x.
- Scripts de inicialización, firewall privado, backup y restore PostgreSQL.
- Soporte TLS opcional en el servidor Python.

### Changed
- El operador ya no se introduce manualmente; se obtiene de la sesión.
- SQLite deja de ser el almacenamiento principal.
- La versión portable sin servidor se elimina del flujo v3 porque es incompatible con la trazabilidad multiusuario central.

### Security
- Cabeceras CSP, frame-deny, nosniff, referrer y permissions policy.
- Rate limit básico de login por IP.
- Errores internos no se exponen al cliente.
- `CONFIG_LOCAL.bat` y backups quedan fuera de Git.


### Hardening de release
- Serialización de comprobaciones de capacidad mediante `FOR UPDATE`.
- Protección del último administrador activo.
- Auditoría append-only reforzada con triggers PostgreSQL.
- Smoke PostgreSQL ampliado.
- Nuevo `VALIDAR_RELEASE.bat` para el gate reproducible en Windows.
