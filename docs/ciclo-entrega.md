# Ciclo de entrega: de la salida del camión a la confirmación del cliente

Este documento describe cómo funciona hoy el reparto, para el informe y para quien construya pantallas encima. No contiene claves.

## 1. Qué pasa, paso a paso

1. **Despachar.** El despachador elige camión y pedidos. El servidor calcula **una vez** la ruta por calles con OSRM (perfil *driving*): base, paradas (la más cercana primero) y vuelta a la base. La polilínea queda guardada en el despacho y es la que dibujan el mapa del despachador y el simulador; el cliente recibe solo su tramo (ver «Qué ve cada cliente de la ruta»). Los pedidos pasan a **Despachada**.
2. **En ruta.** El simulador mueve cada camión *a lo largo de esa polilínea*, una lectura de telemetría cada 5 s. El camión y la ruta del mapa coinciden, y la hora estimada de llegada se calcula con los km que faltan por esa ruta.
3. **En la puerta.** Al llegar a la dirección de un pedido, el simulador pasa el pedido a **Camión en la puerta** y empieza a correr el plazo del cliente. El camión espera unas lecturas y sigue a la próxima parada.
4. **Última parada.** El simulador registra `despacho.llegada_en` y el camión **vuelve a la base** por la ruta de regreso. Al llegar registra `despacho.regreso_en`: recién ahí el camión queda libre para otro despacho. Sin despacho, el camión está **en base**, detenido en su puesto, enviando telemetría.
5. **El cliente revisa y responde** (banner, campanita y pantalla del pedido). Primero ve el paso de revisión: los productos con sus cantidades y la temperatura del viaje, y elige **Sí, todo llegó bien**, **No, algo falló** (con el tipo y qué pasó) o **No recibiré mi pedido**. **Recibí mi pedido** solo se envía con «Sí, todo llegó bien» y el pedido queda **Entregada**. Si algo falló, el botón deja de decir eso, el pedido igual queda **Entregada** (o **Rechazada en recepción** si rechaza todas las unidades) y se crea un requerimiento ligado al pedido. **No recibiré mi pedido** abre el motivo (no había nadie, la dirección no coincide) y deja **Entrega no concretada**, también con su requerimiento; no confirma la entrega. Las dos acciones están en la página y en el diálogo de la campanita. **Cancelar** cierra el diálogo sin enviar. Al confirmar, la pantalla dice «Pedido entregado exitosamente». Si no quedan pedidos en camino ni en la puerta, el viaje pasa a fase `volviendo` (el regreso a la base lo sigue registrando el simulador).
6. **Sin respuesta.** Pasado `CONFIRMACION_AUTO_SEG` (120 s en la demostración; en la vida real serían horas) el pedido se da por **Entregada** con la marca «confirmada automáticamente».

El botón «Marcar entregado y cerrar despacho» queda solo como **corrección manual** para administrador y despachador.

## 2. Estados del pedido (RN-15)

| Orden | Estado | Final | Cómo se llega |
|---|---|---|---|
| 1 | Recibida | no | el cliente genera la orden |
| 2 | Confirmada | no | ventas |
| 3 | En preparación | no | ventas |
| 4 | Despachada | no | el despachador la asigna a un camión |
| 5 | Camión en la puerta | no | el simulador, al llegar a la dirección |
| 6 | Entregada | **sí** | el cliente acepta, o vence el plazo, o corrección manual |
| 7 | Entrega no concretada | no | el cliente informa que no pudo recibir |
| 8 | Cancelada | **sí** | cliente (solo «Recibida») o ventas (hasta «En preparación» o desde «Entrega no concretada») |
| 9 | Rechazada en recepción | **sí** | el cliente revisó y rechazó todas las unidades (RN-23, supuesto a validar con Cofrial) |

**Dos finales que se parecen y no son lo mismo.** «Entrega no concretada» dice que nadie pudo recibir: la mercadería no se revisó y se puede reprogramar. «Rechazada en recepción» dice que el cliente la revisó y no la aceptó: no se reprograma, no se factura y, si ya pagó, se le devuelve. Si necesita los productos, hace un pedido nuevo.

