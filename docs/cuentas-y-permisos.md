# Cuentas y permisos

Este documento no contiene claves. Las claves viven solo en `aws/.estado/secretos.env` (ignorado por git) y en las variables de la instancia web (`DEMO_PASSWORD`, `ADMIN_PASSWORD`).

## Cómo se manejan las claves

- **Cada cuenta de prueba tiene su propia clave** (desde el 29-oct-2026), derivada de `DEMO_PASSWORD` (o de `ADMIN_PASSWORD` para `admin@` y `eric@`) y del nombre de usuario (`web/clientes/cuentas_demo.py`). No hay una variable por cuenta: la web la calcula al crear la cuenta y la hoja para entregar se calcula en el computador con el mismo `.env`:
  `python3 web/clientes/cuentas_demo.py --env aws/.estado/secretos.env --url http://IP --salida aws/.estado/hoja-cuentas.md` (en local: `--env .env --url http://localhost:8000 --salida hoja-cuentas.md`). La hoja trae claves reales: `hoja-cuentas*.md` está en `.gitignore`; se imprime o se entrega en mano, nunca por GitHub, Trello ni chat.
- Una cuenta que todavía tiene la clave común de antes pasa sola a la suya en el siguiente arranque (`cargar_demo`); una clave que su dueño ya cambió no se toca. Reiniciar el contenedor no cambia ninguna otra clave.
- Cada persona cambia la suya en **Cambiar mi clave** (`/cuenta/clave/`, enlace en el menú de usuario).
- El administrador crea, desactiva o cambia claves de cualquier cuenta en `/admin/` (Usuarios).
- `python manage.py cambiar_clave_demo` es un comando manual que restablece las cuentas de prueba a su clave propia (`--misma` pone la misma en todas, como antes).

## Crear una cuenta o recuperar la clave (sin ayuda del equipo)

- **Particular (B2C):** `/cuenta/registro/`. Queda activa y compra de inmediato con la lista pública.
- **Empresa (B2B):** `/cuenta/registro/empresa/` (enlace en Ingresar y en la portada). La cuenta queda **inactiva y sin vendedor**: aparece en el CRM, pestaña **Solicitudes** (con un contador), donde un vendedor la aprueba y queda en su cartera, o el administrador la aprueba eligiendo el vendedor; gerencia solo la ve. Al aprobarla se activa y queda una nota en la ficha; al rechazarla se borra. Si la empresa intenta entrar antes, la pantalla le dice que su cuenta aún no está activa (solo si la clave es correcta, para no revelar qué correos existen). No hay migración: «pendiente» es `cliente B2B sin vendedor` + `cuenta inactiva`.
- **Olvidé mi clave:** «¿Olvidaste tu clave?» en Ingresar (`/cuenta/recuperar/`). Llega un enlace de un solo uso que dura una hora; la respuesta es la misma exista o no el correo. El enlace usa la dirección pública (la primera de `DJANGO_CSRF_ORIGINS`) y no el `Host` del pedido. Tope de 10 pedidos por IP y hora (`LIMITE_RECUPERAR_HORA`). Necesita un correo de envío (ver `docs/credenciales-y-cuentas.md`, «Correo»); sin él, el mensaje se escribe en el registro del contenedor. Las cuentas de prueba usan correos ficticios: para mostrarlo, crear una cuenta con un correo real.

## Cuentas

| Cuenta | Rol | Puede | No puede (respuesta) |
|---|---|---|---|
| `admin@cofrial.cl`, `eric@cofrial.cl` | Administrador / despacho | Todo: CRM, flota, cerrar despachos, `/admin/` | — |
| `felipe@cofrial.cl` | Cliente institucional B2B | Catálogo con lista institucional, carrito, órdenes, orden de compra | CRM y flota (403); pedidos ajenos (404) |
| `sergio@cofrial.cl`, `ana@correo.test` | Cliente particular B2C | Catálogo al público, carrito, seguimiento de sus pedidos | CRM y flota (403); pedidos ajenos (404) |
| `abastecimiento@hospital.test` | Cliente institucional B2B | Igual que Felipe | CRM y flota (403) |
| `vendedora@cofrial.cl`, `vendedor2@cofrial.cl` | Vendedor | CRM de su cartera, prospectos nuevos | Flota (403) |
| `gerencia@cofrial.cl` | Gerencia | Lectura del CRM y los tableros | Crear prospectos (403) |
| `despacho@cofrial.cl` | Despachador | Flota, armar y cerrar despachos | Embudo del CRM (403) |

## Pruebas

`python3 aws/verificar.py` inicia sesión con cada cuenta (claves desde el entorno o `secretos.env`) y comprueba los casos de permisos: B2C en `/crm/` y `/flota/` (403), vendedora en `/flota/` (403), despachador en `/flota/` (200) y en `/crm/embudo/` (403), gerencia en `/crm/prospectos/nuevo/` (403), vendedora en la misma ruta (200), administrador en `/flota/` (200) y pedido ajeno (404). Las pruebas automáticas (`manage.py test`) cubren además que una clave cambiada no se pisa al reiniciar.
