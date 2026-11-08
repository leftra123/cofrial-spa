# Tickets COF — seguimiento interno

Registro solo del equipo (Eric y Sergio). No forma parte del informe.

Hechos: COF-01, COF-02, COF-03, COF-04, COF-06 y COF-07. Sigue COF-05, que puede usar los documentos que COF-04 ya asocia al pedido.

Supuesto para empezar COF-01: un camión puede llevar varios pedidos en una sola ruta (así está armado el despacho hoy). Si se decide un viaje por pedido, COF-01 y COF-02 cambian de alcance.

## Integración con `main` (8-nov-2026)

COF-01, COF-02 y COF-03 se hicieron dos veces, en paralelo. Al integrar la PR #75 quedó esto:

- COF-01: queda la versión de `main`. El filtro de la ruta es del servidor y el cliente no recibe coordenadas ni trazado de otras paradas. De la PR queda el orden de las paradas en la flota.
- COF-02: queda la revisión al recibir de `main`, con el título «Tu paquete llegó» y el cierre del viaje de la PR. La confirmación automática no dice «exitosamente». El mapa y la temperatura siguen visibles en la puerta y después de la entrega.
- COF-03: queda la versión de `main` (`accion` y `pedido` en cada aviso).
- COF-04: la institución no elige boleta; recibe factura a crédito. El público elige.
- COF-06 y COF-07: entran como estaban.

Las secciones de abajo son el registro original de la PR; donde difieran, manda esta lista.

## Orden de trabajo

| Orden | Ticket | Importancia | Estado | Por qué va aquí |
|---|---|---|---|---|
| 1 | COF-01 | Alta | Hecho | El mapa del pedido muestra solo el tramo hasta su parada, con las paradas en orden. Probado con dos pedidos en el mismo camión. |
| 2 | COF-02 | Alta | Hecho | Al llegar, la pantalla muestra el paquete. «Pedido entregado exitosamente» aparece al confirmar, y el viaje se cierra si no quedan paradas. |
| 3 | COF-03 | Alta | Hecho | Cada botón del aviso actúa sobre ese pedido y ese momento. La boleta o factura se nombra si ya existe. El archivo para abrirla queda en COF-04. |
| 4 | COF-07 | Media | Hecho | Cada sección muestra solo su propio esqueleto. La página anterior se oculta; no se funde con la que entra. |
| 5 | COF-06 | Baja | Hecho | Salir pregunta antes. Cancelar deja la sesión abierta. Confirmar cierra y vuelve a ingresar. |
| 6 | COF-04 | Alta | Hecho | En el carrito se elige boleta o factura. El RUT es el de la cuenta. La factura pide el giro. El PDF se descarga desde el pedido. |
| 7 | COF-05 | Media, bloqueado | Pendiente, depende de COF-04 | La sección «Documentos de pago» muestra lo que COF-04 haya emitido y asociado al pedido. |

## Qué pide cada uno y qué hay hoy

### COF-01 — Mostrar un único recorrido claro para cada pedido

Hecho. Probado con dos pedidos en el mismo camión: una sola línea en el mapa, la lista en orden y el texto que explica la parada anterior.

- El mapa del cliente dibuja un solo tramo: hasta su parada, sin la vuelta a la bodega ni las paradas posteriores. Desde la posición del camión, la línea sigue ese tramo.
- Las paradas salen en el orden del viaje. La suya dice «Tu entrega» y la dirección. Las otras dicen «Otro pedido» o «Tu otro pedido», sin nombre ni calle ajena.
- Si hay una parada pendiente antes, el texto explica que se atiende primero porque queda antes en el recorrido desde la bodega.
- En la flota, los pedidos del viaje quedan en ese mismo orden y el destino de la tarjeta es la próxima parada. El mapa del conductor sigue mostrando la vuelta completa: es el recorrido del camión, no un segundo camino para el cliente.

Supuesto que quedó en el código: un camión puede llevar varios pedidos en la misma ruta.

- Cada pedido muestra un solo recorrido activo.
- Las paradas aparecen en el orden en que se realizarán.
- Si se atiende primero otro pedido, se explica qué ocurrirá y por qué.
- La ruta y el estado del pedido coinciden para el cliente y el conductor.

### COF-02 — Confirmar la entrega y completar el recorrido

Hecho.

- Con el camión en la puerta, la pantalla es «Tu paquete llegó»: dirección, hora, camión y temperatura. Se quitan el mapa, la hora estimada y el itinerario de un viaje que ya llegó.
- «Pedido entregado exitosamente» aparece solo después de «Recibí mi pedido». La confirmación automática no usa esa frase.
- Si no quedan pedidos en camino ni en la puerta, el despacho pasa a `volviendo`. Si queda otra parada, el viaje sigue y la pantalla lo dice.
- El regreso a la bodega lo sigue registrando el simulador.