«Entrega no concretada» **no es final**: sale de ahí de dos maneras. (a) **Reprogramar:** el despachador la ve de nuevo en *Armar despacho* y la despacha en otro viaje; el pedido vuelve a **Despachada**, con otro despacho y sin la hora de puerta, y el motivo queda guardado como historial. (b) **Cancelar:** ventas la da de baja y el stock se repone. Mientras no esté en «Despachada», el simulador no la trata como una parada pendiente (solo visita pedidos «Despachada»).

## 3. Quién ejecuta el temporizador y por qué es seguro

El plazo vive en la base (`orden.puerta_en`), no en la memoria de ningún proceso. Lo evalúan **dos** lugares con la misma regla: cada vuelta del simulador (cada 5 s) y la web al leer pedidos (`ordenes_de`) o la flota. La sentencia es una sola `UPDATE` condicional sobre el estado:

```sql
UPDATE orden SET estado = 'Entregada', entrega_resuelta_en = now(), entrega_automatica = true
WHERE estado = 'Camión en la puerta' AND puerta_en <= now() - plazo
```

- **Reinicio del contenedor:** no se pierde nada; al volver, la próxima vuelta ve las órdenes vencidas y las cierra.
- **Doble ejecución** (varios contenedores, simulador y web a la vez): la segunda no encuentra filas en ese estado y no cambia nada.
- **El cliente decide entre medio:** si ya aceptó o rechazó, la orden no está en «Camión en la puerta» y la sentencia no la toca. Al revés, `resolver_entrega` solo actúa si la orden sigue en la puerta y toma el bloqueo de la fila antes de decidir.

## 4. Endpoints

Todos exigen sesión de cliente y devuelven 404 si la orden no es propia (una orden ajena se ve igual que una inexistente).

| Método y ruta | Qué hace |
|---|---|
| `GET /pedidos/<id>/entrega/` | JSON `{estado, puede_responder, puerta_en, se_confirma_sola_en_seg, resuelta_en, motivo, automatica, unidades_rechazadas}` |
| `GET /pedidos/<id>/entrega/?revision=1` | lo mismo más `revision` (`productos` con `producto_id`, `temperatura`, `problemas`, `efecto`) mientras se puede responder; es lo que arma el diálogo de revisión de la campanita |
| `POST /pedidos/<id>/entrega/` | `accion=aceptar` (con `resultado=bien` o `resultado=falla` más, por producto, `rechazo_<producto_id>` y `motivo_<producto_id>`, y `tipo_problema` y `problema`, al menos 5 caracteres si no rechaza unidades; sin `resultado` cuenta como «todo bien», por compatibilidad) o `accion=no_recibido` con `motivo` (obligatorio, al menos 5 caracteres). Con `X-Requested-With: fetch` o `Accept: application/json` responde `{ok, mensaje, entrega}` (400 si falla); sin esas cabeceras redirige al pedido con un mensaje |
| `GET /api/pedidos/<id>/seguimiento/` | `estado`, `mapa_en_vivo`, `mensaje` («Tu pedido aún no sale.» sin despacho), `entrega` y `seguimiento` (posición, temperatura, `ruta_url`, `llegada_en`, ETA). Con el mapa apagado, `lat`, `long` y `destino` van `null` |
| `GET /api/pedidos/<id>/ruta/` | `{puntos, parada, aproximada, km}`: **solo el tramo** desde la posición actual del camión hasta la parada de este pedido (`parada` es solo su `lat` y `long`). 404 si el pedido no va «Despachada» (en la puerta y después, el mapa ya no se pide) |
| `GET /api/avisos/` | campanita; tipos `puerta`, `llego`, `no_concretada` y `rechazada`. Los avisos `cerca` (con `minutos`) y `puerta` mientras espera respuesta traen `destacado: true` |
| `GET /pedidos/<id>/documentos/<doc>/` | boleta o factura de ese pedido. Con `?descarga=1` entrega el PDF |
| `GET /flota/despachar/ruta/?ordenes=1,2` | (despachador) vista previa de la ruta que quedará guardada |

