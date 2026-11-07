# Revisión en navegador: vendedor, gerencia, despachador y administrador

> Recorrido hecho el 6-nov-2026 sobre `main` en `2d610d2` (PR #66, con todas las sesiones integradas). Repite con el equipo la revisión que se hizo con la cuenta B2B de Felipe y que encontró errores que las pruebas automáticas no veían. Los clientes (B2B y B2C) los revisa otra sesión.

## Cómo se probó

- **Stack local aislado** (`cofrial-equipo`): base, web, 50 camiones simulados en 5 contenedores, Grafana, 120 km/h, sin claves de IA y con `DESPACHO_AUTO=0`. Las claves se generaron para este stack con `web/clientes/cuentas_demo.py` y no están en el repositorio.
- **Navegador integrado de la app** (Chromium), en escritorio y en móvil emulado de 375 px, con tema claro y oscuro. Con él se miraron las pantallas, se hizo doble clic, se usó atrás y adelante y se confirmó lo que se ve en el mapa y en Grafana.
- **Auditoría de diseño en las páginas de cada rol**: cada una se cargó a 375 y a 1280 px, en claro y en oscuro, midiendo desborde horizontal e imágenes rotas (192 mediciones: vendedora 52, gerencia 52, despachador 36, administrador 52). El color y el contraste se miraron solo en una muestra a ojo (panel, embudo, ficha, cobranza, flota, armar despacho, `/demo/`, usuarios, stock y Grafana), no en todas las páginas.
- **Rastreo por HTTP** de cada rol: inicia sesión, sigue todos los enlaces que encuentra (35 a 82 páginas por rol) y anota lo que no da 200. Se repitió con las seis cuentas que creé desde `/operacion/cuentas/`.
- **Envíos simultáneos** (hilos, varias sesiones a la vez) para imitar doble clic, dos pestañas y un reintento tras perder la respuesta.

## Lo recorrido

| Rol | Pantallas y acciones | Menú sin 403 | Resultado |
|---|---|---|---|
| Vendedora y vendedor | Panel, embudo, nuevo prospecto, clientes y ficha, interacción, dirección, cobranza (facturar, pagar), solicitudes de empresas, requerimientos, IA, demanda, alertas de frío | Sí, tras H-1 | 1 enlace que daba 403 (corregido). 1 desborde móvil (corregido). Doble envío de prospecto (corregido) |
| Gerencia | Lo mismo en solo lectura, flota, armar despacho (solo mira) y BI | Sí | No ve botones de escritura y los POST dan 403 |
| Despachador | Flota, armar despacho con dos clientes, cierre de viaje, despacho automático, alertas y demanda | Sí | Doble clic y despacho automático simultáneo: un solo viaje |
| Administrador | Todo lo anterior más `/demo/` con escenarios, `/bi/`, `/operacion/` (stock, usuarios por tipo, claves) | Sí | Crear un usuario de cada tipo, reponer stock con aviso, escenarios y claves: bien |

**Que el menú no ofrezca lo que da 403.** El rastreo de las cuentas de prueba y de las seis nuevas dejó solo un enlace prohibido (H-1). Matriz de permisos que dio el stack (GET):

| Ruta | vendedor | gerencia | despachador | admin | cliente |
|---|---|---|---|---|---|
| `/bi/` | 403 | 200 | 403 | 200 | 403 |
| `/demo/`, `/operacion/…` | 403 | 403 | 403 | 200 | 403 |
| `/flota/`, `/flota/despachar/`, `/api/flota/` | 403 | 200 | 200 | 200 | 403 |
| `/crm/embudo/`, `/crm/cobranza/`, `/crm/solicitudes/`, `/crm/ia/` | 200 | 200 | 403 | 200 | 403 |
| `/crm/prospectos/nuevo/` | 200 | 403 | 403 | 200 | 403 |

Los POST de escritura (despachar, activar escenario, sumar stock, asignar clave, correr despacho automático, cerrar viaje) dan 403 a quien no corresponde: pasan despachador y administrador, o solo el administrador.

**Filtros y navbar al moverse.** En `/crm/clientes/` el texto de búsqueda se recuerda al abrir una ficha y volver con «atrás» (la lista sigue filtrada y la pestaña activa sigue marcada).

**Un vendedor no ve la cartera ajena.** Con `vendedor2` y con un vendedor recién creado y sin cartera: ficha, prospecto, interacción, mover etapa, cancelar y facturar de otra cartera dan 404 o «Orden no encontrada en tu cartera»; el panel, la cobranza, las alertas y los requerimientos no muestran al Hospital. El reclamo de un cliente B2C sin vendedor lo ven todos los vendedores: es la bandeja común que ya estaba documentada.

## Flujos que vería el profesor

| Flujo | Qué se hizo | Resultado |
|---|---|---|
| Crear un usuario de cada tipo | Las seis tarjetas de `/operacion/cuentas/` por HTTP y una gerencia más por el navegador (claves distintas primero y doble clic al final). Cada cuenta nueva inició sesión | ✓ Una sola cuenta con el doble clic; «Las claves no coinciden» conserva usuario y nombre. Cada rol llega a su pantalla de inicio sin 403 en el menú |
| Asignar clave | Clave común y clave corta rechazadas; una buena entra y la anterior ya no | ✓ |
| Reponer stock y ver el aviso | Ana pide «Avisarme» por 3 camarones; el vendedor lo ve en demanda; el administrador repone; Ana ve «Ya disponible» y el contador del menú | ✓ (ver A-1 sobre el doble envío) |
| Despacho con dos clientes | Ana (B2C) y el Hospital (B2B) en un viaje: camión sugerido, ruta de 4,2 km con los dos números y mapa de la flota | ✓ Con doble clic sobre «Despachar y salir ahora»: un viaje |
| Escenario en el mapa y en el tablero | «Falla de frío ahora» sobre ese viaje (`/demo/`): el camión pasó a rojo con 14,3 °C, `/crm/alertas/` y Grafana mostraron los mismos 2 pedidos afectados. Luego «Cliente no recibe» en otro viaje: el pedido quedó «Entrega no concretada» y llegó el requerimiento | ✓ |
| Empresa nueva | Registro, intento de entrar antes (explica que espera), aprobación por dos vendedores a la vez | ✓ Una aprobación; la otra recibe «otra persona la revisó»; gerencia no ve el botón |

## Errores encontrados y corregidos

Cada uno tiene su commit.

| # | Gravedad | Pasos | Esperado | Real | Arreglo |
|---|---|---|---|---|---|
| H-1 | Media | Entrar como vendedor y abrir `/crm/alertas/` sin pedidos afectados | Que el botón del estado vacío no lleve a una página prohibida | «Ver la flota en vivo» llevaba a `/flota/` y daba 403 | La plantilla muestra el botón solo a quien ve la flota |
| H-2 | Alta | Pedir `/favicon.ico` (lo hace el navegador desde páginas sin `<link rel=icon>`, como las de error 400, 429 y 500) más de 60 veces en 10 minutos desde una misma IP | Que no cuente como barrido | Contaba como «no encontrado»: la IP entera recibía 429 («Demasiados intentos»), también el inicio de sesión de los demás. En la defensa toda la sala sale por una IP. Me bloqueé yo mismo al auditar | El limitador ignora `/favicon.ico` y `/apple-touch-icon*.png`; prueba nueva |
| H-3 | Baja | Móvil de 375 px: ficha de un cliente o de un prospecto | Sin desplazamiento horizontal | El campo «Detalle» de «Registrar interacción» (`size="50"`) medía 457 px y la página, 490 px | CSS: el campo se encoge y baja de línea |
| H-4 | Media | Enviar «Nuevo prospecto» 4 veces a la vez (dos pestañas o respuesta perdida) | Un prospecto | Cuatro prospectos iguales en el embudo | Bloqueo del vendedor: la misma persona en 60 s lleva al prospecto ya creado; prueba nueva |
| H-5 | Baja | «Clasificar con IA» sobre un reclamo que el sistema ya clasificó (p. ej. «Entrega no concretada»), con la IA caída y desde una pestaña vieja | Decir que la IA no respondió y que el reclamo no cambió | «La IA lo clasificó como … (confianza None)» | El aviso comprueba primero si la IA estuvo disponible; prueba nueva |

## Filas de la matriz repetidas tras la integración

Las de este recorrido. Las de cliente (CU-02, CU-05, E-02, E-06, E-08, E-09, E-15, E-33) son de la otra sesión.

| Fila | Qué se repitió | Resultado |
|---|---|---|
| CU-01 | Las cuentas de prueba y las seis nuevas: destino por rol y menú | ✓ |
| CU-06 | Ficha propia y ajena, interacción, agregar dirección (y una mala) | ✓ |
| CU-08 | Orden del portal en la ficha con chip «OC pendiente»; cancelar una «Recibida» (stock repuesto); alerta de frío | ✓ |
| CU-10 | Tipos de las seis columnas en `telemetria`; 50 camiones, 16 780 filas | ✓ |
| CU-11 | La base rechaza `lat = 200` (restricción `lat_valida`) | ✓ |
| CU-12 | Panel, API (`resumen` con `sin_senal`), cierre de viaje por rol | ✓ gerencia y vendedora reciben 403; el despachador debe confirmar |
| CU-13 | `/bi/` por rol, refresco de 5 s, escritura de gerencia (403), el CRM y Grafana dan los mismos 2 pedidos | ✓ |
| RN-09 | Matriz de rutas por rol, vendedor ajeno y vendedor sin cartera | ✓ |
| RN-13 | Falla de frío con 2 clientes a bordo | ✓ CRM y BI coinciden |
| RN-14 | IA sin claves: reintento, panel `/crm/ia/`, clasificación manual | ✓ salvo H-5 |
| RN-16 | Pedido refrigerado en camión congelado | ✓ rechazado con el motivo |
| E-04 | 4 despachos simultáneos del mismo pedido con el mismo camión | ✓ **ya no ocurre**: un viaje, la orden «Despachada» |
| E-04 por el despacho automático | 3 pasadas manuales a la vez | ✓ un viaje, ningún camión con dos |
| E-07 | Pedido con la dirección sin ubicar, a mano y por el despacho automático | ✓ **ya no ocurre**: se rechaza con «ubícala antes de despacharla» |
| E-10 | `docker compose stop flota-5` por 2 min | ✓ **ya no ocurre**: el panel marca «Sin señal 10» y vuelve a 0 al reiniciar |
| E-13 | Vendedor cancela un pedido «Despachada» | ✓ rechazado, stock intacto |
| E-16 | Registro de empresa, intento previo, dos aprobaciones a la vez | ✓ |
| E-18 | 11 claves malas a una cuenta | ✓ solo esa cuenta recibe 429 por 15 minutos; otra entra |
| E-19 y E-20 | 12 GET y 13 POST hostiles por rol (ids enormes, `%00`, scripts, 5 000 caracteres, SQL) | ✓ ninguno da 500; el texto con `<img onerror>` queda escapado |
| E-22 | IA caída: soporte, reintento y panel | ✓ |
| E-26 | Detener y volver a iniciar un contenedor del simulador | ✓ sin pérdida de pedidos; sin viaje en curso, así que no probé el salto en el mapa |
| E-27 | Cierre manual de un viaje en curso | ✓ pide confirmación; sin ella no cierra |
| E-29 | Cliente ganado sin cuenta del portal: el administrador la crea | ✓ el cliente entra con la cuenta enlazada |
| E-23 y E-11 | — | No concluyentes; ver «Sin probar» |

## Errores abiertos, por gravedad

| # | Gravedad | Qué pasa | Qué hacer |
|---|---|---|---|
| A-1 | Media | **Reponer stock enviado dos veces suma dos veces.** Cuatro POST simultáneos de +10 dejaron +40 (dos pestañas, o reintentar tras perder la respuesta). El botón se desactiva al primer clic y eso cubre el doble clic; no cubre dos pestañas | Un identificador de un solo uso por formulario, o mostrar «última reposición hace N s» en la fila. No lo cambié: toca el formulario y el modelo de la operación |
| A-2 | Baja | Registrar una interacción dos veces a la vez guarda dos filas (4 de 4). Misma causa que A-1, sin daño: es un texto repetido | Igual que A-1, si se quiere |
| A-3 | Baja, pero visible en vivo | Un cliente creado por el administrador desde `/operacion/cuentas/` queda con la dirección **sin ubicar**: su primer pedido no se puede despachar hasta que el despachador pulse «Ubicar» en Armar despacho (1 s, usa el servicio de mapas, necesita internet) | Dicho en el guion (`docs/guion-defensa.md`, flujo 5) o ubicar la dirección al crear la cuenta |
| A-4 | Baja | Una cuenta bloqueada por 10 claves malas queda 15 minutos sin salida y no hay pantalla ni comando para desbloquearla (los contadores viven en la memoria del único proceso) | Límite conocido (E-18). En la defensa, esperar o reiniciar la web |
| A-5 | Informativa | En el navegador del panel perdí la sesión tres veces (las dos primeras justo tras recrear la web, la tercera sin reinicio). Por HTTP las sesiones sobreviven a `docker compose restart web` y no logré repetirlo | Sin causa conocida. Si ocurre en la defensa: volver a ingresar |
| A-6 | Informativa | `/bi/` abre Grafana sin la barra de Cofrial y sin un «volver»; el menú lo abre en otra pestaña, así que no estorba | Límite |

No encontré errores en `web/flota/rutas.py`, `web/flota/demo.py`, `web/flota/escenarios.py` ni en `iot/`.

## Sin probar

- **Un teléfono real** y otros navegadores (Safari, Firefox): el móvil fue la emulación de 375 px del panel de la app.
- **Los diálogos `confirm()`** del navegador del panel se rechazan solos: en `/demo/` los botones de escenario piden confirmar y tuve que aceptarlos desde la consola. En un Chrome normal el profesor los verá como cuadros de confirmación.
- **Contraste de color de todas las pantallas** en claro y oscuro: solo un muestreo a ojo; la medición automática fue de desborde.
- **CU-12 con OSRM caído (E-23)**: apunté la web a un servidor muerto, pero las rutas probadas ya estaban en `ruta_cache` y no hubo llamada que fallar; para probarlo hace falta una ruta nueva.
- **E-11** (ruptura mientras el camión está en la última puerta) y **E-26 con un viaje en curso** (el salto del camión en el mapa).
- **Documentos** (guía, factura y nota de crédito) en PDF: solo las acciones, no abrí los archivos.
- **IA con claves reales**, **Mercado Pago** y **AWS**: nada de esto corre en el stack local. El despacho automático se probó con la pasada manual, no con el servicio `despachador` encendido.
- **Dos pestañas reales**: se imitaron con envíos simultáneos desde hilos.

## Cómo repetirlo

```bash
docker build -t <proyecto>-web ./web
docker compose run --rm -e DEMO_PASSWORD= -e ADMIN_PASSWORD= -e VELOCIDAD_MEDIA_KMH=50 web python manage.py test --noinput
```

`VELOCIDAD_MEDIA_KMH=50` hace falta si el `.env` del stack usa 120 km/h para que los viajes terminen pronto: una prueba exige el valor por defecto. Las claves del stack se calculan con `python3 web/clientes/cuentas_demo.py --env .env --url http://localhost:<puerto> --salida <archivo fuera del repositorio>`.
