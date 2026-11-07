# Matriz de cobertura de casos de uso

> Recorrido hecho el 6-nov-2026 como lo haría el profesor en la defensa: cada rol, los caminos alternativos y los bordes. Parte de `main` en 3731f71 (PR #58 y #59 incluidos). **No incluye los cambios de las sesiones entrega-cliente, flota-autonoma, simulador-ia, admin-operacion y vistas-filtros**: la última sección dice qué filas repetir cuando se fusionen.

**Cómo se probó.** *Vivo:* stack local aislado con base, web, 50 camiones simulados y Grafana, velocidad 120 km/h y sin claves de IA, manejado por HTTP con varias sesiones a la vez. *Auto:* prueba automática de Django (o `iot/test_simulador.py`). *Código:* lectura del código, sin ejecutarlo.

**Resultado.** ✓ funciona. **Corregido:** fallaba y se arregló en esta rama. **Abierto:** falla y está sin arreglar. **Límite:** decisión o alcance que hay que saber explicar.

**Suite al cerrar esta rama:** 492 pruebas de Django en verde, 9 saltadas (5 son los errores abiertos marcados con `@abierto`, que fallan si se activan), y 17 de `iot/test_simulador.py` en verde.

En la columna de pruebas, los archivos `tests_casos_*` son los nuevos de esta rama: `cofrial/tests_casos_sesion.py`, `pedidos/tests_casos_compra.py`, `crm/tests_casos_cartera.py` y `flota/tests_casos_viaje.py`.

## Casos de uso del informe

| ID | Caso | Cómo se probó | Resultado | Prueba automática |
|---|---|---|---|---|
| CU-01 | Iniciar sesión por perfil | Vivo con las 7 cuentas: destino por rol, registro B2C y solicitud de empresa | ✓ | `cofrial/tests_rutas.py`, `cofrial/tests_cuentas.py` |
| CU-02 | Catálogo con precio por perfil | Vivo: filtros con basura, mismo producto con dos precios | ✓ | `catalogo/tests.py` (`visitante_ve_lista_publica`, `cliente_institucional_ve_su_lista`) |
| CU-03 | Carrito | Vivo: cantidades absurdas, doble agregar, producto sin stock y retirado | **Corregido** (dos Agregar a la vez perdían una unidad) | `pedidos/tests.py`, `tests_casos_compra` |
| CU-04 | Generar órdenes | Vivo: B2C, B2B con y sin OC, mixto, dirección ajena, stock insuficiente, carrera | **Corregido** (A2 prometía crear una dirección y no había dónde; se agregan A6 y A7) | `pedidos/tests.py`, `tests_casos_compra`, `tests_casos_sesion` |
| CU-05 | Seguir el pedido | Vivo: mapa, avisos, API con id ajeno | ✓ con E-09 abierto | `flota/tests.py`, `pedidos/tests_entrega.py` |
| CU-06 | Gestionar clientes | Vivo: ficha propia y ajena, interacción, direcciones | **Corregido** (faltaba agregar dirección) | `crm/tests.py`, `tests_casos_cartera` |
| CU-07 | Pipeline | Vivo: cada transición y cada rechazo | **Corregido** (A5 no existía; RUT sin validar) | `crm/tests.py`, `tests_casos_cartera` |
| CU-08 | Seguimiento de pedidos web | Vivo: orden del portal en la ficha, chip de OC pendiente, alerta y cancelación | **Corregido** (el vendedor no podía cancelar) | `crm/tests.py`, `tests_casos_cartera` |
| CU-09 | Requerimiento con IA | Vivo sin claves: queda sin clasificar, reintento avisa, clasificación manual | **Corregido** (sin IA se perdía el cruce con telemetría; no había cómo cerrar el caso) | `crm/tests.py`, `tests_casos_cartera` |
| CU-10 | Enviar telemetría | Vivo: 50 camiones, campos y tipos en la tabla, inserción continua | ✓ | `flota/tests.py`, `iot/test_simulador.py` (17) |
| CU-11 | Detectar ruptura | Vivo: consulta 5 da 0 filas; lectura con latitud 200 rechazada por la base | ✓ | `flota/tests.py` (`rechaza_valores_fuera_de_rango`) |
| CU-12 | Monitorear flota | Vivo: panel, API, cierre manual, roles | ✓ con E-07 y E-10 abiertos | `flota/tests.py`, `flota/tests_rutas.py` |
| CU-13 | Dashboard BI | Vivo: `/bi/` por rol, refresco de 5 s, escritura de gerencia rechazada, CRM y Grafana dan los mismos pedidos afectados | **Corregido** (el conteo y la tabla no coincidían) | `cofrial/tests_bi.py` |
| CU-14 | Asistente de tienda | Vivo sin claves: responde por regla o avisa indisponibilidad | ✓ | `catalogo/tests.py` (`un_cliente_no_recibe_datos_de_otro`, `inyeccion_y_fuera_de_alcance_ni_llegan_al_modelo`) |

## Reglas de negocio

| ID | Regla | Cómo se probó | Resultado | Prueba automática |
|---|---|---|---|---|
| RN-01 | Precio por perfil | Vivo y Auto | ✓ | `pedidos/tests.py` (`rn01_...`) |
| RN-02 | Stock transaccional | Vivo: dos sesiones compran las 5 últimas a la vez; una orden, stock 0 | ✓ | `pedidos/tests.py` (`no_se_vende_dos_veces_la_ultima_unidad`) |
| RN-03 | Un carrito abierto | Vivo: 6 Agregar a la vez sobre un cliente sin carrito | ✓ | `pedidos/tests.py` (`rn03_...`) |
| RN-04 | Dirección propia | Vivo con id ajeno, texto y número enorme | ✓ | `pedidos/tests.py` (`rn04_...`) |
| RN-05 | OC B2B | Vivo: compra sin OC y OC de 31 caracteres | ✓ | `pedidos/tests.py` (`rn05_...`) |
| RN-06 | Precio congelado | Auto | ✓ | `pedidos/tests.py` (`rn06_...`) |
| RN-07 | Cancelación | Vivo: cliente en «Despachada» rechazado; vendedor | **Corregido** (la regla existía solo en el admin de Django, donde el vendedor no entra) | `pedidos/tests.py`, `tests_casos_cartera`, `tests_casos_viaje` |
| RN-08 | Repetir pedido | Vivo tras compra mixta | **Corregido** (copiaba solo los congelados) | `pedidos/tests.py`, `tests_casos_compra` |
| RN-09 | Cartera | Vivo: matriz de 36 rutas por 8 perfiles | **Corregido** (reclamos, panel de IA e indicador se veían entre carteras; un vendedor clasificó uno ajeno) | `crm/tests.py`, `tests_casos_cartera` |
| RN-10 | Transiciones | Vivo | **Corregido** (faltaba el retroceso a «Contactado») | `crm/tests.py`, `tests_casos_cartera` |
| RN-11 | Cierre | Vivo: perder sin motivo, ganar sin RUT, RUT inválido, duplicado con otro formato | **Corregido** (aceptaba `11111111-2` y el mismo RUT sin puntos) | `crm/tests.py`, `tests_casos_cartera` |
| RN-12 | Interacciones | Vivo | ✓ | `crm/tests.py` (`contactado_exige_una_interaccion`) |
| RN-13 | Alerta de frío | Vivo: ruptura forzada con dos clientes en el camión | **Corregido** en CRM y BI; E-09 abierto en la vista del cliente | `crm/tests.py`, `tests_casos_cartera` |
| RN-14 | Clasificación con IA | Vivo sin claves; Auto con proveedor simulado | ✓ | `crm/tests.py` (`si_la_api_falla_el_requerimiento_se_conserva`) |
| RN-15 | Pedido a nombre del cliente | Vivo: carrito del cliente antes y después | **Corregido** (borraba el carrito del cliente) | `crm/tests.py`, `tests_casos_cartera` |
| RN-16 | Separación térmica | Vivo: mixto da 2 órdenes con su referencia; camión de otro rango rechazado | ✓ | `pedidos/tests.py` (`rn09_un_carrito_mixto...`), `flota/tests.py` (`no_mezcla_cadena_de_frio`) |
| RN-17 | Guía de despacho | Vivo y Auto | ✓ | `pedidos/tests_documentos.py` |
| RN-18 | Público paga al comprar | Vivo con Webpay simulado. **Mercado Pago no se probó en vivo** (sin credenciales) | ✓ | `pedidos/tests_documentos.py`, `pedidos/tests_mercadopago.py` |
| RN-19 | Factura B2B | Vivo: antes de entregar rechazada, ajena rechazada | ✓ | `pedidos/tests_documentos.py`, `tests_casos_viaje` |
| RN-20 | Pagos | Vivo: negativo, sobre el saldo, sobre una guía | ✓ | `pedidos/tests_documentos.py` |
| RN-21 | Nota de crédito | Vivo: sin rango, sobre una guía | ✓ | `pedidos/tests_documentos.py` |
| RN-22 | Cobranza | Vivo y Auto | ✓ | `pedidos/tests_documentos.py` |

Los nombres de algunas pruebas conservan una numeración antigua de reglas (`rn09_un_carrito_mixto` es RN-16). Vale la numeración del informe.

## Bordes que el informe no menciona

| ID | Caso | Cómo se probó | Resultado | Prueba automática |
|---|---|---|---|---|
| E-01 | Sesión vencida a mitad de una compra | Vivo: borrar la cookie y confirmar | **Corregido.** Antes, página en blanco (405) al volver del login, también en el CRM. Ahora vuelve a la página de origen, con aviso y carrito intacto | `tests_casos_sesion` |
| E-02 | Comprar el último stock a la vez | Vivo | ✓ el segundo ve «No hay stock» y el botón bloqueado | `pedidos/tests.py` |
| E-03 | Doble envío del formulario de compra | Vivo: 4 POST a la vez | ✓ una orden y un descuento. Si la respuesta buena se pierde, el segundo ve «Tu carrito está vacío»; el botón se desactiva al primer clic | `tests_casos_compra` |
| E-04 | Doble despacho (doble clic, dos pestañas) | Vivo: 4 POST a la vez | **Abierto, grave** (flota-autonoma). La orden quedó **Entregada** sin viaje y CAM-01 con 3 viajes abiertos | `tests_casos_viaje`, se salta hasta fusionar |
| E-05 | Carrito mixto | Vivo | ✓ | `pedidos/tests.py` |
| E-06 | Producto retirado con carrito armado | Vivo | **Corregido.** Se compraba igual | `tests_casos_compra` |
| E-07 | Pedido con dirección sin ubicar | Vivo: empresa con calle inexistente en un viaje de 3 paradas | **Abierto, grave** (flota-autonoma). El camión vuelve y la orden queda «Despachada» para siempre; cerrar el viaje lo rechaza | `tests_casos_viaje`, se salta hasta fusionar |
| E-08 | Dos clientes en un viaje | Vivo y Auto: cada uno ve y confirma solo lo suyo | ✓ (la ruta propia la cambia entrega-cliente) | `tests_casos_viaje` |
| E-09 | Ruptura después de recibir | Vivo | **Corregido** en CRM y BI. **Abierto** en la vista del cliente (entrega-cliente): sigue viendo «variación de temperatura» y la temperatura actual de un camión que ya no lleva su carga | `tests_casos_cartera`; `tests_casos_viaje`, se salta hasta fusionar |
| E-10 | Camión sin señal | Vivo: 45 s sin lecturas | **Abierto** (flota-autonoma). El panel lo muestra normal; solo existe «Sin lecturas» si nunca reportó | `tests_casos_viaje`, se salta hasta fusionar |
| E-11 | Ruptura durante una entrega | Vivo y Auto | **Corregido.** Con el camión en la última puerta no contaba, porque `llegada_en` se fija al llegar | `tests_casos_cartera` |
| E-12 | Reclamo sobre un viaje con alerta | Vivo sin IA | **Corregido.** Ventas no veía la telemetría si la IA fallaba | `tests_casos_cartera` |
| E-13 | Cancelar una orden despachada | Vivo y Auto | ✓ rechazada, stock intacto | `tests_casos_viaje` |
| E-14 | Cancelar dos veces | Auto | ✓ repone una vez | `tests_casos_compra` |
| E-15 | Cliente que no confirma | Vivo: pasó solo a «Entregada» a los 120 s | ✓ y se puede facturar | `pedidos/tests_entrega.py`, `tests_casos_viaje` |
| E-16 | Empresa sin aprobar | Vivo: explica que espera aprobación; gerencia no aprueba; dos vendedores a la vez aprueban una sola vez | ✓ | `cofrial/tests_cuentas.py` |
| E-17 | B2B sin OC | Vivo | ✓ referencia WEB propia por orden | `pedidos/tests.py` |
| E-18 | Cuenta bloqueada por claves malas | Vivo | **Corregido.** Con 2 procesos la clave correcta entraba o daba 429 al azar. Ahora 10 fallos bloquean siempre, solo a esa cuenta | `cofrial/tests_seguridad.py`; el cambio de procesos se verificó en vivo |
| E-19 | Vendedor mira la cartera ajena | Vivo: cliente, prospecto, documento y orden por URL | **Corregido** en reclamos; el resto ya daba 404 | `tests_casos_cartera`, `crm/tests.py` |
| E-20 | URLs con ids ajenos o enormes | Vivo: 13 GET y más de 40 POST hostiles | ✓ ningún 500 | `cofrial/tests_seguridad.py` |
| E-21 | Mensajes técnicos | Vivo | **Corregido.** El CRM mostraba `invalid literal for int()` | `tests_casos_cartera` |
| E-22 | IA caída | Vivo sin claves: soporte, reintento, panel, sugerencias y asistente siguen | ✓ | `crm/tests.py` |
| E-23 | OSRM caído | Vivo con host muerto | ✓ ruta aproximada. **Límite:** vista previa y despacho tardan 8 s cada uno | `flota/tests_rutas.py` |
| E-24 | Base caída | Vivo: `docker compose stop db` | ✓ 503 propio sin traza; `/salud/` sigue en 200 y `/salud/bd/` da 503; vuelve sola en 1 s y el simulador se reconecta en 5 s | `cofrial/tests_seguridad.py` |
| E-25 | Grafana caído | Vivo | ✓ 502 con página propia | `cofrial/tests_bi.py` |
| E-26 | Simulador detenido y vuelto a iniciar | Vivo: reinicio con CAM-05 en ruta | ✓ sin perder pedidos. **Límite:** el viaje recomienza desde la base y el camión salta en el mapa | `iot/test_simulador.py` |
| E-27 | Cierre manual de un viaje que ya llegó | Vivo | Ver E-07: rechazado aunque queden órdenes colgadas | `tests_casos_viaje`, se salta hasta fusionar |
| E-28 | Cliente ganado sin dirección | Vivo | **Corregido** para pedidos del vendedor | `tests_casos_cartera` |
| E-29 | Cliente ganado sin cuenta del portal | Vivo | **Abierto** (derivar a admin-operacion): no puede entrar; solo compra por su vendedor | Sin prueba |
| E-30 | Cuenta B2B sin vendedor | Vivo con `felipe@cofrial.cl` | **Abierto, datos de demo.** Sus pedidos solo los ven gerencia y admin. **No usar esa cuenta para mostrar el CRM del vendedor.** Asignarla exige cambiar `crm/tests.py` (`rn09_...`), por eso se dejó | Sin prueba |
| E-31 | Reclamo sin cierre | Vivo | **Corregido.** «Marcar como resuelto»; ningún flujo llenaba `respondido_en` ni el estado «resuelto». **Límite:** el cliente ve el estado, no un texto de respuesta | `tests_casos_cartera` |
| E-32 | Quién confirma y prepara un pedido | Código | **Límite.** «Confirmada» y «En preparación» solo se pasan en el admin de Django; despachar las recorre automáticamente | `pedidos/tests.py` |
| E-33 | Reprogramar una entrega fallida | Auto | ✓ **Límite:** `orden.despacho` apunta al último viaje, y las alertas del primero dejan de contar para esa orden | `pedidos/tests_entrega.py` |
| E-34 | Editar o borrar una dirección | Código | **Límite.** Se puede agregar; editar o borrar queda en el admin de Django | Sin prueba |
| E-35 | RUT de datos de demo | Vivo | **Límite.** `76.543.210-K` (Supermercados del Sur) no tiene dígito válido; es dato sembrado y las pruebas lo usan | Sin prueba |

## Errores abiertos, por gravedad

| # | Fila | Gravedad | Sesión | Qué hacer |
|---|---|---|---|---|
| 1 | E-04 | Alta: un doble clic falsea una entrega | flota-autonoma | Bloquear camión y órdenes **y revalidar el estado después del bloqueo**. Bloquear sin revalidar no basta, porque `avanzar` salta de «Despachada» a «Entregada» |
| 2 | E-07, E-27 | Alta: pedido colgado sin salida | flota-autonoma | Rechazar órdenes sin lat/long al despachar, o dejar cerrar un viaje con órdenes pendientes |
| 3 | E-09 | Media: alarma falsa al cliente | entrega-cliente | Usar `crm.servicios.fin_de_exposicion` en `pedidos.servicios.seguimiento` y en los avisos |
| 4 | E-10 | Media: el panel oculta una falla de señal | flota-autonoma | Marcar lecturas viejas |
| 5 | E-29 | Media | admin-operacion | Crear la cuenta del portal al ganar o desde la ficha |
| 6 | E-30 | Baja, pero visible en vivo | Sin sesión | Asignar vendedor a la cuenta y ajustar la prueba `rn09_...` |

## Qué repetir después de fusionar

Estas pruebas no vieron los cambios de las otras sesiones. Tras cada fusión, correr la suite y además:

```bash
docker compose run --rm -e DEMO_PASSWORD= -e ADMIN_PASSWORD= -e CASOS_ABIERTOS=1 web python manage.py test flota.tests_casos_viaje --noinput
```

Si una prueba marcada con `@abierto` pasa, quitar el decorador. La de `sin_senal` espera una clave `sin_senal` en la tarjeta: ajustarla al nombre que use flota-autonoma.

| Sesión | Filas por repetir |
|---|---|
| entrega-cliente | CU-05, RN-13, E-08, E-09, E-11, E-15, E-33. Revisar que `seguimiento` y los avisos sigan la regla de RN-13 |
| flota-autonoma | CU-12, RN-16, E-04, E-07, E-10, E-13, E-23, E-26, E-27. Con el despacho automático, repetir E-04 y E-07 también por esa vía |
| simulador-ia | CU-10, CU-11, CU-13, RN-13, RN-14, E-11, E-22, E-26 |
| admin-operacion | CU-01, RN-02, RN-09, E-02, E-06, E-16, E-18, E-29. Si agrega desbloqueo de cuentas, probarlo con el proceso único de gunicorn |
| vistas-filtros | CU-02, CU-06, CU-08, RN-09, E-19, E-20. Los filtros de `/crm/requerimientos/` deben partir de `requerimientos_visibles`, no de `Requerimiento.objects` |

## Sin probar

- Mercado Pago en vivo: sin credenciales de prueba en este stack.
- IA con claves reales: el camino feliz quedó con proveedor simulado. Correr `python3 aws/verificar.py --ia` antes de la defensa.
- AWS: nada de esto se desplegó. El cambio a un proceso de gunicorn hay que verlo en la EC2.
- Navegador real: el recorrido fue por HTTP. Doble clic, mapa y pantallas móviles no se miraron con los ojos.