**Qué ve cada cliente de la ruta.** El viaje guardado puede llevar a varios clientes, y la polilínea completa la ve el despachador. Al cliente `ruta_del_pedido` (`web/pedidos/servicios.py`) le entrega solo el tramo desde el camión hasta su parada: el filtro es del servidor, no del mapa, así que ni leyendo el JSON a mano aparecen la polilínea completa, las paradas de otros clientes ni los tramos de otras entregas. Si el camión todavía debe pasar por la casa de otro cliente antes de llegar a la de este, el trazo por calles delataría esa parada; en ese caso se entrega una línea recta aproximada (punteada en el mapa) entre el camión y esta dirección. Apenas el camión pasa esa parada, el tramo vuelve a ir por calles. El pedido que va primero siempre recibe el tramo por calles.

**Pantalla abierta al salir el camión.** Antes del despacho la página del pedido no trae el bloque de seguimiento. Esa pantalla consulta sola `/api/pedidos/<id>/seguimiento/` cada 5 segundos y, al pasar a «Despachada», se vuelve a dibujar: «Tu pedido va en camino», el mapa y la temperatura. No hace falta recargar a mano. En el catálogo y el resto de la tienda no corre esa consulta: la salida se avisa por la campanita.

**Aviso de llegada.** Que el camión esté cerca o haya llegado no depende de abrir la campanita. `campana.js` consulta `/api/avisos/` (cada 5 s mientras haya un aviso destacado, cada 15 s si no) y, en cualquier página del cliente, muestra un banner fijo arriba: «Tu pedido N.º X está por llegar» (a menos de 2 km, con los minutos estimados; se puede cerrar) y «El camión llegó con tu pedido» (con «Revisar y recibir»; no se cierra hasta responder). El texto ocupa su columna; los botones y la cruz van juntos, alineados al centro de la franja, y en una fila angosta bajan enteros debajo del texto. Además cambia el título de la pestaña, vibra una vez en los celulares y deja el aviso en la campanita. En esa lista, cada aviso es un solo bloque: si está sin leer, el verde cubre el texto y el botón. La acción es un botón holgado, con ícono y con un texto que dice a dónde lleva («Ver dónde va», «Ver boleta», «Revisar y recibir»). En la pantalla del propio pedido el banner no se repite: el estado del pedido pasa a «Tu pedido está por llegar» y se resalta.

**Un solo itinerario por pedido (COF-01).** `seguimiento.itinerario` dice en qué parada va este pedido y, si el camión pasa antes por otra entrega, lo explica: «Tu pedido es la parada 2 de 3. Antes pasamos por otra entrega…». Cuenta paradas, nunca nombre, dirección ni coordenadas de otro cliente; las «anteriores» son las paradas previas del viaje cuyos pedidos siguen «Despachada». Se muestra bajo el mapa del pedido.

**«Pedido entregado exitosamente» (COF-02).** Aparece solo cuando el cliente confirma, con todo bien o con algo que falló (y el reclamo para ventas): en el mensaje de la respuesta (JSON y redirección), en el título del estado del pedido junto a «Recorrido cerrado» y en el aviso «llegó» de la campanita. La confirmación automática por plazo también cierra el recorrido, pero dice «Pedido entregado» y «lo dimos por entregado», porque nadie confirmó. «No pude recibirlo» no es una entrega exitosa y no lo muestra. En la puerta, la pantalla dice «Tu paquete llegó» y aclara que aún no queda como entregado.

**Botones y datos de los avisos (COF-03).** Cada aviso de `/api/avisos/` trae `accion` (texto y pantalla a la que lleva) y `pedido` (estado, monto que paga el cliente —con IVA si es institucional— y su documento: factura o boleta si existe, si no la guía de despacho). Acciones: salió, ventana y cerca → «Ver dónde va» (`/pedidos/<id>/#seg`); «estamos afuera» → «Revisar y recibir» (abre la revisión) y «No pude recibirlo», los dos en la misma fila y más chicos que el resto de acciones de la campanita; llegó → «Ver boleta/factura» (`#documentos`) o «Ver pedido»; no concretada → «Escribir a ventas» y alerta de temperatura → «Reportar un problema» (`/soporte/?orden=<id>`). 

