# IT Warehouse 404 — QA v3.1 RC1

Cambios implementados en la rama de revisión:
- Entradas y salidas parciales de lotes.
- Traslados parciales con conservación del remanente.
- Vinculación explícita origin_item_id y destination_item_id.
- Rechazo de entrada inicial con cero unidades y validación estricta de quantity/new_quantity.
- Pruebas de integración con PostgreSQL desechable, incluida concurrencia.
- GitHub Actions CI para sintaxis, unitarias, checks estáticos e integración.

No certificados en esta revisión:
- Interacción de botones/diálogos real en Windows y móvil.
- Permisos de cámara y HTTPS en móviles corporativos.
- Restauración PostgreSQL real y comparación íntegra.
- Pruebas HTTP detalladas de roles/CSRF y operación multiusuario corporativa.

Estado: RELEASE CANDIDATE. Ver docs/VALIDACION-V3.1.md.
