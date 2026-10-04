# Arquitectura v3

```text
PC / móvil
   │ HTTPS recomendado
   ▼
ThreadingHTTPServer (server.py)
   ├─ Auth / RBAC / CSRF
   ├─ API inventario
   ├─ API movimientos
   ├─ API usuarios
   ├─ API auditoría
   └─ QR PNG
          │
          ▼
      PostgreSQL
   users / sessions
   locations / items
   movements / audit_log
```

## Concurrencia
Los movimientos bloquean la fila de material con `SELECT ... FOR UPDATE` dentro de una transacción PostgreSQL. Dos operadores no pueden completar de forma simultánea transiciones incompatibles sobre el mismo registro.

## Identidad
`operator_user_id` y `operator_name` se toman de la sesión del servidor. El frontend no envía un campo operador editable.

## Auditoría
Los cambios relevantes generan una fila `audit_log` con usuario, acción, entidad, resumen, metadatos, IP y User-Agent. No existe endpoint de edición/borrado del audit log.

## Seguridad de red
El servidor puede escuchar en `0.0.0.0`, pero la regla incluida de Windows Firewall solo abre el puerto en redes `Private`. Para móvil/cámara se recomienda HTTPS con certificado confiable.