**Quién recibe.** El comprador elige en el carrito quién recibe el pedido (`orden.recibe_nombre`); la revisión al recibir lo muestra («Recibe: …») para que quien abre la puerta sepa a nombre de quién va. Detalle y reglas en `docs/decisiones.md`.

**Reclamo al recibir.** `resolver_entrega(..., con_problema=True, tipo_problema=...)`: el pedido queda «Entregada» (el camión sí entregó) y se crea un `requerimiento` con asunto «Problema al recibir el pedido N.º X: <tipo>», la descripción del cliente y el pedido ligado. Los tipos «Los productos llegaron tibios o descongelados» → categoría «Reclamo por temperatura»; «Faltan o sobran productos» y «Producto dañado o en mal estado» → «Problema en la entrega»; «Otro problema» lo clasifica la IA como cualquier consulta. No hay tablas ni campos nuevos.

**Recepción parcial (RN-23, supuesto a validar con Cofrial).** Con «No, algo falló», el paso de revisión pide por producto cuántas unidades rechaza y el motivo (`PROBLEMAS_AL_RECIBIR`: temperatura, faltante, dañado u otro). Se guarda por línea en `orden_item.cantidad_rechazada` y `motivo_rechazo`; `cantidad` no cambia. Los campos del formulario son `rechazo_<producto_id>` y `motivo_<producto_id>`, y el servicio los valida todos en la transacción que tiene bloqueada la orden: un producto ajeno, un número inválido, más de lo pedido o un motivo faltante no dejan nada a medias. El comentario solo es obligatorio si no rechaza unidades o elige «Otro problema». Si marcó «Sí, todo llegó bien», lo que hubiera en esos campos no cuenta.

| Caso | Estado | Documentos | Dinero |
|---|---|---|---|
| B2B, sin factura (lo normal) | Entregada | La factura se emite después, solo por lo aceptado | Lo rechazado nunca se cobra |
| B2B, con factura previa | Entregada | Nota de crédito por lo rechazado | Baja la deuda; si ya había pagado más que el nuevo total, se devuelve lo que sobra |
| B2C, boleta o factura pagada al comprar | Entregada | El documento no cambia (es una foto); nota de crédito por lo rechazado | Devolución: `pago` con monto negativo, medio `devolucion` y referencia `NC-<folio>` |
| Rechazo total B2B | Rechazada en recepción | Sin factura (no aparece en «entregadas sin factura») | Nada que cobrar |
| Rechazo total B2C | Rechazada en recepción | Nota de crédito por todo; la boleta queda anulada | Devolución de todo |
| Sin respuesta (`confirmar_vencidas`) | Entregada, automática | Pedido completo | El silencio no rechaza nada |

La nota de crédito sale de `documentos.rebajar_por_rechazo`. Su monto es la diferencia entre el total pedido y el total aceptado, ambos ya redondeados con IVA, para que documento menos nota dé lo mismo que una factura por lo aceptado. El tope es lo que el documento aún no tiene rebajado (notas anteriores del vendedor incluidas); si ya está rebajado entero, no se emite otra y el rechazo igual se registra. **Stock:** lo rechazado no se repone; bodega lo revisa y, si sirve, lo devuelve con «Reponer» en `/operacion/` (ver `docs/decisiones.md`). El reclamo (`requerimiento`) tiene asunto «Problema al recibir el pedido N.º X: Recepción parcial» o «Rechazo total»; su categoría sale de los motivos (la temperatura manda) y la ficha del cliente y el reclamo en el CRM muestran la tabla de lo rechazado. El prototipo registra la devolución en `pago`; no llama a la API de devoluciones de Mercado Pago.

