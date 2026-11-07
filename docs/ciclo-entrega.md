# Ciclo de entrega: de la salida del camión a la confirmación del cliente

Este documento describe cómo funciona hoy el reparto, para el informe y para quien construya pantallas encima. No contiene claves.

## 1. Qué pasa, paso a paso

1. **Despachar.** El despachador elige camión y pedidos. El servidor calcula **una vez** la ruta por calles con OSRM (perfil *driving*): base, paradas (la más cercana primero) y vuelta a la base. La polilínea queda guardada en el despacho y es la que dibujan el mapa del despachador y el simulador; el cliente recibe solo su tramo (ver «Qué ve cada cliente de la ruta»). Los pedidos pasan a **Despachada**.
2. **En ruta.** El simulador mueve cada camión *a lo largo de esa polilínea*, una lectura de telemetría cada 5 s. El camión y la ruta del mapa coinciden, y la hora estimada de llegada se calcula con los km que faltan por esa ruta.
3. **En la puerta.** Al llegar a la dirección de un pedido, el simulador pasa el pedido a **Camión en la puerta** y empieza a correr el plazo del cliente. El camión espera unas lecturas y sigue a la próxima parada.
4. **Última parada.** El simulador registra `despacho.llegada_en` y el camión **vuelve a la base** por la ruta de regreso. Al llegar registra `despacho.regreso_en`: recién ahí el camión queda libre para otro despacho. Sin despacho, el camión está **en base**, detenido en su puesto, enviando telemetría.
5. **El cliente revisa y responde** (banner, campanita y pantalla del pedido). Primero ve el paso de revisión: los productos con sus cantidades y la temperatura del viaje, y elige **Sí, todo llegó bien** o **No, algo falló** (con el tipo y qué pasó). Con **Recibí mi pedido** el pedido queda **Entregada**; si algo falló, además se crea un requerimiento ligado al pedido (el reclamo) que ventas ve en el CRM. Con **No pude recibirlo** y el motivo queda **Entrega no concretada**, también con su requerimiento.
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
| `GET /pedidos/<id>/entrega/` | JSON `{estado, puede_responder, puerta_en, se_confirma_sola_en_seg, resuelta_en, motivo, automatica}` |
| `GET /pedidos/<id>/entrega/?revision=1` | lo mismo más `revision` (`productos`, `temperatura`, `problemas`) mientras se puede responder; es lo que arma el diálogo de revisión de la campanita |
| `POST /pedidos/<id>/entrega/` | `accion=aceptar` (con `resultado=bien` o `resultado=falla` más `tipo_problema` y `problema`, al menos 5 caracteres; sin `resultado` cuenta como «todo bien», por compatibilidad) o `accion=no_recibido` con `motivo` (obligatorio, al menos 5 caracteres). Con `X-Requested-With: fetch` o `Accept: application/json` responde `{ok, mensaje, entrega}` (400 si falla); sin esas cabeceras redirige al pedido con un mensaje |
| `GET /api/pedidos/<id>/seguimiento/` | `estado`, `mapa_en_vivo`, `mensaje` («Tu pedido aún no sale.» sin despacho), `entrega` y `seguimiento` (posición, temperatura, `ruta_url`, `llegada_en`, ETA). Con el mapa apagado, `lat`, `long` y `destino` van `null` |
| `GET /api/pedidos/<id>/ruta/` | `{puntos, parada, aproximada, km}`: **solo el tramo** desde la posición actual del camión hasta la parada de este pedido (`parada` es solo su `lat` y `long`). 404 si el pedido no está «Despachada» ni «Camión en la puerta» |
| `GET /api/avisos/` | campanita; tipos `puerta`, `llego` y `no_concretada`. Los avisos `cerca` (con `minutos`) y `puerta` mientras espera respuesta traen `destacado: true` |
| `GET /flota/despachar/ruta/?ordenes=1,2` | (despachador) vista previa de la ruta que quedará guardada |

**Qué ve cada cliente de la ruta.** El viaje guardado puede llevar a varios clientes, y la polilínea completa la ve el despachador. Al cliente `ruta_del_pedido` (`web/pedidos/servicios.py`) le entrega solo el tramo desde el camión hasta su parada: el filtro es del servidor, no del mapa, así que ni leyendo el JSON a mano aparecen la polilínea completa, las paradas de otros clientes ni los tramos de otras entregas. Si el camión todavía debe pasar por la casa de otro cliente antes de llegar a la de este, el trazo por calles delataría esa parada; en ese caso se entrega una línea recta aproximada (punteada en el mapa) entre el camión y esta dirección. Apenas el camión pasa esa parada, el tramo vuelve a ir por calles. El pedido que va primero siempre recibe el tramo por calles.

**Aviso de llegada.** Que el camión esté cerca o haya llegado no depende de abrir la campanita. `campana.js` consulta `/api/avisos/` (cada 5 s mientras haya un aviso destacado, cada 15 s si no) y, en cualquier página del cliente, muestra un banner fijo arriba: «Tu pedido N.º X está por llegar» (a menos de 2 km, con los minutos estimados; se puede cerrar) y «El camión llegó con tu pedido» (con «Revisar y recibir»; no se cierra hasta responder). Además cambia el título de la pestaña, vibra una vez en los celulares y deja el aviso en la campanita. En la pantalla del propio pedido el banner no se repite: el estado del pedido pasa a «Tu pedido está por llegar» y se resalta.

**Quién recibe.** El comprador elige en el carrito quién recibe el pedido (`orden.recibe_nombre`); la revisión al recibir lo muestra («Recibe: …») para que quien abre la puerta sepa a nombre de quién va. Detalle y reglas en `docs/decisiones.md`.

**Reclamo al recibir.** `resolver_entrega(..., con_problema=True, tipo_problema=...)`: el pedido queda «Entregada» (el camión sí entregó) y se crea un `requerimiento` con asunto «Problema al recibir el pedido N.º X: <tipo>», la descripción del cliente y el pedido ligado. Los tipos «Los productos llegaron tibios o descongelados» → categoría «Reclamo por temperatura»; «Faltan o sobran productos» y «Producto dañado o en mal estado» → «Problema en la entrega»; «Otro problema» lo clasifica la IA como cualquier consulta. No hay tablas ni campos nuevos.

**Visibilidad del mapa (RN-16):** el cliente ve el mapa en vivo solo con el pedido «Despachada» o «Camión en la puerta». Antes de salir ve «Tu pedido aún no sale»; al terminar ve el resumen de temperatura sin mapa.

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

**`orden`** (se agregan): `puerta_en` timestamptz nulo (llegada del camión a esa dirección; inicia el plazo), `entrega_resuelta_en` timestamptz nulo, `entrega_motivo` text (vacío por defecto) y `entrega_automatica` boolean (falso). Son hechos de una entrega de esa orden; se dejan en `orden` porque cada orden tiene a lo más una entrega vigente y se sobrescriben al reprogramar (el motivo se conserva como historial).

**`estado_orden`** (datos): dos filas nuevas, «Camión en la puerta» y «Entrega no concretada», ambas con `es_final = false`; el flujo se renumera (Entregada pasa a 6 y Cancelada a 8).

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
