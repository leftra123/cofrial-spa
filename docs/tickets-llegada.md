# Tickets de llegada — seguimiento interno

Registro del equipo. No forma parte del informe. Fija qué se vio y qué quedó hecho.

Vistos el 08-nov-2026 en la tienda, con la cuenta de Sergio, pedidos en CAM-12 y CAM-17.

## Orden

| Orden | Ticket | Qué se vio |
|---|---|---|
| 1 | LLE-01 | Hecho. Con el viaje cerrado no hay última señal ni mapa apagado: la página dice que el recorrido terminó y deja el registro de temperatura. |
| 2 | LLE-02 | Hecho. «Ver dónde va» y la cruz van en la misma fila, alineados al centro del aviso. |
| 3 | LLE-03 | Hecho. En «Revisa tu pedido», «No recibiré mi pedido» pide el motivo y no confirma la entrega. «Recibí mi pedido» solo va con «Sí, todo llegó bien». |
| 4 | LLE-04 | Hecho. Con el camión en la puerta no hay mapa ni ruta, tampoco al recargar: la página dice que el pedido llegó a su destino. |
| 5 | LLE-05 | Hecho. El pedido entregado ofrece «Ver boleta» y «Descargar PDF». La vista es una hoja blanca con el logo. |
| 6 | LLE-06 | Hecho. En la campanita, «Ver dónde va» y el resto de acciones se ven como botón. |
| 7 | LLE-07 | Hecho. Con el pedido abierto, al salir el camión la pantalla pasa sola a «en camino». En las otras páginas solo avisa la campanita. |

## LLE-01 — Al llegar, cerrar la pantalla de seguimiento (hecho)

Cuando el camión ya llegó a la dirección, la página del pedido deja de ser un seguimiento.

Hoy, con el viaje terminado, `web/templates/pedidos/detalle.html` sigue armando la grilla `#seg`: «Salió», «Llega entre» y «Última señal». El mapa no se dibuja (`mapa_en_vivo` es falso fuera de «Despachada» y «Camión en la puerta», en `pedidos/servicios.py`), pero queda el recuadro «El mapa en vivo ya no está disponible». `entrega.js` del detalle sigue contando la última señal cada segundo.

- No se muestra «Última señal» ni el recuadro del mapa apagado.
- La pantalla dice que el pedido llegó a su destino y que el recorrido de ese pedido terminó.
- «Pedido entregado exitosamente» sigue reservado a la confirmación del cliente. La confirmación automática no usa esa frase: hoy eso ya está en el encabezado de «Entregada» (`detalle.html`).
- La temperatura del viaje puede quedar como registro, no como una señal en vivo.

## LLE-02 — Alinear el aviso «está por llegar» (hecho)

El banner verde de «Tu pedido N.º N está por llegar» tiene el texto, el botón y la cruz en la misma fila, y en la foto quedan a distintas alturas.

Lo arma `pintarBanner` en `web/static/js/campana.js`. El botón «Ver dónde va» es un enlace con clase `btn`. La cruz es `.al-cerrar`, absoluta arriba a la derecha. El estilo está en `web/static/css/tienda.css` (`.aviso-llegada-item`).

- El texto ocupa su columna y las acciones quedan alineadas entre sí, al centro de la franja.
- «Ver dónde va» se lee como botón. La cruz cierra solo ese aviso y no se monta sobre el botón.
- En una fila angosta, el botón baja completo debajo del texto, sin quedar cortado.
- El aviso de «el camión llegó» usa la misma alineación.

## LLE-03 — Poder decir que no se recibe el pedido (hecho)

En «Revisa tu pedido» el cliente elige si lo recibe. Hoy las dos opciones son radios («Sí, todo llegó bien» y «No, algo falló») y el único botón de envío dice «Recibí mi pedido». Elegir «no» no cambia ese botón. «No pude recibirlo» está escondido en un `<details>` de la página del pedido y no aparece en el diálogo de la campanita.

El diálogo lo construye `revisar()` en `web/static/js/entrega.js`. El formulario de la página está en `detalle.html`. El servidor ya distingue `accion=aceptar` y `accion=no_recibido` en `resolver_entrega`.