**Comprobante (COF-04).** En el carrito el público elige boleta o factura. El RUT es el de la cuenta y la factura pide el giro si falta. Lo recibe pagado al comprar. La institución no elige: recibe factura a crédito después de la entrega, como hasta ahora, y el carrito le pide el giro si falta. En el pedido, «Ver boleta» o «Ver factura» y «Descargar PDF» abren el comprobante de venta. La guía queda en la tabla como documento que acompaña la entrega. La vista es una hoja blanca, con el logo de Cofrial, el folio, el RUT, los productos y el total. El PDF declara que es una simulación y no un DTE del SII.

**Visibilidad del mapa:** el cliente ve el mapa en vivo solo con el pedido «Despachada» y antes de que el camión registre la llegada a esa parada. Antes de salir ve «Tu pedido aún no sale». Con el camión en la puerta, la página dice que el pedido llegó a su destino: no dibuja el mapa, la ruta ni la última señal, tampoco al recargar, y deja la hora de llegada, quién recibe, la dirección y la temperatura como registro. Cuando el viaje de ese pedido ya terminó (entregado, rechazado en recepción o entrega no concretada) tampoco muestra el mapa ni el recuadro vacío: dice que el recorrido terminó y deja el registro de temperatura. «Pedido entregado exitosamente» solo aparece si el cliente confirmó la recepción.

**Aviso para quien despacha (antes de la salida).** El menú interno muestra junto a «Flota» cuántos pedidos esperan camión, en cualquier pantalla y sin recargar (`static/js/por-despachar.js`). Lo ven administrador, gerencia y despachador; ventas y los clientes no cargan el script y reciben 403 si piden la ruta. Cuenta lo mismo que «Armar despacho» (`pedidos_por_despachar()`), incluidas las entregas no concretadas que esperan reprogramarse. Al abrir el contador aparece el aviso de `sugerencias.py`: qué camión conviene o «sin camión libre de ese rango». El despachador y el administrador reciben además enlaces a «Armar despacho» con el camión y los pedidos marcados; gerencia solo recibe el enlace a Flota, porque consulta y no arma viajes. Nada sale hasta que una persona confirma.

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `GET /flota/por-despachar/` | admin, gerencia, despachador | JSON `{total}`: un solo `COUNT`, sin IA. El menú recibe este número con `/api/avisos-equipo/` |
| `GET /flota/por-despachar/?detalle=1` | los mismos | Agrega `texto` (plantilla del código, sin IA) y `acciones` (`texto`, `url`). Se pide solo al abrir el contador |

**Avisos en tiempo real por tipo de usuario.** El equipo tiene una campana en el menú (`static/js/avisos-equipo.js`, `GET /api/avisos-equipo/`, cada 15 s) y el cliente conserva la suya (`/api/avisos/`), que ahora también trae `stock_n`. Cuando un número sube aparecen un mensaje dentro de la página, el número en el título de la pestaña y, si la persona dio permiso, una notificación del navegador. Qué ve cada rol y por qué está en `docs/decisiones.md`.

**Capacidad del camión:** ni el despacho manual, ni las sugerencias, ni el modo automático limitan por kilos, porque los productos no tienen peso en la base. Qué faltaría y cómo afecta al modelo está en `docs/decisiones.md`.

**Camiones de dos cámaras.** Una parte de la flota (`CAM-05`, `CAM-14`, `CAM-23`, `CAM-32` y `CAM-41`) lleva refrigerado en la cámara 1 y congelado en la cámara 2. El carrito mixto sigue generando una orden por rango, pero ambas pueden salir en un solo viaje y con una sola parada. `despachar` guarda en `orden.camara` dónde viaja cada una. La sugerencia y el despacho automático juntan en un camión de dos cámaras las direcciones que esperan pedidos de ambos rangos, y para un solo rango prefieren un camión simple. El simulador envía una lectura por cámara: seguimiento, avisos, CRM y Grafana miran solo la cámara del pedido, mientras la flota muestra ambas y marca el camión en alerta si cualquiera lo está. En `/demo/` se elige qué cámara falla; los escenarios por viaje fallan en la cámara 1.

