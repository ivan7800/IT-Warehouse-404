# IT Warehouse 404 v3.1.0-rc1

Inventario de almacén IT **multiusuario**, pensado para un servidor central y clientes Windows/móvil en LAN.

## Cambios de la v3.1 RC

- Entrada y salida parcial de stock por cantidades, con destinatario y ticket.
- Traslado parcial entre ubicaciones: mantiene remanente en origen y crea lote separado en destino.
- Formulario de movimientos con cantidad seleccionable.
- **Pendiente de validación real:** integración PostgreSQL, movimientos simultáneos y restauración de backups. No desplegar en producción hasta superar el gate.

## Qué cambia respecto a v2.1

- PostgreSQL central en lugar de SQLite local.
- Usuarios y roles: `admin`, `manager`, `operator`, `viewer`.
- Sesiones HTTP con token aleatorio almacenado mediante hash.
- Contraseñas PBKDF2-SHA256 con salt y 310.000 iteraciones.
- Protección CSRF en operaciones de escritura.
- El operador de cada movimiento procede de la sesión autenticada: ya no es un texto editable.
- Auditoría por usuario, IP, entidad y acción.
- Transacciones y `SELECT ... FOR UPDATE` para impedir movimientos concurrentes incoherentes, incluida la capacidad de ubicaciones.
- QR de material y ubicación.
- Escáner móvil de QR/Code128/Code39/EAN mediante `BarcodeDetector` cuando el navegador lo soporte.
- Fallback manual por Asset Tag, serie o ubicación.
- Administración de usuarios/roles con protección para conservar al menos un administrador activo.
- Migrador de SQLite v2.x a PostgreSQL v3.

## Roles

| Rol | Lectura | Entradas/movimientos | Crear ubicaciones | Auditoría | Usuarios |
|---|---:|---:|---:|---:|---:|
| viewer | Sí | No | No | No | No |
| operator | Sí | Sí | No | No | No |
| manager | Sí | Sí | Sí | Sí | No |
| admin | Sí | Sí | Sí | Sí | Sí |

Los usuarios se desactivan; no se borran, para preservar la trazabilidad histórica.

## Requisitos servidor

- Windows 10/11 o Windows Server con Python 3.10+.
- PostgreSQL 14+ recomendado.
- `psycopg` y `qrcode` (se instalan con `requirements.txt`).
- Red privada LAN para los clientes.

## Puesta en marcha

### 1. Crear PostgreSQL

Desde `psql` como administrador, usando una contraseña propia:

```sql
CREATE USER warehouse WITH PASSWORD 'CAMBIA_ESTA_CLAVE';
CREATE DATABASE warehouse404 OWNER warehouse;
```

No publiques esa contraseña ni `CONFIG_LOCAL.bat`.

### 2. Dependencias

Ejecuta:

```text
INSTALAR_DEPENDENCIAS.bat
```

### 3. Configuración local

Copia `CONFIG_EJEMPLO.bat` como `CONFIG_LOCAL.bat` y edita:

```bat
set "WAREHOUSE_DATABASE_URL=postgresql://warehouse:TU_PASSWORD@127.0.0.1:5432/warehouse404"
set "WAREHOUSE_HOST=0.0.0.0"
set "WAREHOUSE_PORT=8765"
```

`CONFIG_LOCAL.bat` está excluido mediante `.gitignore`.

### 4. Esquema y primer administrador

Ejecuta:

```text
INICIALIZAR_BBDD.bat
```

Aplica `schema_postgresql.sql` y solicita usuario/contraseña del primer admin.

### 5. Acceso desde la LAN

Ejecuta `ABRIR_FIREWALL_PRIVADO.bat`. La regla solo habilita el puerto en el perfil **Private** de Windows Firewall.

Inicia con `INICIAR_SERVIDOR.bat`.

- Servidor: `http://127.0.0.1:8765`
- Clientes LAN: `http://IP_DEL_SERVIDOR:8765`

No expongas directamente este servicio a Internet.

## HTTPS y cámara móvil

`getUserMedia()`/cámara normalmente requiere **HTTPS** cuando el móvil accede por IP LAN. La v3 admite TLS nativo:

```bat
set "WAREHOUSE_TLS_CERT=C:\certs\warehouse-cert.pem"
set "WAREHOUSE_TLS_KEY=C:\certs\warehouse-key.pem"
set "WAREHOUSE_COOKIE_SECURE=1"
```

El certificado debe ser confiable para los móviles. En una red corporativa es preferible un certificado interno válido o un reverse proxy HTTPS gestionado por TI.

Sin HTTPS sigue disponible la búsqueda manual por Asset/serie/código.

## Migrar v2.x

1. Haz backup de `warehouse.db`.
2. Inicializa una base v3 vacía.
3. Ejecuta `MIGRAR_DESDE_V2.bat`.
4. Indica la ruta del `warehouse.db` v2.
5. Ejecuta una sola vez sobre una v3 vacía.

Los movimientos antiguos conservan el nombre de operador original y quedan vinculados a una cuenta técnica desactivada `legacy-import`.

## Backups

`BACKUP_POSTGRES.bat` usa `pg_dump -Fc` y crea un dump en `backups/`.

`RESTAURAR_POSTGRES.bat` requiere escribir explícitamente `RESTAURAR` antes de usar `pg_restore --clean`.

Prueba restauraciones periódicamente; un backup no probado no es una estrategia de recuperación completa.

## Seguridad implementada

- PBKDF2-SHA256 + salt.
- cookie `HttpOnly`, `SameSite=Lax` y `Secure` cuando hay TLS.
- CSRF para POST/PATCH.
- expiración de sesión.
- limitación básica de intentos de login por IP.
- CSP, `X-Frame-Options`, `nosniff`, Referrer-Policy y Permissions-Policy.
- consultas parametrizadas PostgreSQL.
- roles comprobados también en servidor, no solo en la UI.
- `audit_log` append-only: sin endpoint de modificación/borrado y con triggers PostgreSQL que bloquean `UPDATE`/`DELETE`.
- mensajes de error internos no se entregan al cliente.

## Pruebas

Sin PostgreSQL:

```bash
python -m py_compile server.py db.py security.py scripts/*.py
python -m unittest tests/test_core.py -v
python tests/static_checks.py
node --check static/app.js
```

Con PostgreSQL inicializado:

```bash
python tests/postgres_smoke.py
```

En Windows, después de configurar la instalación, ejecuta también:

```text
VALIDAR_RELEASE.bat
```

Este gate comprueba sintaxis, unit tests, invariantes de seguridad/concurrencia, conexión PostgreSQL, esquema, triggers e índices críticos. La aceptación manual final sigue incluyendo dos operadores simultáneos y cámara móvil HTTPS.

## Limitaciones conocidas

- `BarcodeDetector` depende del navegador. Hay fallback manual.
- La cámara móvil en LAN necesita HTTPS/contexto seguro.
- Esta entrega no incorpora SSO/Entra ID; la autenticación es local a IT Warehouse.
- Para alta disponibilidad, Internet público o varias sedes deben añadirse reverse proxy, TLS corporativo, monitorización y política formal de backup/restore.
