# Revisión de usuarios del 8-nov-2026 y sus correcciones

> Material interno del equipo (el informe del Hito 1 ya se entregó). Una revisión de solo lectura recorrió en el navegador al visitante y las 10 cuentas demo en un stack desechable, y buscó regresiones de las revisiones del 6-nov (`revision-usuarios-clientes.md`, `revision-usuarios-equipo.md`, `matriz-casos-de-uso.md`). Resultado: 0 errores bloqueantes, 0 altos, 1 medio y varios bajos; ninguna regresión (C-01 a C-04, E-04, E-18, E-20, E-25 y H-2 siguieron bien).

## Errores y cómo se corrigieron

| # | Gravedad | Qué pasaba | Arreglo | Prueba |
|---|---|---|---|---|
| 1 | Media | Unos 60 «no encontrado» en 10 minutos bloqueaban con 429 a toda la IP, también la pantalla de ingreso. En la defensa toda la sala sale por una IP | El ingreso (`/cuenta/entrar/` y `/admin/login/`) queda fuera de ese bloqueo y conserva su límite de claves malas por cuenta. Ver «El barrido de rutas no bloquea el ingreso» en `decisiones.md` | `cofrial/tests_seguridad.py`, `BarridoDeRutasTests` |
| 2 | Baja | En pedidos entregados sin lecturas (12 y 13 del Hospital Regional) la temperatura quedaba como bloque gris | Muestra un guion hasta que llega una lectura | `pedidos/tests_temperatura_sin_lecturas.py` |
| 3 | Baja | «Mis pedidos» B2B y la ficha del CRM mostraban el neto como «Total» y Cobranza el monto con IVA | «Total con IVA» con el mismo valor en las tres pantallas (el particular ya incluye el IVA) | `pedidos/tests_total_con_iva.py` |
| 4 | Baja | RUT de ejemplo inválidos en `credenciales-y-cuentas.md`; tres cuentas demo regionales sin documentar; el 403 de `/flota/` decía «sección del CRM» | RUT corregidos (76.111.222-8, 11.222.333-9), cuentas agregadas a las dos tablas, el 403 nombra la sección | `clientes/tests_docs_cuentas.py`, `TextoDelAccesoNegadoTests` |
| 5 | Baja | Con el usuario vacío, Enter movía el foco a la clave sin avisar | Enter avanza solo si el campo tiene texto y falta otro; si no, envía y el navegador marca el campo. Incluye el cambio de ingreso con Enter que estaba sin commitear | `cofrial/tests_cuentas.py`, `PantallaEntrarTests`; verificado con Enter real en el navegador |

## Lo que sigue abierto (no son errores nuevos)

- E-30: la cuenta `felipe@cofrial.cl` sigue sin vendedor. Para mostrar el CRM del vendedor, usar el Hospital Regional.
- Con una IP bloqueada por barrido, quien ya tiene sesión tampoco navega hasta que vence la ventana; reiniciar la web limpia los contadores.
- Una cuenta bloqueada por 10 claves malas queda 15 minutos sin salida (A-4 de `revision-usuarios-equipo.md`).
- El banner de «El camión llegó» tapa cerca de un cuarto de la pantalla en 375 px, sobre el formulario de recepción.

## Sin probar en esa revisión

`/bi/` (no hay Grafana en el stack mínimo), Mercado Pago, la IA con claves reales, el correo real, AWS, los 50 camiones (corrieron 10), un teléfono real, tablet, el tema oscuro y los PDF de documentos.