**Al desplegar:** primero la web, que migra la base; después el simulador, que debe reiniciarse para leer la segunda cámara.

## 5. Rutas por calles: decisiones y respaldo

- **Servidor, no navegador:** la ruta se pide a OSRM una vez, desde la web, y se guarda. Las pantallas no vuelven a pedirle nada.
- **Caché por secuencia de coordenadas** (`ruta_cache`): mismas paradas, misma ruta. Al sembrar, `cargar_demo` deja calculadas las rutas de los despachos de la demostración y la de cada dirección de cliente.
- **Respaldo:** tiempo de espera de 4 s y un reintento; si OSRM no responde, la ruta son rectas entre los puntos, marcada `aproximada` (línea punteada en el mapa), y el simulador avanza con el factor de calles de siempre. Nunca un error.
- **Diagnóstico de la ruta por el cerro Ñielol:** el camión se movía en línea recta mientras la web dibujaba la ruta por calles; la recta cruzaba el parque. Ahora ambos usan la misma polilínea.
- **Viajes anteriores a este cambio** (sin ruta guardada): la web la calcula una vez al consultarlos y la guarda; el simulador, hasta entonces, avanza en rectas.

## 6. Cambios al modelo de datos (para el MER y el diccionario)

Todos los atributos nuevos dependen solo de la clave de su tabla (3FN); no hay atributos derivados de otros no clave.

**`despacho`** (se agregan):

| Columna | Tipo | Nulo | Justificación |
|---|---|---|---|
| `regreso_en` | timestamptz | sí | cuándo el camión volvió a la base; define cuándo queda libre. Depende solo del despacho |
| `fase` | varchar(12), por defecto `en_ruta` | no | `en_ruta`, `en_la_puerta` o `volviendo`; la informa el simulador para mostrar la situación del camión sin deducirla de coordenadas |
| `ruta_geojson` | jsonb | sí | recorrido guardado: `puntos` [[lat, long]…] y `paradas` [{direccion_id, indice}] |
| `ruta_aproximada` | boolean, falso | no | verdadero si la ruta son rectas por falta de OSRM |

Restricción nueva: `regreso_requiere_llegada` (`regreso_en` solo si hay `llegada_en`). `llegada_en` cambia de significado: ahora es la llegada a la última parada, no el cierre. Los viajes ya cerrados reciben `regreso_en = llegada_en` en la migración. La **situación** de un camión («en base», «en ruta», «en la puerta», «volviendo») no se guarda: se deriva (sin despacho abierto = en base; con despacho, `fase`).

**`orden`** (se agregan): `puerta_en` timestamptz nulo (llegada del camión a esa dirección; inicia el plazo), `entrega_resuelta_en` timestamptz nulo, `entrega_motivo` text (vacío por defecto), `entrega_automatica` boolean (falso) y `comprobante` (`boleta` o `factura`, por defecto `boleta`; las órdenes institucionales ya existentes quedan en `factura`). Los cuatro primeros son hechos de una entrega de esa orden; se dejan en `orden` porque cada orden tiene a lo más una entrega vigente y se sobrescriben al reprogramar (el motivo se conserva como historial). `comprobante` es la elección de la compra y no cambia con la entrega.

**`estado_orden`** (datos): dos filas nuevas, «Camión en la puerta» y «Entrega no concretada», ambas con `es_final = false`; el flujo se renumera (Entregada pasa a 6 y Cancelada a 8). Con RN-23 se agrega «Rechazada en recepción» (9, `es_final = true`).

**`orden_item`** (se agregan, migración `pedidos/0011`): `cantidad_rechazada` integer, 0 por defecto, con CHECK entre 0 y `cantidad`, y `motivo_rechazo` varchar(12), vacío por defecto, con CHECK de que hay motivo si y solo si hay unidades rechazadas. Dependen de la clave completa de la línea (3FN). Lo aceptado no se guarda: es `cantidad - cantidad_rechazada`.