- Si el cliente marca que no lo recibe, el botón pasa a «No recibiré mi pedido» y no confirma la entrega.
- Esa acción abre el motivo (no había nadie, no coincide la dirección, o lo que ya pide el formulario) y deja el pedido en «Entrega no concretada».
- «Recibí mi pedido» solo se envía con «Sí, todo llegó bien».
- El mismo par de acciones se ve en la página del pedido y en el diálogo. «Cancelar» cierra sin enviar.

## LLE-04 — Al recargar, un pedido llegado no vuelve a mostrar el mapa (hecho)

Con el camión en la puerta, al recargar sigue el mapa, la ruta, «En vivo» y el paso «Camión en la puerta». El recuadro verde dice «Tu pedido llegó», pero la página no se ve como una entrega cerrada.

`mapa_en_vivo` incluye «Camión en la puerta», así que `seguimiento()` manda latitud, destino y `ruta_url`. El script de `detalle.html` crea el mapa en cuanto llega una lectura con coordenadas. El paso del encabezado solo dice «Pedido entregado exitosamente» cuando el estado ya es «Entregada».

- Si el camión ya registró la llegada a esta dirección, la página no dibuja el mapa ni la ruta, tampoco al recargar.
- El título de esa pantalla es que el pedido llegó a su destino. No pide una «última señal».
- Se mantienen la hora de llegada, quién recibe, la dirección y, si hace falta, la temperatura del viaje como dato cerrado.
- El mapa en vivo queda solo mientras el estado es «Despachada» y el camión todavía no llegó a esta parada.

## LLE-05 — Ver la boleta como documento (hecho)

Con el pedido entregado, «Documentos y pago» lista «Boleta N.º 4» y la guía, sin una hoja que se reconozca como boleta. El enlace «Ver» va pegado al nombre, dentro de la celda, y la guía no es el comprobante de venta.

La hoja ya existe: `web/templates/pedidos/comprobante.html` y el PDF de `pedidos/documentos.py`. La hoja es una tarjeta del sitio: no lleva el logo y el fondo sigue el tema. El PDF no incluye el logotipo.

- Desde el pedido entregado hay una acción clara «Ver boleta» y otra «Descargar PDF».
- La vista es una hoja blanca, con el logo de Cofrial, el folio, el RUT de la cuenta, los productos y el total.
- La guía sigue en la tabla como documento que acompaña la entrega, sin presentarse como boleta.
- El PDF declara que es una simulación y no un DTE del SII.

## LLE-06 — La acción de la campanita se ve y se entiende (hecho)

Dentro de la campanita, cada aviso trae un enlace secundario (clase `btn-sec`) con textos cortos: «Ver dónde va», «Ver pedido», «Ver factura». Sobre el fondo blanco del panel se ve como texto sin botón. No existe la cadena «Ver ahora» en el código; es esta acción la que se lee así.

La pinta `pintar()` en `campana.js`. El texto sale de `_accion_del_aviso` en `pedidos/servicios.py`.

- El control se ve como botón: fondo, borde, alto de toque e ícono de a dónde lleva.
- El aviso sin leer es un solo sector: el verde cubre el texto y el botón, no se corta donde empieza la acción.
- El texto dice a qué lleva: ver el recorrido, revisar y recibir, o ver la boleta. No un «ver ahora» suelto.
- Arriba del botón, el aviso ya dice de qué pedido se trata y qué pasó.

## LLE-07 — Al despachar, la pantalla del cliente pasa a «en camino» (hecho)

Cuando despacho arma el viaje y el camión sale, quien tiene abierto su pedido sigue viendo «en preparación» hasta que recarga a mano.

El script de `detalle.html` solo consulta `/api/pedidos/<id>/seguimiento/` si la página ya trajo el bloque `#seg`. Ese bloque no está antes de que exista el despacho (`seguimiento()` sale vacío). La campanita sí consulta `/api/avisos/` cada 15 segundos, pero no redibuja la página del pedido.

- Con el pedido abierto, al pasar a «Despachada» la página se vuelve a dibujar sola y muestra «Tu pedido va en camino», el mapa y la temperatura.
- No hace falta que la persona recargue.
- Si está en otra pantalla de la tienda, el aviso de salida sigue saliendo por la campanita; no se recarga una página que no es la del pedido.