- La entrega queda registrada para el pedido correcto.
- La pantalla pasa a «Pedido entregado exitosamente».
- El recorrido queda marcado como finalizado.
- No se muestra la entrega como exitosa antes de confirmar que ocurrió.

### COF-03 — Corregir las acciones y la información de los avisos

Hecho, salvo abrir o descargar el archivo: eso queda en COF-04, cuando el documento se pueda emitir a elección.

- «Recibí mi pedido» y «No pude recibirlo» salen solo en el aviso del pedido que está en la puerta, y envían la respuesta de ese número.
- El aviso de salida, de llegada o de temperatura no trae esos botones.
- Si la entrega no se concretó, el botón es «Escribir a ventas» de ese pedido.
- Si el pedido ya tiene boleta o factura, el aviso y el detalle dicen cuál es y llevan a «Documentos y pago» de esa orden. La guía no se presenta como factura. Si la factura institucional todavía no existe, el detalle lo dice.
- No hay un botón de descarga: el archivo aún no existe.

### COF-07 — Ordenar la carga y animación entre el carro y «Mis compras»

Hecho. En la barra, «Mis compras» es «Mis pedidos» (`/pedidos/`).

- El carro no muestra el esqueleto de carga del catálogo. Cada destino usa el suyo: pestañas en Mis pedidos, líneas del carro en el carrito y tarjetas solo en el catálogo.
- Mientras llega la página, se ve ese esqueleto. Si ya está en caché, entra el contenido. La página que se deja queda oculta, con su alto, y no se transparenta encima de la otra.
- Un documento guardado que no corresponde al destino se pide de nuevo.
- La carga, el contenido y el vacío se distinguen: el esqueleto no tiene el texto de la sección, y «Aún no tienes pedidos» reemplaza al esqueleto cuando la lista llega vacía.

### COF-06 — Confirmar antes de cerrar sesión

Hecho. El botón de la tienda abre un diálogo. Sin JavaScript, el mismo botón sigue enviando el formulario.

- «¿Salir de la cuenta?» pregunta antes de cerrar la sesión.
- «Cancelar», Escape o un clic fuera cierran el diálogo y la sesión sigue abierta.
- «Confirmar» envía el formulario a `/cuenta/salir/` y lleva a `/cuenta/entrar/`. Un `next` externo no sale del sitio.
- El panel interno no usa este diálogo: su enlace sigue cerrando hacia la portada.

### COF-04 — Permitir elegir boleta o factura para el pedido

Hecho, con esta regla mientras Cofrial o la asesoría no indiquen otra:

- El RUT es el de la cuenta. No se pide uno distinto ni se reemplaza en la compra.
- La boleta usa el nombre y ese RUT. No pide más datos.
- La factura pide el giro si la cuenta no lo tiene, y lo guarda. La razón social es el nombre de la cuenta y la dirección es la de entrega.
- El público que elige factura la recibe pagada al comprar. La institución que elige factura la recibe después de la entrega, como hasta ahora. Si elige boleta, la boleta queda emitida al generar la orden.
- Desde el pedido se abre el documento y se descarga el PDF. El archivo dice que es una simulación y no un DTE del SII.

- La selección de boleta o factura queda asociada al pedido.
- La aplicación solicita los datos necesarios según la opción elegida.
- El documento emitido se puede consultar o descargar desde el pedido.
- El equipo valida con Cofrial o su asesoría contable los datos tributarios que deben solicitarse y cómo tratarlos.

### COF-05 — Mostrar los documentos emitidos en «Documentos de pago»

Pendiente. No se empieza hasta cerrar COF-04.

- Se muestran los documentos asociados al usuario y a sus pedidos.
- Cada documento indica a qué pedido pertenece y si es boleta o factura.
- El usuario puede abrirlo o descargarlo.
- Si todavía no se ha emitido, se informa su estado sin presentarlo como disponible.

Hoy el cliente ve documentos solo dentro de cada orden, en «Documentos y pago». El listado por cliente existe para el CRM, no para esta sección.

## Hecho

- COF-01. Visto en el pedido que va segundo: una línea hasta su dirección, «Otro pedido» en la parada 1 y la explicación de por qué se atiende antes.
- COF-02. Paquete llegado al estar el camión en la puerta. Entrega exitosa solo al confirmar. El viaje se cierra cuando no quedan paradas.
- COF-03. Los botones del aviso son del pedido que está en la puerta. La boleta o factura se nombra si ya existe.
- COF-04. En el carrito se elige boleta o factura. El RUT es el de la cuenta. El PDF se descarga desde el pedido.
- COF-07. Del carrito a Mis pedidos se ve el esqueleto de pedidos, no el del catálogo. El carrito y el catálogo hacen lo mismo con el suyo. La página anterior queda oculta.
- COF-06. Salir pregunta. Cancelar deja la sesión. Confirmar vuelve a la pantalla para ingresar.
