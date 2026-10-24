# Cuentas y permisos

Este documento no contiene claves. Las claves viven solo en `aws/.estado/secretos.env` (ignorado por git) y en las variables de la instancia web (`DEMO_PASSWORD`, `ADMIN_PASSWORD`).

## Cómo se manejan las claves

- Cada clave se fija **solo al crear la cuenta** (`cargar_demo`): las cuentas `admin@` y `eric@` usan `ADMIN_PASSWORD` y el resto `DEMO_PASSWORD`. Reiniciar el contenedor no las cambia.
- Cada persona cambia la suya en **Cambiar mi clave** (`/cuenta/clave/`, enlace en el menú de usuario).
- El administrador crea, desactiva o cambia claves de cualquier cuenta en `/admin/` (Usuarios).
- `python manage.py cambiar_clave_demo` es un comando manual para dejar todas las cuentas de demostración con una clave nueva.

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
