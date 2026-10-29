# Recuperación de clave (cuenta web)

Documento de referencia para la funcionalidad «¿Olvidaste tu clave?». Complementa `docs/cuentas-y-permisos.md` y `docs/credenciales-y-cuentas.md`.

**Estado:** implementado en rama `sergio/recuperar-clave` (pendiente de merge a `main`). Mismo patrón que la rama remota `claude/cuentas-recuperar-registro` (Eric), sin el alcance de registro de empresa.

## 1. Problema y objetivo

Los usuarios ingresan con **correo como nombre de usuario** (`User.username` / `User.email`). Antes solo podían cambiar la clave **con sesión iniciada** (`/cuenta/clave/`) o mediante **administración** (`/admin/` o comandos). Faltaba un flujo desde la pantalla de ingreso.

En el prototipo académico muchos correos son ficticios (`@correo.test`, `@*.test`) **sin buzón real**. La funcionalidad debe ser **demostrable** en el laboratorio y, en un despliegue con correo verdadero, **escalable** sin cambiar el diseño.

## 2. Decisión adoptada

Patrón **estándar de Django**: solicitud por correo → **enlace de un solo uso** con token → formulario **elegir clave nueva**, con las mismas reglas que el registro B2C.

**Alternativa evaluada y no implementada en esta entrega:** solicitud visible en CRM → admin o vendedor aprueba → usuario elige clave (mejor narrativa sin SMTP; más desarrollo). Queda descrita en la sección 6.

Registro formal: `docs/decisiones.md` (entrada del 29-oct-2026).

## 3. Flujo funcional

### Usuario (sin sesión)

1. En `/cuenta/entrar/`, enlace **«¿Olvidaste tu clave?»** → `/cuenta/recuperar/`.
2. Indica el **correo con el que ingresa**.
3. Pantalla **«Revise su correo»** (`/cuenta/recuperar/enviado/`) — **misma respuesta** exista o no la cuenta (no revelar cuentas registradas).
4. Abre el enlace del mensaje → `/cuenta/recuperar/<uid>/<token>/` → elige clave dos veces → `/cuenta/recuperar/listo/` → ingresa con la clave nueva.

### Sistema (técnico)

| Pieza | Ubicación |
|-------|-----------|
| Solicitud | `Recuperar` (`PasswordResetView`) en `web/cofrial/vistas.py` |
| Rutas | `web/cofrial/urls.py` (`recuperar`, `recuperar_enviado`, `recuperar_nueva`, `recuperar_listo`) |
| Plantillas | `web/templates/cuenta/recuperar*.html`, `recuperar_correo.txt`, `recuperar_asunto.txt` |
| Caducidad del enlace | `PASSWORD_RESET_TIMEOUT = 3600` s (1 hora) en `web/cofrial/settings.py` |
| Límite de abuso | `LIMITE_RECUPERAR_HORA` (por defecto 10 POST/hora por IP en `/cuenta/recuperar/`) |

## 4. Correo: prototipo vs producción

| Entorno | Comportamiento |
|---------|----------------|
| **Sin `EMAIL_HOST`** (local / lab por defecto) | `EMAIL_BACKEND = console`: el mensaje **no sale a Internet**; el cuerpo (con el enlace) aparece en **logs del contenedor `web`**. |
| **Con SMTP** (`EMAIL_HOST`, usuario, clave, TLS) | Envío real al buzón del `User.email`. |
| **URL del enlace** | Si existe `DJANGO_CSRF_ORIGINS`, el enlace usa el **primer origen** (IP o dominio público), no el `Host` del pedido (reduce enlaces falsos). |

**Defensa / demo:** las cuentas `@*.test` no tienen buzón; en vivo se copia el enlace desde logs **o** se configura SMTP hacia un correo real de prueba. El reset por administrador en `/admin/` sigue siendo canal de soporte documentado.

## 5. Seguridad

- Token **de un solo uso**; tras cambiar la clave, el enlace deja de servir.
- **No enumeración** de correos en la respuesta al usuario.
- Solo usuarios **activos** reciben enlace.
- **Validación de clave** al guardar (`AUTH_PASSWORD_VALIDATORS`: longitud mínima, clave no común), coherente con `RegistroB2CForm`.
- **Rate limit** en el formulario de solicitud.

**Limitación en demo:** el backend consola expone el enlace a quien lea logs; en producción no debe usarse consola — SMTP (p. ej. Amazon SES) y HTTPS (`DJANGO_HTTPS=1`).

## 6. Alternativa: aprobación en CRM

**Idea:** el usuario envía correo → **admin o vendedor** ve la solicitud en CRM → al aprobar, el usuario define clave nueva (mismas reglas).

**Ventaja:** no depende de buzones ficticios; alinea B2B con validación humana del ejecutivo.

**Por qué no en esta entrega:** alcance acotado y reutilización del patrón Django ya probado; evita duplicar lógica antes de coordinar merge con registro de empresa en la rama de Eric.

**Si se implementa después:** estados pendiente/aprobado/rechazado, formulario final con `validate_password`, pruebas automáticas y actualización de este documento.

## 7. Cómo probar

### Pruebas automáticas

```bash
docker compose exec web python manage.py test cofrial.tests_cuentas
```

Cubre: enlace en login, cambio de clave, enlace de un solo uso, correo inexistente, URL pública con `CSRF_TRUSTED_ORIGINS`.

### Prueba manual (local)

1. `docker compose up -d --build web`
2. Abrir `/cuenta/recuperar/` con `ana@correo.test`
3. `docker compose logs web -f` → copiar la URL `/cuenta/recuperar/.../`
4. Abrir en el navegador; clave nueva ≥ 8 caracteres y no común
5. Ingresar en `/cuenta/entrar/`

## 8. Variables de entorno

Ver `.env.example`: `LIMITE_RECUPERAR_HORA`, bloque `EMAIL_*`, `DJANGO_CSRF_ORIGINS`.
