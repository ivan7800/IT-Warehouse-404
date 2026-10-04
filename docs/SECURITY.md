# Seguridad

- Contraseñas: PBKDF2-HMAC-SHA256, salt aleatorio, 310.000 iteraciones.
- Sesiones: token aleatorio; en PostgreSQL solo se guarda SHA-256 del token.
- Cookie: HttpOnly + SameSite=Lax; Secure al usar TLS.
- CSRF: cabecera `X-CSRF-Token` en escrituras autenticadas.
- Autorización: roles comprobados en backend.
- SQL: parámetros `%s`; no se concatena entrada del usuario en consultas de datos.
- Login: limitación básica por IP en memoria.
- Navegador: CSP, DENY framing, nosniff, no-referrer, permisos mínimos.
- Auditoría: sin API para mutarla.
- Secretos: `CONFIG_LOCAL.bat` no debe subirse a Git.

## No cubre por sí solo

- SSO/Entra ID.
- MFA.
- WAF/rate limit distribuido.
- alta disponibilidad.
- exposición directa a Internet.

Para un despliegue corporativo amplio, colocar detrás de reverse proxy TLS y controles de red gestionados por TI.
