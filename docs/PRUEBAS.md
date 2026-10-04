# Plan de aceptación v3

1. Inicializar PostgreSQL y crear admin.
2. Login admin y creación de manager/operator/viewer.
3. Confirmar que viewer no puede escribir.
4. Confirmar que operator puede alta/movimiento pero no usuarios/auditoría.
5. Confirmar que manager puede crear ubicación y ver auditoría.
6. Confirmar que admin puede cambiar rol/desactivar usuario.
7. Abrir dos navegadores con operadores diferentes e intentar salida simultánea del mismo equipo: solo una debe completar.
8. Validar que `operator_name` corresponde a la sesión, no a un campo enviado por cliente.
9. Escanear Asset y QR de ubicación desde móvil HTTPS.
10. Ejecutar `BACKUP_POSTGRES.bat`, restaurar en BBDD de prueba y comprobar conteos.
11. Ejecutar `python tests/postgres_smoke.py`.


## Gate automatizado de Windows
Ejecutar `VALIDAR_RELEASE.bat`. Debe finalizar con `RELEASE GATE AUTOMATIZADO SUPERADO`.

## Criterio STABLE
Solo marcar STABLE cuando:
- `VALIDAR_RELEASE.bat` = PASS;
- dos sesiones distintas no puedan completar simultáneamente una salida incompatible del mismo activo;
- la capacidad de una ubicación no pueda sobrepasarse con dos operaciones concurrentes;
- un móvil HTTPS pueda escanear al menos un QR/Asset real o quede documentado el fallback manual;
- se haya creado y restaurado un backup en una base de prueba.
