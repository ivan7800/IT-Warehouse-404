# Validación IT Warehouse 404 v3.1 RC1

## Antes de empezar
Solo usar una base de datos de pruebas. No ejecutar tests mutables en producción.

## Validación automática
- Crear PostgreSQL desechable, definir WAREHOUSE_DATABASE_URL y WAREHOUSE_TEST_DATABASE=1.
- python scripts/init_db.py
- python -m unittest discover -s tests -p test_inventory_integration.py -v
- Comprobar GitHub Actions CI con resultado success.

## Aceptación Windows (pendiente)
- Login correcto e incorrecto, cierre de sesión y expiración.
- Alta individual, alta de stock, entradas parciales, salidas parciales, devolución.
- Movimientos parciales y completos; confirmar ubicación, cantidad e historial.
- Bloquear duplicados de serie/Asset Tag, stock insuficiente y destino sin capacidad.
- Verificar individualmente Dashboard, Inventario, Ubicaciones, Mapa, Movimientos, Escáner, Auditoría y Usuarios.
- Verificar permisos viewer/operator/manager/admin y rechazos HTTP de modificaciones no autorizadas.

## Aceptación móvil (pendiente)
- Abrir mediante HTTPS confiable en red autorizada.
- Lectura QR de material y estantería con cámara.
- Probar permiso denegado y fallback manual.
- Confirmar todos los botones, modales y formulario responsive.

## Recuperación (pendiente)
- Ejecutar BACKUP_POSTGRES.bat sobre un entorno de pruebas.
- Verificar dump con pg_restore --list.
- Crear base vacía separada y restaurar usando pg_restore --no-owner --no-acl.
- Comparar recuentos y relaciones de items, movements, locations, users y audit_log.
- Probar inicio de sesión y consulta del historial tras restauración.
- Documentar tiempo real de recuperación, responsable y fecha.

**STABLE solo después de todas las verificaciones con evidencias.**