**`v_orden_total`**: `total_clp` y `unidades` pasan a contar solo lo aceptado y se agregan `rechazado_clp` y `unidades_rechazadas`. Sin rechazos da lo mismo de antes.

**`ruta_cache`** (tabla nueva): `clave` varchar(64) PK (SHA-256 de la secuencia de coordenadas), `ruta_geojson` jsonb, `km` double, `aproximada` boolean, `creada_en` timestamptz. Es una caché técnica sin relaciones; todo depende de la clave.

**`comuna`** (datos): `cargar_demo` siembra las 22 comunas principales de La Araucanía de forma idempotente. Antes solo existían Temuco y Villarrica, y por eso el formulario de registro solo las ofrecía.

## 7. Variables de entorno

| Variable | Dónde | Qué hace |
|---|---|---|
| `CONFIRMACION_AUTO_SEG` | web y simulador | plazo del cliente en la puerta (120 s) |
| `OSRM_URL` | web | servicio de rutas; vacío = rectas aproximadas |
| `OSRM_TIMEOUT_SEG` | web | tiempo de espera por intento (4 s) |
| `VELOCIDAD_MEDIA_KMH`, `FACTOR_CALLES` | web y simulador | velocidad compartida; el factor solo se aplica a rectas |
| `DETENCION_LECTURAS` | simulador | lecturas detenido en cada dirección |

## 8. Pruebas

`flota/tests_rutas.py`, `pedidos/tests_entrega.py` y `iot/test_simulador.py` cubren: ruta con y sin OSRM, caché y reintento; ciclo completo del camión con y sin ruta, ida, puerta, llegada, vuelta y regreso; guardado en base; estados, aceptación, rechazo con motivo y requerimiento ligado, plazo vencido, idempotencia y orden ajena; visibilidad del mapa por estado; reprogramación; situación de la flota y siembra de comunas.

`flota/tests_por_despachar.py` cubre el contador: sigue a los pedidos, cuenta lo mismo que «Armar despacho», una sola consulta sin IA, quién queda fuera, los enlaces por rol, «sin camión libre de ese rango» y el límite conocido de la capacidad.

`flota/tests_rutas.py`, `pedidos/tests_entrega.py`, `pedidos/tests_comprobante.py`, `pedidos/tests_recepcion_parcial.py` y `iot/test_simulador.py` cubren: ruta con y sin OSRM, caché y reintento; ciclo completo del camión con y sin ruta, ida, puerta, llegada, vuelta y regreso; guardado en base; estados, aceptación, rechazo con motivo y requerimiento ligado, plazo vencido, idempotencia y orden ajena; visibilidad del mapa por estado; reprogramación; situación de la flota y siembra de comunas.

`flota/tests_rutas.py`, `flota/tests_dos_camaras.py`, `pedidos/tests_entrega.py`, `pedidos/tests_comprobante.py`, `pedidos/tests_recepcion_parcial.py` y `iot/test_simulador.py` cubren: ruta con y sin OSRM, caché y reintento; ciclo completo del camión con y sin ruta, ida, puerta, llegada, vuelta y regreso; guardado en base; estados, aceptación, rechazo con motivo y requerimiento ligado, plazo vencido, idempotencia y orden ajena; visibilidad del mapa por estado; reprogramación; situación de la flota y siembra de comunas.

## 9. Escenarios de la demostración, sensores y revisión de camiones (13-nov-2026)

**Quién decide al recibir.** Ningún escenario responde por el cliente, salvo «Cliente no está». «Pedido bueno» (`entrega_perfecta`) ya no confirma solo: solo evita rupturas al azar; el cliente revisa y acepta o rechaza, o vence el plazo de siempre. Si el camión no tuvo problemas de frío (`temperatura.en_rango`), la revisión muestra solo «Recibí mi pedido» y un enlace «¿Algo no está bien? Reportar un problema» que abre las opciones de siempre; con un problema de temperatura registrado, las opciones se ven desde el principio.

