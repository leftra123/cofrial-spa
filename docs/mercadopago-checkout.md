# Mercado Pago — Payment Brick (modo prueba)

Integración del canal **B2C** con **Card Payment Brick** en un **modal centrado** (560px) en el carrito (`/carrito/`). El cliente paga sin salir de la tienda Cofrial. El canal **B2B** no usa pasarela.

## Objetivo

- Formulario de tarjeta MP en modal (ancho fijo ~560px, skeleton mientras carga el SDK).
- La **orden, stock y boleta** se crean cuando el pago queda **`approved`** (POST `/v1/payments` con el token del Brick).
- Sin credenciales MP → **Webpay simulado** al confirmar el carrito (CI).

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

1. Cliente B2C abre el carrito (resumen con total y dirección).
2. Pulsa **Continuar al pago** → modal con skeleton y luego Card Payment Brick.
3. `onSubmit` → `POST /carrito/mp/pagar/` con `formData` de MP.
4. Backend valida carrito, crea `CheckoutPago`, llama `POST /v1/payments`.
5. Si `approved` → `generar_ordenes` + boletas → redirect al pedido.

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

En Chrome: recarga forzada (**Ctrl+Shift+R** o Cmd+Shift+R). Comprueba que el botón diga **«Continuar al pago · $…»** (no «Pagar … con Mercado Pago» ni modal «Confirmar compra y pago»).

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
