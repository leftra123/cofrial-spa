# Revisión en navegador: visitante, cliente particular (B2C) y cliente institucional (B2B)

> Hecha el 6-nov-2026, sobre `main` en 2d610d2 (PR #66 incluido). Es la misma revisión que se hizo con la cuenta B2B de Felipe, ahora con los tres tipos de cliente. La encargó Eric porque esa revisión encontró fallos que las pruebas automáticas no veían: clics perdidos entre pestañas y la raya del menú en la pestaña equivocada. Los roles internos (vendedor, gerencia, despacho, admin) los revisa otra sesión; `web/flota/` e `iot/` no se tocaron.

## Cómo se probó

- **Stack local aislado** (`cofrial-clientes`, web en el 8062, base en el 5462, claves generadas solo para esta prueba, `.env` fuera de git). Corrían la base, la web y 10 camiones simulados (CAM-01 a CAM-10) a 120 km/h, sin claves de IA y con rutas rectas (`OSRM_URL` vacío).
- **Navegador del panel de Claude** (Chromium), escritorio 1280 px y móvil 375 px, tema claro y oscuro. Se manejó con clics reales, doble clic, escritura y, para las carreras, con scripts que disparan clics cada 30 a 60 ms.
- **Truco que costó un falso positivo:** las cookies de `localhost` no distinguen el puerto. Con otros stacks locales abiertos en el mismo navegador, el primer envío del registro dio «403 formulario vencido». Se descartó como falla de la aplicación: con una dirección propia (`clientes.localhost:8062`) el mismo formulario funcionó. Para ensayar la defensa con varios stacks, usar un nombre de host distinto por stack.
- Las entregas se armaron con `flota.servicios.despachar` desde la consola de Django, porque despachar es del rol de despacho y esta revisión es de clientes. Todo lo que el cliente ve y hace, se hizo en el navegador.
- Cuentas: las del stack local (`felipe@cofrial.cl`, `ana@correo.test`, `sergio@cofrial.cl`), más tres creadas en la prueba por la propia pantalla: una cliente particular (registro con «Precargar datos de ejemplo»), una empresa pendiente y una recuperación de clave.

## Qué se recorrió

✓ = visto y bien. **C-nn** = falla corregida (sección siguiente). **A-nn** = falla o duda abierta.

| Pantalla | Visitante | Particular (B2C) | Institucional (B2B) |
|---|---|---|---|
| Portada | ✓ escritorio claro y oscuro, móvil oscuro | – | – |
| Registro particular | ✓ con campos inválidos y doble clic: una sola cuenta | – | – |
| Pedir cuenta de empresa | ✓ doble clic: una solicitud; **C-03** al recargar | – | – |
| Ingreso, clave mala, recuperar clave | ✓ mensaje claro; enlace de un solo uso; clave común y claves distintas rechazadas | ✓ | ✓ |
| Catálogo y filtros | ✓ tres clics seguidos de categoría: queda el último; recuerda los filtros con aviso | ✓ | ✓ precio institucional (neto) y «Repetir mi último pedido» |
| Detalle de producto | ✓ claro, escritorio | ✓ escritorio oscuro; la pestaña Catálogo queda marcada | – |
| Carrito | – (pide ingresar) | ✓ **C-01**, **C-04** | ✓ mezcla de rangos avisa que se parte en 2 pedidos |
| Quién recibe | – | ✓ lista propia y nombre nuevo | ✓ rechaza `<b>…</b>`, acepta apóstrofo y tilde; **A-02** |
| Compra | – | ✓ Webpay simulado, doble clic: una orden, un descuento | ✓ con OC, doble clic: dos órdenes (una por rango), sin duplicar |
| Mis pedidos | – | ✓ filtros por pestaña con clics seguidos; **C-01** | ✓ |
| Seguimiento (mapa, temperatura) | – | ✓ mapa con teselas, ruta propia, gráfica | – (sus pedidos no se despacharon; la API se probó con cuentas B2C) |
| Aviso de llegada y revisión al recibir | – | ✓ banner en cualquier página, cerrable, móvil | – |
| Recibí mi pedido / no pude recibirlo | – | ✓ doble clic: un solo registro; reenvíos tardíos no cambian nada | – |
| Cancelar orden | – | – | ✓ pide confirmar; doble clic: se repone una vez |
| Agregar OC a una orden pendiente | – | – | ✓ una vez puesta no se cambia; **A-03** |
| Soporte y asistente | – | ✓ doble clic y doble Enter: un solo mensaje; sin IA responde «no disponible» | – |
| Avisarme (sin stock) | – | ✓ doble clic: un solo aviso | – |
| Mi clave y salir | – | ✓ salir y «atrás» no deja ver nada privado; Mi clave se vio, sin cambiarla | – |
| Menú: raya y pestañas | ✓ | ✓ clics rápidos, atrás y adelante: URL, pestaña y raya siempre coinciden | ✓ |

Cobertura de combinaciones (no se probó todo en todo):

| | Escritorio oscuro | Escritorio claro | Móvil oscuro | Móvil claro |
|---|---|---|---|---|
| Visitante | portada, catálogo, filtros | portada, detalle, pedir empresa | portada, catálogo, ingreso, registro | no |
| Particular | catálogo, carrito, pedido, soporte, asistente | pedido, clave | no | catálogo, banner, pedido en puerta, soporte, carrito |
| Institucional | no | catálogo, carrito, pedido | no | catálogo, pedidos, detalle, carrito |

## Encontrado y corregido

Cuatro commits chicos en esta rama. Las correcciones de JavaScript y de plantilla no tienen prueba automática posible en Django; la de la cuenta de empresa y la del carrito sí la tienen.

### C-01. Con la sesión vencida, el login quedaba dentro de la tienda (media-alta) — `2ac92bf`

- **Pasos:** ingresar como cliente, esperar a que la sesión venza (se probó borrándola en el servidor), y pulsar la pestaña «Mis pedidos». Lo mismo con «Actualizar» en el carrito.
- **Esperado:** ir a «Ingresar» y volver al pedido después, como pasa al escribir la dirección a mano.
- **Real:** la navegación por pestañas pedía la página con `fetch`, recibía el login (un 200 tras redirigir) y lo pintaba dentro de la tienda: formulario de ingreso con el menú de cliente, el nombre del usuario, el botón «Salir», la dirección `/pedidos/` y el formulario con `action` vacío. Enviarlo mandaba la clave a `/pedidos/`, que redirigía al login otra vez: la persona escribía su clave y volvía a ver el formulario vacío.
- **Arreglo:** `nav-slide.js` y `tienda.js` detectan que la respuesta terminó en `/cuenta/entrar/` y navegan de verdad a esa dirección. Verificado en el navegador: queda el login real, con `next` correcto y el menú de visitante.

### C-02. En móvil de 375 px, «Carrito» y su contador quedaban cortados (media) — `df4f717`, `2bf6a57`

- **Pasos:** abrir el catálogo o el carrito con un teléfono de 375 px.
- **Esperado:** ver las cuatro pestañas y el contador del carrito; en el carrito, la pestaña activa visible.
- **Real:** el menú se desliza de lado y mostraba «Carri» detrás del borde difuminado. En `/carrito/` la pestaña activa quedaba medio escondida y el contador, fuera de la vista.
- **Arreglo:** la pestaña elegida se trae a la vista al marcarla (la raya se mide después de mover el menú) y, bajo 480 px, el menú tiene menos relleno: caben los cuatro enlaces con el contador. Verificado: con 3 productos, `scrollWidth` = `clientWidth` y la raya sigue alineada con la pestaña tras clics rápidos.

### C-03. Recargar la confirmación de «Pedir cuenta de empresa» mostraba errores (media-baja) — `38ddd77`

- **Pasos:** enviar la solicitud de empresa y recargar la página de confirmación.
- **Esperado:** seguir viendo «Solicitud enviada».
- **Real:** la confirmación era la respuesta del POST. Al recargar, el navegador reenvía el formulario y salía «Ya existe una cuenta con ese RUT» y «Ya existe una cuenta con ese correo», justo después de que la solicitud sí se había enviado.
- **Arreglo:** el POST redirige a `/cuenta/registro/empresa/?enviado=1` y esa misma vista muestra la confirmación leyendo la solicitud de la sesión (sin ruta nueva, para no tocar las matrices de rutas). Sin solicitud en la sesión vuelve al formulario. Dos pruebas nuevas en `cofrial/tests_cuentas.py`.

### C-04. Un producto retirado decía «Solo quedan 5» en el carrito (baja) — `d70c7d6`

- **Pasos:** dejar un producto en el carrito, retirarlo del catálogo (con stock 5) y abrir el carrito.
- **Esperado:** que diga que ya no está disponible.
- **Real:** el botón de comprar quedaba bloqueado (bien), pero la etiqueta decía «Solo quedan 5», y la compra se rechazaba sin que se entendiera por qué.
- **Arreglo:** la etiqueta dice «Ya no está disponible». Prueba ampliada en `pedidos/tests_casos_compra.py`.

## Encontrado y abierto

| # | Qué | Gravedad | Notas |
|---|---|---|---|
| A-01 | Las cookies de `localhost` se comparten entre puertos, así que dos stacks locales en el mismo navegador se pisan (403 de formulario vencido, sesiones que desaparecen) | Baja, solo local | No afecta a AWS, que es un solo host. Para ensayar con varios stacks, usar hosts distintos (`algo.localhost`) |
| A-02 | Si la compra falla por el nombre de quien recibe, el formulario vuelve sin el número de OC ni el nombre que se había escrito | Baja | El carrito se recarga con la redirección y no conserva lo tecleado |
| A-03 | El número de OC acepta cualquier carácter (`OC-777 <b>` se guardó) | Baja | Se muestra escapado, no hay inyección. «Quién recibe» sí valida letras; el OC no |
| A-04 | Una pestaña abierta sigue mostrando datos del cliente después de cerrar sesión en otra | Baja | Los sondeos reciben 403 y se detienen; al navegar se pide ingresar (C-01). Los datos ya pintados quedan a la vista |
| A-05 | Al recuperar la clave, el error «demasiado común» sale bajo el campo de confirmación | Muy baja | Solo la etiqueta |
| A-06 | Dos clics seguidos en «Agregar» del mismo producto suman una unidad: el botón se bloquea mientras llega la respuesta | Decisión | Evita duplicar con el doble clic. Quien quiera dos usa el selector de cantidad |
| A-07 | «Llega entre 23:40 y 00:00» con salida a las 23:45 | Solo con la demo rápida | La ventana de llegada se calcula con la velocidad de la web (50 km/h) y el simulador va a 120. No pasa con `VELOCIDAD_MEDIA_KMH=50` |
| A-08 | La consola del navegador registra un 404 de `/api/pedidos/N/ruta/` en pedidos ya entregados | Muy baja | La pantalla explica «El mapa en vivo ya no está disponible» |
| A-09 | El botón «Precargar datos de ejemplo» pone siempre la misma clave, que está escrita en `web/static/js/precarga.js` (público) | Decisión documentada (`docs/decisiones.md`) | Quien se registre así tiene una clave conocida. `REGISTRO_PRECARGA=0` lo oculta; conviene apagarlo si el sitio queda abierto después de la defensa |

## Suite

Imagen reconstruida con `docker build -t cofrial-clientes-web ./web` y `docker compose run --rm -e DEMO_PASSWORD= -e ADMIN_PASSWORD= web python manage.py test --noinput`: **674 pruebas, 9 saltadas (las de `@abierto` y las que dependen de servicios externos), 1 falla de entorno**. La falla es `cofrial.tests.VelocidadCompartidaWebTests.test_valores_por_defecto`: espera `VELOCIDAD_MEDIA_KMH` sin definir y este stack local la tenía en 120 para la demostración. Con `-e VELOCIDAD_MEDIA_KMH=` el módulo `cofrial.tests` pasa completo (9 de 9). Hay que correr la suite con esa variable vacía o con el `.env` por defecto.

## Filas de la matriz repetidas

De `docs/matriz-casos-de-uso.md` («Qué repetir después de fusionar»), las que tocan a estos usuarios. Todas con el stack local ya integrado.

| Fila | Resultado | Cómo |
|---|---|---|
| CU-01 | ✓ | Registro particular, solicitud de empresa e ingreso de las cuentas de cliente caen en el catálogo; empresa sin aprobar explica que espera |
| CU-02 | ✓ | El mismo producto (merluza) cuesta $29.990 al particular y $24.990 neto al institucional; filtros con texto, números y valores basura dan 200 |
| CU-05 | ✓ | Mapa con teselas, temperatura y ruta; el cliente ve su destino y su tramo. Con un tercero: 404 en seguimiento, ruta y pedido |
| RN-02, E-02 | ✓ | Dos clientes confirman a la vez el último producto: una orden (N.º 12), stock 0 y el otro vuelve al carrito |
| E-06 | ✓ **más C-04** | Producto retirado con carrito armado: la compra se rechaza; ahora la etiqueta lo dice bien |
| E-08 | ✓ | Dos clientes en un viaje: cada uno ve solo su destino y su ruta; el pedido del otro da 404 |
| E-09 | ✓ **cerrado en la vista del cliente** | Se insertó una lectura con ruptura después de la entrega de un pedido ya recibido: el aviso de variación queda oculto y la API da `hubo_ruptura: false`. Con el pedido en ruta, la gráfica y el aviso sí lo muestran. La matriz lo daba por abierto |
| E-15 | ✓ | Un pedido en la puerta sin respuesta pasó solo a «Entregada» a los 2 min (`entrega_automatica`) |
| E-16 | ✓ | Empresa sin aprobar: «aún no está activa» solo con la clave correcta |
| E-18 | ✓ | Diez claves malas bloquean solo a esa cuenta (429); otra cuenta entra sin problema |
| E-33, E-11, RN-13 | No repetidos aquí | Dependen de reprogramar entregas y de forzar rupturas durante el viaje: son del recorrido de despacho |

También se probaron, aunque la matriz no las pedía: cancelar con doble clic (repone una vez), «Repetir mi último pedido» con doble clic (no duplica cantidades), agregar una dirección con doble clic (una sola), reenviar a mano la confirmación o el reclamo de un pedido ya entregado (el estado no cambia y no se crea reclamo), `?orden=` con valores basura en Soporte (200, sin traza), y el reclamo de «no pude recibirlo» (un solo requerimiento aunque se haga doble clic).

## Errores abiertos, por gravedad

Ninguno bloquea la defensa. En orden:

1. **A-09** (decisión): la clave fija del botón de ejemplo. Apagarlo con `REGISTRO_PRECARGA=0` si el sitio queda público.
2. **A-02**: la compra rechazada por el nombre de quien recibe pierde lo tecleado.
3. **A-03**: el OC acepta cualquier carácter (se muestra escapado).
4. **A-04**: una pestaña vieja sigue mostrando datos tras cerrar sesión en otra.
5. **A-07**, **A-01**, **A-05**, **A-08**: solo de demostración, de entorno local o de etiquetas.
6. **A-06**: decisión de diseño, no falla.

De las filas que no son de estos usuarios y siguen según la matriz: E-04, E-07, E-10 (flota-autonoma), E-29 y E-30. No se reprodujeron aquí porque son de despacho o del CRM.

## Qué no se pudo probar

- **Mercado Pago:** sin credenciales; el pago fue Webpay simulado.
- **IA con claves reales:** sin claves en el stack, el asistente y Soporte respondieron «no disponible» y el reclamo quedó sin clasificar. El camino feliz de la IA no se vio en esta revisión.
- **Correo real:** el enlace de recuperación salió en el registro del contenedor y apunta a `https://localhost:8443` (solo en modo DEBUG). En AWS el enlace depende de `DJANGO_CSRF_ORIGINS` (`http://IP`); hay que revisarlo allí con un correo real.
- **AWS:** nada se desplegó ni se tocó.
- **Combinaciones sin recorrer:** B2B en tema oscuro, B2C en móvil oscuro, visitante en móvil claro, y tablet. En los demás casos no se miró cada pantalla en los cuatro modos, solo las de la tabla de cobertura.
- **Gestos táctiles reales:** el móvil fue una ventana de 375 px con clics de ratón, sin pulsaciones largas ni desplazamientos con el dedo.
- **Navegadores distintos de Chromium** (Safari, Firefox) y lectores de pantalla.
- **Mapa con teselas reales en móvil** y el mapa de un viaje con varias paradas visto con ojos; se confirmó por API y por el contenedor del mapa, no cada trazo.
- **Los 50 camiones y Grafana:** solo corrieron 10 camiones y no se levantó Grafana; no era parte de esta revisión.
