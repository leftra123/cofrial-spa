# Mercado Pago — Payment Brick (modo prueba)

Integración de **Card Payment Brick** en un **modal centrado** (560px) en el carrito (`/carrito/`). En la demostración lo usan el particular y la empresa. Quien no paga ahora puede **Generar orden** y pagarla a 30 días.

## Objetivo

- Formulario de tarjeta MP en modal (ancho fijo ~560px, skeleton mientras carga el SDK).
- La **orden, stock y boleta** se crean cuando el pago queda **`approved`** (POST `/v1/payments` con el token del Brick).
- Sin credenciales MP → **Generar orden** a 30 días (el particular descarga el documento al momento; la empresa, la factura después de la entrega).

## Variables de entorno

```env
MERCADOPAGO_ACCESS_TOKEN=TEST-...    # credencial privada (backend)
MERCADOPAGO_PUBLIC_KEY=TEST-...      # credencial pública (Brick en el navegador)
MERCADOPAGO_PUBLIC_URL=http://localhost:8000   # webhook en AWS (HTTPS); en local con Brick basta HTTP salvo que quieras webhook o contexto seguro (ver abajo)
```

`activo()` exige **ACCESS_TOKEN y PUBLIC_KEY**.

## En AWS

Agregar `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_PUBLIC_KEY` y `MERCADOPAGO_PAYER_EMAIL` a `aws/.estado/secretos.env` (claves `TEST-`, nunca en git) y ejecutar `bash aws/provision.sh recrear-web`. El pago va directo a `/v1/payments`, sin webhook, por lo que funciona con el sitio en HTTP. Sin esas claves el carrito vuelve al cobro simulado.

## Flujo

1. Particular o empresa abre el carrito (resumen con total y dirección).
2. **Pagar ahora** abre el modal con **«Confirma tu compra»** (total, documento, dirección, quién recibe). **Confirmar y pagar** sigue al Card Payment Brick; **Cancelar compra** (o Esc, o un clic fuera) cierra sin cobrar y el carrito avisa, con un mensaje neutro, que no se cobró nada. El formulario de tarjeta se monta solo al confirmar. En el formulario, Esc o la × preguntan «¿Cancelar la compra?» antes de cerrar. Si la tarjeta no resulta, el modal deja reintentar y no crea el pedido.
3. **Generar orden**, debajo, crea el pedido a 30 días sin pasar por Mercado Pago.
4. `onSubmit` del Brick → `POST /carrito/mp/pagar/` con `formData` de MP.
5. Backend valida carrito, crea `CheckoutPago`, llama `POST /v1/payments`.
6. Si `approved` → `generar_ordenes` + documento pagado → redirect al pedido.

Webhook (`/carrito/mp/webhook/`) y URLs de vuelta siguen disponibles para pagos pendientes en producción.

## Archivos

| Archivo | Rol |
|---------|-----|
| `web/static/js/mp-brick.js` | Inicializa el Brick |
| `web/templates/pedidos/carrito.html` | Contenedor `#mp-brick-container` |
| `web/pedidos/mercadopago.py` | `pagar_con_brick`, webhook |
| `web/pedidos/views.py` | `mp_pagar_brick`, contexto del carrito |

## Tarjetas de prueba

