# IT Warehouse 404 — revisión RC2 (integrada en GitHub)

La entrega RC2 del ZIP proporcionado por el usuario se ha integrado en la rama de revisión existente, conservando las mejoras posteriores de CI e integración con PostgreSQL. La rama `main` no se modifica por seguridad hasta aceptar el Pull Request.

## Correcciones incluidas
- Relación de lotes derivados mediante `origin_item_id` y `destination_item_id`.
- Validación de cantidades para entradas, salidas y ajustes.
- Rechazo de alta inicial de lotes con cantidad cero.
- Comprobaciones estáticas y pruebas unitarias de regresión.
- Pruebas de PostgreSQL, concurrencia, roles y CSRF, además de backup/restore, procedentes de la rama mejorada.

## Verificación pendiente
- Revisar la última ejecución de GitHub Actions para esta versión.
- Windows y dispositivos móviles reales, navegación por todos los botones y cámara QR.
- Despliegue corporativo y restauración bajo el procedimiento de IT.

**RC2 no implica certificación para producción.**