**Escenarios** (`/demo/`, solo administrador): pedido bueno, ruptura de frío, cliente no está y dos trampas del sensor. Las trampas mueven lo que informa el sensor, no la carga:

| Tipo | Qué hace el sensor | Qué prueba |
|---|---|---|
| `sensor_falla` (falsa alarma) | Marca saltos de 9 a 14 °C sobre lo real y salta la alerta | La carga está bien: aceptarla es correcto (falso positivo) |
| `sensor_pegado` (falso «normal») | Queda clavado en un valor dentro del rango y nunca avisa | Si la carga llegó tibia, solo el cliente lo detecta al recibir |

**Diagnóstico de un camión** (`web/flota/diagnostico.py`, `GET /flota/camion/<id>/diagnostico/`): con las últimas 12 lecturas el código clasifica `ruptura` (sube de a poco), `sensor_alerta` (alerta con un salto de 6 °C o más entre dos lecturas), `sensor_pegado` (8 lecturas idénticas sin alerta) o `normal`. La IA gratuita solo redacta el texto (se descarta si nombra otro camión; no recibe clientes ni direcciones) y su texto se guarda 2 minutos para no gastar cuota.

**Revisión técnica** (`revision_camion`, migración `flota/0009`): `id`, `camion_id`, `motivo` (equipo de frío, sensor, otro), `nota`, `abierta_en/por`, `cerrada_en/por`. Una sola abierta por camión (índice único parcial). Un camión en revisión no se sugiere ni se despacha; sigue su viaje hasta volver a la base. Lo envían y devuelven el administrador y el despachador (`POST /flota/camion/<id>/revision/`, con confirmación); gerencia solo consulta. Se ofrece en el recuadro de diagnóstico de cada camión y desde el pin rojo del mapa («Qué hacer ›»).

**Otros cambios del mismo día.** La Torre de control (con la rúbrica) queda solo para el administrador y sin enlace para gerencia, que ahora inicia en el CRM. Las tablas con más de 10 filas se paginan en el navegador (`static/js/paginacion.js`: «Viendo 1–10 de N», Anterior, Siguiente, 10/25/50 filas). El filtro del catálogo permite marcar varias categorías y varios rangos (`?categoria=1&categoria=2`). El aviso de cookies se cierra con Escape o al enviar el ingreso.

## 10. Qué camión usar, viajes unidos y demostración lista (14-nov-2026)

- **¿Qué camión uso?** (`GET /flota/despachar/sugerir-camion/?ordenes=…`, `flota/sugerencias.py`): el código elige con reglas (el frío que exigen los productos, camión libre, sin ruptura ni revisión técnica, con lecturas recientes y combustible suficiente: ≥ 25 % y, en un viaje de 150 km o más de ida y vuelta, ≥ 50 %; los 150 km y el 50 % son supuestos del prototipo). Gana el de más combustible; para un solo rango se prefiere un camión simple. La IA solo redacta el porqué y su texto se descarta si nombra un camión que no corresponde. A la IA no llegan clientes ni direcciones.
- **Viajes unidos por camino:** `_agrupar_por_camino` parte por el pedido más lejano de la base y le suma los que quedan en su ruta (desvío ≤ 12 km, `DESVIO_MAX_KM`), hasta 6 paradas: un camión en vez de varios al mismo lado. Las coordenadas no salen del cálculo.
- **Enviar con un clic:** la sugerencia de Flota muestra cada viaje ya armado con «Enviar ahora» (confirma y despacha por `POST /flota/despachar/`) y «Revisar antes». Lo ven administrador y despachador; gerencia solo la sugerencia.
- **Pérdida de señal** (`sin_senal`, migración `flota/0010`): el camión sigue, mide bien y entrega, pero no envía lecturas durante 36 (≈ 3 min); Flota lo marca «Sin señal». No cambia la temperatura.
- **Demostración lista:** «Preparar la demostración» crea tres pedidos cercanos, los despacha en camiones sanos con «Pedido bueno» y deja tres camiones en reparación (se devuelven con «Borrar lo de la demostración»); «Pedido de prueba cercano» crea uno suelto.