[Documentación MP Chile — tarjetas de prueba](https://www.mercadopago.cl/developers/es/docs/checkout-bricks/additional-content/test-cards)

Las cuentas demo con correo `@correo.test` se mapean a `@testuser.com` al crear el pago (Mercado Pago no acepta el dominio `.test`). El Brick recibe el correo normalizado en `initialization.payer.email`.

**Tarjeta de prueba aprobada (Chile):** nombre del titular **`APRO`**, documento **RUT** (no «Otro»), número de tarjeta y CVV según la doc MP. Si al pulsar **Pagar** no pasa nada, recarga con Cmd+Shift+R (hubo un bug de JS en `onSubmit` ya corregido).

## Desarrollo local (Docker)

El servicio `web` **copia el código al construir la imagen**. Si cambias plantillas, CSS o `mp-brick.js` y sigues viendo el modal antiguo:

```bash
docker compose build web && docker compose up -d web
```

En Chrome: recarga forzada (**Ctrl+Shift+R** o Cmd+Shift+R). Comprueba que el botón diga **«Pagar ahora · $…»** y, debajo, **«Generar orden»**.

Para no reconstruir en cada cambio, usa `docker-compose.override.example.yml` → `docker-compose.override.yml` (monta `./web` en vivo).

## HTTPS en local (recomendado para pruebas del Brick)

Chrome muestra *«El llenado automático… se inhabilitó porque este formulario no usa una conexión segura»* en `http://localhost:8000`. No impide pagar con tarjetas TEST, pero el checkout se comporta mejor en **contexto seguro** (cookies `Secure`, autofill, menos avisos).

### Opción A — Caddy + mkcert (equipo)

1. Instalar [mkcert](https://github.com/FiloSottile/mkcert) e instalar la CA en el sistema:

   ```bash
   brew install mkcert nss
   ./scripts/generar-certs-local.sh
   ```

2. Levantar web **y** proxy TLS:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build web caddy
   ```

3. Entrar por **`https://localhost:8443`** (Caddy). Evita mezclar con `http://localhost:8000` mientras el stack HTTPS esté activo: antes teníamos cookies `Secure` y fallaba el CSRF en HTTP.

Variables que aplica `docker-compose.https.yml` (puedes copiarlas a `.env` si quieres documentarlas):

```env
HTTPS_PUERTO=8443
DJANGO_HTTPS=0
DJANGO_CONFIAR_PROXY=1
DJANGO_CSRF_ORIGINS=https://localhost:8443,http://localhost:8000
MERCADOPAGO_PUBLIC_URL=https://localhost:8443
```

### Opción B — túnel público (webhook MP desde la nube)

Si necesitas que Mercado Pago llame a `/carrito/mp/webhook/` desde internet:

```bash
ngrok http 8000
```

Copia la URL `https://….ngrok-free.app` en `MERCADOPAGO_PUBLIC_URL` y reinicia `web`. Para el Brick en el navegador puedes seguir con la opción A o abrir la URL ngrok.

## Checklist

- [ ] Brick visible en carrito B2C con credenciales TEST
- [ ] Pago aprobado → orden + boleta + redirect
- [ ] Pago rechazado → mensaje en Brick, carrito abierto
- [ ] B2B sin Brick
- [ ] Sin credenciales → Webpay simulado

## Emulador de Mercado Pago (13-nov-2026)

Sin `MERCADOPAGO_ACCESS_TOKEN` y `MERCADOPAGO_PUBLIC_KEY`, el carrito ya no se queda solo con «Generar orden»: ofrece **Pagar ahora con Mercado Pago** con un emulador (`web/static/js/mp-emulador.js`, `POST /carrito/mp/emulador/`, `mercadopago.pagar_emulado`). Muestra una tarjeta de prueba y deja elegir cómo responde el pago, con los mismos titulares de las tarjetas de prueba de Mercado Pago: `APRO` (aprobado), `FUND` (fondos insuficientes) y `OTHE` (rechazado por error general).

- Usa el mismo camino que el Brick real: valida el carrito, crea el `CheckoutPago` y pasa por `_aplicar_respuesta_pago`. Solo un pago **aprobado** crea la orden, el documento pagado (boleta o factura al contado) y el pago (`medio = mercadopago`, referencia `EMU-…`) y descuenta el stock. Un rechazo no deja nada y el carrito queda como estaba.
- No sale nada a internet y no se cobra. Con credenciales reales el emulador desaparece y se ve el Brick; `MP_EMULADOR=0` lo apaga aunque no haya credenciales.
- Los rechazos se explican en español (`DETALLES_DE_RECHAZO`), también en el pago real.
- Pruebas: `pedidos/tests_mp_emulador.py` (aprobado, rechazado, titular inventado, institución con factura, y que solo aparezca sin credenciales).
