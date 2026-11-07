# Guion de la defensa técnica (Hito 2, jue 12-nov-2026)

> Dura unos 12 minutos más preguntas. Cada bloque dice qué mostrar, qué decir y qué dimensión de la rúbrica del Hito 2 respalda. Las direcciones y las cuentas están en `docs/guia-pruebas-aws.md`; la clave de demostración **no** va en el repositorio.
> Reparto sugerido: **Eric** presenta los bloques 1, 2 y 4; **Sergio** los bloques 3, 5 y 6. Ambos deben poder responder todo: la rúbrica penaliza los "vacíos conceptuales".

## Antes de entrar (30 min antes)

1. Start Lab y esperar el círculo verde; credenciales nuevas; `bash aws/provision.sh estado` (todo `available` y `running`) o `encender`.
2. `python3 aws/verificar.py --ia`: todo con ✓ y un requerimiento **sin clasificar** para la demo de la IA.
3. Abrir en pestañas: `/salud/`, `/` (sin sesión), el BI en `/bi/` (con la cuenta de gerencia o admin; Grafana ya no se abre por el puerto 3000), `/flota/`, `/crm/`.
4. Plan B: capturas de `docs/capturas-visual/`, por si el laboratorio no responde.
5. Confirmar que `ANTHROPIC_API_KEY` está vacía en `aws/.estado/secretos.env`: en la defensa la IA debe ser solo la gratuita (Gemini y Groq).
6. Confirmar que la EC2 IoT corre el simulador con escenarios: si el código llegó después de crearla, `bash aws/provision.sh recrear-iot`. Probar un botón de `/demo/` y limpiar.
5. En `/flota/`, confirmar que «Despacho automático» dice **Apagado** y que «Armar despacho» tiene al menos cuatro pedidos: dos para el armado manual y el resto para la pasada automática. Encendido, vaciaría la lista antes del bloque del despacho.
6. Confirmar que `ANTHROPIC_API_KEY` está vacía en `aws/.estado/secretos.env`: en la defensa la IA debe ser solo la gratuita (Gemini y Groq).

## Guion

| # | Bloque | Qué mostrar | Qué decir (idea clave) | Rúbrica |
|---|---|---|---|---|
| 1 | Problema y solución (1 min) | `informe/img/arquitectura-cloud.drawio.png` | Los tres dolores comparten una causa: no hay un dato único. Una base central en RDS a la que escriben el portal y los camiones, y de la que leen el CRM y el BI | H1 |
| 2 | Despliegue persistente (2 min) | `/salud/` con `{"estado": "ok"}`; consola de las dos EC2 y RDS | Backend en EC2 con Docker Compose y reinicio automático; RDS PostgreSQL en subred privada; nada depende de un PC local. Declarar límites: Single-AZ, HTTP, `LabRole` | D1 |
| 3 | E-commerce B2B y B2C (3 min) | Comprar como `ana@correo.test` y como `abastecimiento@hospital.test`: **mismo producto, otro precio**; en B2B se pide la OC y, si falta, la orden se crea igual como «OC pendiente» (RN-05) y ventas lo ve en el CRM | Lista de precios por tipo de cliente; carrito y orden persisten en la base. Cancelar y mostrar que el stock se repone | D2 |
| 4 | CRM (2 min) | Con `vendedora@cofrial.cl`: la orden web recién creada aparece en la ficha del Hospital; un prospecto no avanza sin interacción | Erradica el Shadow IT: la cartera es de la empresa y cada vendedor ve solo la suya | D2 |
| 5 | IoT y dashboard (3 min) | `/flota/` con "En vivo · cada 5 s"; `/api/flota/`; Grafana en `/bi/` con ventas por canal y alertas; hacer una compra y ver el gráfico cambiar en 5 a 10 s | Contenedores Docker en la EC2 dedicada insertan `camion_id`, `temp_camara`, `lat`, `long`, `combustible_pct` y `alerta_ruptura_frio` directo en RDS; el tablero cruza ventas con cadena de frío | D3, D4 |
| 6 | IA gratuita en vivo (2 min) | En el CRM, clasificar el requerimiento de ejemplo con el botón de IA | Gemini en free tier con respaldo Groq; guarda la confianza, umbral 0,60 y tope de 12 s (la latencia medida es de 4 a 7 s); si falla, queda "sin clasificar" y no se pierde (RN-14). Medido: 20 de 20 con respaldo | D5 |

### Bloque 7 (opcional, 2 min): escenarios del simulador con IA

Sirve para mostrar IoT, IA y CRM en una sola historia. Si el tiempo aprieta, va después del bloque 6 o se usa al responder "muéstreme una falla".

**Antes de empezar:** el camión debe estar recorriendo un viaje. A 50 km/h los viajes dentro de Temuco terminan en pocos minutos, así que conviene armar uno nuevo en `/flota/despachar/` justo antes o usar uno a otra comuna. Tener abiertas `/demo/` y `/flota/`.

1. En `/demo/`, sección 4, escribir: «falla de frío a mitad de ruta en el camión del Hospital» y pulsar **Interpretar con IA**.
2. Leer la propuesta en voz alta: el resumen lo redacta el código a partir de lo que aceptó el validador. Hasta aquí nada cambió en el simulador.
3. Pulsar **Activar esta propuesta**. El escenario aparece «pendiente» y pasa a «en curso» cuando el camión llega a ese avance; para no esperar, usar el botón **Falla de frío ahora**.
4. En `/flota/` el camión pasa a rojo; las alertas llegan al CRM y a Grafana, igual que una falla real.
5. Con **Cliente no recibe**: el pedido pasa a «Camión en la puerta» y luego a «Entrega no concretada», y aparece el requerimiento en `/crm/requerimientos/`.
6. Cerrar con **Borrar lo de la demostración**.

**Qué decir:** la IA interpreta y propone, pero no decide. Un validador en código acepta solo tres escenarios y parámetros acotados, la base lo repite con restricciones `CHECK` y una persona confirma. Las lecturas las siguen insertando los contenedores: el escenario viaja por RDS, que la EC2 IoT ya alcanza, sin abrirle ningún puerto.

**Si la IA no responde:** la pantalla lo avisa y los cuatro botones hacen lo mismo sin ella. No hay que explicar nada más: es parte del diseño.

### Bloque 8 (opcional, 4 min): reparto regional en tiempo acelerado

Sirve para mostrar el negocio real: Cofrial reparte en toda La Araucanía, no solo en Temuco. Va bien después del bloque 5 o al responder «¿y si el cliente está lejos?».

**Antes de empezar:** tener abiertas `/flota/`, `/demo/` y otra ventana con `abastecimiento@hospitalangol.test` (las claves están en la hoja de cuentas). Revisar que `/flota/despachar/` tenga pedidos `OC-REG-…`; si se usaron en un ensayo, comprar uno desde la cuenta de Angol, Villarrica o Pucón.

1. En `/flota/despachar/` marcar los pedidos de Lautaro, Victoria y Angol. El mapa muestra la ruta por carretera, 273,5 km ida y vuelta y unos 328 minutos a velocidad real, y propone un camión refrigerado.
2. Pulsar **Despachar y salir ahora**.
3. En `/demo/`, sección 5, elegir **60×**. El aviso naranja aparece en todas las pantallas, también en la del cliente, y en Grafana.
4. Con la cuenta de Angol, abrir el pedido: los km bajan unos 4 por lectura y «Llega entre» es una ventana de 2 minutos. Con las tres paradas, el camión llega a Angol en unos 4 minutos y vuelve a la base en unos 7.
5. Antes de llegar aparece «Tu pedido está por llegar» y luego «Camión en la puerta». El cliente confirma con **Recibí mi pedido**: tiene los mismos 2 minutos de siempre.
6. En `/flota/` el camión pasa a «volviendo» y regresa por la carretera. En Grafana se ve en el mapa de toda la región.
7. Cerrar con **Borrar lo de la demostración**, que deja el tiempo en 1×.

**Qué decir:** el multiplicador solo cambia los km que avanza el camión por lectura. Sigue entrando una lectura cada 5 segundos con los seis campos de la pauta, y las reglas de frío y de despacho no cambian. La hora de llegada usa el mismo multiplicador, por eso sigue siendo una hora real del reloj.

**Si OSRM está caído:** las rutas de la demostración ya están en la caché. Un viaje nuevo que no esté en ella sale igual, con rectas punteadas.

## Recorrido por los cuatro flujos

> Antes era la página pública `/guia/`; se sacó del sitio el 29-oct-2026 porque es conocimiento del equipo, no algo para cualquier visitante. Sirve para ensayar y para responder "muéstreme cómo funciona" sin improvisar.

**1. Un cliente compra y sigue su pedido** (cliente institucional o particular)
1. Ingresa con su cuenta; un particular nuevo puede crearla en `/cuenta/registro/`.
2. En `/catalogo/` filtra o busca y pulsa **Agregar**: el precio cambia según el perfil.
3. En `/carrito/` elige la dirección (la institución indica su orden de compra; si la deja vacía, la orden queda «OC pendiente» con referencia WEB-año-número y la agrega después en el detalle) y pulsa **Generar orden**.
4. El pedido queda **Recibida**; pasa al flujo 2 para que salga en un camión.
5. En `/seguimiento/` ve el camión en el mapa, la ruta que falta y la temperatura de la cámara; si algo sale mal, **Reportar un problema**.

**2. Despacho arma un viaje con la mejor ruta** (despacho, gerencia o admin)
1. Abre `/flota/`: el mapa y las tarjetas muestran los camiones en ruta, en la puerta, volviendo o con alerta. Los guardados se resumen en un contador y aparecen con **Mostrar los N en base**; los 50 siguen reportando.
2. **Armar despacho** (`/flota/despachar/`): aparecen los pedidos sin camión y los camiones libres.
3. Marca dos o más pedidos del mismo rango: el sistema propone el camión libre con más combustible y dice por qué, y el mapa traza la ruta más corta y numera el orden de entrega. Se puede elegir otro camión.
4. **Despachar y salir ahora**: los pedidos pasan a **Despachada** y la ruta por calles queda guardada (la misma que ven el camión y el cliente).
5. En la flota se ve cada camión: en base, en ruta, en la puerta del cliente o volviendo. El cliente ve su camión solo mientras va en camino.
6. Al llegar, el pedido pasa solo a **Camión en la puerta**; el cliente ve un banner en cualquier página, revisa los productos y la temperatura del viaje y confirma **Recibí mi pedido** (si algo falló, queda entregado y llega a ventas como reclamo) o explica por qué no pudo (queda **Entrega no concretada** y llega a ventas). Si no responde, se confirma sola. Cada cliente ve en su mapa solo el tramo hasta su parada, no el viaje completo.
- Regla de cadena de frío: no se mezclan refrigerado y congelado en un mismo camión.

**Despacho sin personas** (después del armado manual; despachador o admin)
1. Muestra el recuadro «Despacho automático» en `/flota/`: dice **Apagado**, las reglas y qué pedidos no saldrían solos y por qué.
2. Pulsa **Correr una pasada ahora** y confirma. Es una pasada real con las mismas reglas del modo automático: despacha hasta 3 viajes sin esperar la agrupación y deja el resto de los pedidos.
3. El recuadro muestra cada decisión: qué camión, qué pedidos, por qué salió y si el texto lo redactó la IA o el sistema.
4. Di en voz alta: la decisión es código determinista; la IA solo redacta después de que el viaje salió y, si falla, queda el texto del sistema.
- **No enciendas `DESPACHO_AUTO=1` durante la defensa:** recrea el contenedor web y deja la página sin responder mientras arranca. Para dejarlo encendido después, en la EC2 web: agrega `DESPACHO_AUTO=1` a `/opt/cofrial/.env` y corre `docker compose -f aws/docker-compose.web.yml --env-file .env up -d --build web despachador`. Apagarlo es lo mismo con `DESPACHO_AUTO=0`.

**3. Ventas atiende un reclamo con IA** (vendedor, gerencia o admin)
1. Un cliente escribe en `/soporte/` o desde un pedido con «Reportar un problema».
2. `/crm/requerimientos/` muestra quién la clasificó: la IA, una persona o nadie.
3. En uno sin clasificar, **Clasificar con IA**: categoría y confianza en segundos.
4. `/crm/ia/` prueba un mensaje en vivo y muestra lo que recibe cada proveedor (Gemini y Groq).
5. `/crm/embudo/` sigue a los prospectos y `/crm/demanda/` muestra qué productos esperan los clientes.

**4. Un producto sin stock y el aviso al cliente** (cliente y vendedor)
1. El cliente abre un producto sin stock (por ejemplo, los camarones) en `/catalogo/`.
2. Escribe cuántas unidades necesita y pulsa **Avisarme**.
3. El equipo ve esa demanda en `/crm/demanda/` y repone el stock.
4. Con stock suficiente, el cliente ve un contador en `/avisos/` y compra desde ahí.

**5. El administrador agrega usuarios por tipo** (solo `admin@cofrial.cl`; si el profesor pregunta «¿cómo se crea un usuario?»)
1. Ingresar con `admin@cofrial.cl` (la clave está en la hoja de cuentas, no se escribe aquí ni se muestra en pantalla). El inicio es `/crm/`: en «Accesos directos del administrador» pulsar **Usuarios** (también está en el menú lateral, «Operación del sistema»).
2. `/operacion/cuentas/` muestra una tarjeta por tipo con su cantidad: cliente institucional, cliente particular, vendedor, gerencia, despachador y administrador. Pulsar la tarjeta filtra la tabla y la búsqueda sigue funcionando; cada fila tiene **Asignar clave**.
3. Pulsar **Agregar** en una tarjeta (por ejemplo, Vendedor): el formulario pide solo los datos de ese tipo (RUT, dirección y vendedor aparecen solo para clientes). Escribir un correo y una clave dos veces; la clave no se muestra ni vuelve a la pantalla.
4. Volver a la lista: la cantidad de esa tarjeta subió en uno. Mostrar que entra: cerrar sesión e ingresar con la cuenta nueva (esa clave la dicta quien la creó).
5. Abajo, **Clientes sin cuenta del portal**: un cliente ganado en el CRM aparece ahí; **Crear cuenta** lo enlaza a ese mismo cliente, sin duplicarlo.
- Seguridad que se puede mencionar: solo el administrador entra (los demás roles reciben 403), la clave se valida y se guarda con hash, y reponer stock está en `/operacion/stock/`, enlazado desde `/crm/demanda/`.

**Tablero BI:** Grafana en `/bi/` cruza ventas por canal con alertas de ruptura de frío y se refresca solo; lo ven admin (edita) y gerencia (solo mira), el resto recibe acceso denegado.

## Preguntas probables

- **¿Por qué Django y no FastAPI, React o Node?** La pauta deja libre el stack y evalúa negocio, conexión a la base y estabilidad. Django entrega ORM con migraciones, autenticación, permisos por grupo y un admin que sirve de CRM base, con un solo lenguaje (Python) también para el simulador. La API JSON se expuso con Django REST Framework sin cambiar el modelo (`docs/decisiones.md`, D-01).
- **¿Por qué EC2 y no Lambda o Elastic Beanstalk?** Backend persistente, Docker Compose conocido por el equipo y control de la red; ver `informe/03-arquitectura-cloud.md`.
- **¿Por qué la base va en subred privada?** Es el activo de la empresa; solo la alcanzan las dos EC2 por Security Group.
- **¿Qué pasa si la IA falla o está saturada?** Prueba en cascada de modelos, luego Groq; si todo falla, el requerimiento queda "sin clasificar".
- **¿La IA puede romper el simulador o ejecutar algo?** No. Devuelve JSON que el validador lee llave por llave: tipo de una lista cerrada, viaje y parada que existen y números dentro de un rango; lo demás se ignora o se rechaza. Ningún texto del modelo llega a SQL y el motivo de «no recibe» sale de una lista fija. Además, la activación la confirma un administrador.
- **¿Por qué el escenario va por la base y no por una API al contenedor?** La EC2 IoT no tiene entradas abiertas y ya conecta a RDS. Leer una tabla en cada ciclo no agrega puertos ni credenciales, y el escenario sobrevive a un reinicio. El costo es una espera de hasta 5 s.
- **¿Las lecturas de un escenario son falsas?** Las inserta el mismo contenedor, con la misma regla de alerta. El escenario cambia cómo se comporta el camión simulado; van marcadas `forzada` para poder borrarlas después de la demostración.
- **¿Cómo sabe que está en tercera forma normal?** Dependencias funcionales por tabla en `informe/04b-modelo-datos.md`; se corrigió una dependencia transitiva en `orden`.
- **¿Usan una IA de pago?** No en la demostración. El código admite Claude como tercer proveedor opcional, pero solo entra si existe `ANTHROPIC_API_KEY`, y en AWS esa variable queda vacía. Gemini y Groq, ambos en plan gratuito, cubren el requisito.
- **¿La telemetría no llena la base?** Son unas 864 000 filas al día. `podar_telemetria` corre a diario y borra las lecturas normales de más de 7 días; las alertas, las lecturas de los viajes y la última de cada camión se conservan, porque sostienen los pedidos afectados y los reclamos. En producción iría a una base de series de tiempo.
- **¿Qué pasa si dos personas compran la última unidad a la vez?** Se probó con dos sesiones simultáneas: la transacción bloquea el producto, una compra gana y la otra ve «No hay stock suficiente». El stock queda en 0 y nunca negativo. Lo mismo con un doble clic en confirmar: una orden, un descuento.
- **Se me venció la sesión con el carrito armado, ¿lo pierdo?** No. El carrito está en la base y no en la sesión: tras ingresar se vuelve a la página donde estaba y no se compra nada a ciegas. Hasta el 6-nov esto terminaba en una página en blanco; se encontró en este recorrido y se corrigió.
- **¿Un vendedor puede ver los reclamos de otro?** Ya no. El cliente, el prospecto y el documento estaban protegidos, pero la bandeja de reclamos era común y un vendedor pudo clasificar uno ajeno. Se corrigió y tiene pruebas. Los reclamos de clientes sin vendedor, los B2C, siguen en una bandeja común a propósito: si no, no los atendería nadie.
- **Si la ruptura ocurre con dos clientes en el camión, ¿a quién afecta?** A la carga que seguía a bordo. Quien ya recibió no cuenta: su exposición termina al confirmar la entrega, y quien está en la puerta sigue expuesto. El CRM y Grafana usan la misma regla y dan los mismos pedidos.
- **¿Qué hace el cliente si la alerta es real?** Reporta desde el pedido. Ventas ve al lado la temperatura real del viaje, sacada de la base y no de la IA, aunque la IA esté caída. Puede emitir una nota de crédito (RN-21). La alerta no bloquea la entrega ni avisa sola al vendedor: aparece destacada en su ficha y en Alertas.
- **¿Qué pasa si se cae la base en plena demo?** Se probó deteniéndola: el sitio responde 503 con una página propia, sin traza. `/salud/` sigue vivo y `/salud/bd/` lo delata. Al volver la base la web responde en segundos y el simulador se reconecta solo a los 5 s. Lo enviado mientras tanto se pierde: no hay cola.
- **¿Y si se cae OSRM?** El despacho no falla: la ruta son rectas marcadas como aproximadas, y tarda 8 s en vez de un instante porque espera dos intentos. El mapa dibuja esa ruta con línea punteada.
- **¿El tiempo acelerado falsea la telemetría?** No. El simulador sigue insertando una lectura cada `INTERVALO_SEG`, con los mismos campos y la misma regla de alerta; solo avanza más km por lectura. El combustible y la temperatura siguen al ritmo de las lecturas, así que a 60× el combustible baja menos de lo que bajaría en un viaje real.
- **A 60× el camión avanza más de 4 km por lectura, ¿se puede saltar una parada?** No. El avance de cada lectura termina en la primera parada que encuentra, aunque le sobre distancia. Hay una prueba con tres paradas a 200 m entre sí.
- **¿Por qué el plazo para confirmar no se acelera?** Porque lo responde una persona frente a la pantalla. Dividido por 60 serían 2 segundos y nadie alcanzaría a pulsar. Por eso el camión puede ya ir volviendo mientras el cliente confirma, igual que a velocidad normal: se queda 30 segundos en la puerta y el plazo es de 2 minutos.
- **¿De dónde salen las direcciones de otras comunas?** Son direcciones públicas de hospitales, con coordenadas de OpenStreetMap guardadas en `web/clientes/regionales.py`, así que la demostración no depende de Nominatim. Los RUT y los correos son ficticios.
- **¿Qué pasa si detengo el simulador?** Dejan de llegar lecturas y los pedidos en ruta quedan quietos; se pueden cerrar a mano. Al reiniciarlo el viaje recomienza desde la base, sin perder pedidos ni repetir entregas, pero el camión salta en el mapa. Es un simulador: el camión real no vuelve a la base al reiniciar un servidor.
- **¿Quién confirma y prepara los pedidos?** Aquí el prototipo simplifica: «Confirmada» y «En preparación» existen y el vendedor cancela hasta ahí, pero no hay una pantalla de bodega para marcarlas. Despachar recorre esos estados sola. En producción serían pasos de bodega, que el caso no pide.
- **Un prospecto ganado, ¿ya puede comprar?** Queda como cliente con su lista institucional y su vendedor, que le agrega la dirección y le crea pedidos desde la ficha. Todavía no recibe cuenta del portal de forma automática.
- **Cuando ventas resuelve un reclamo, ¿qué ve el cliente?** Ve el estado «resuelto» en Soporte, y queda la fecha para el indicador de primera respuesta. No hay mensajes dentro del portal: la respuesta en sí va por teléfono o correo y se registra como interacción.
- **¿El bloqueo de cuentas funciona con varios servidores?** Con uno sí: 10 claves malas bloquean la cuenta 15 minutos. Los contadores viven en la memoria del proceso, por eso gunicorn corre con un proceso y 16 hilos; con dos procesos se probó que el bloqueo salía al azar. Con varias instancias haría falta Redis.
- **¿Cómo saben que esto funciona?** Más de 480 pruebas automáticas, y un recorrido por cada caso de uso y regla en `docs/matriz-casos-de-uso.md`, que también dice qué sigue abierto y qué no se probó.
- **¿Quién decide en el despacho automático, la IA?** No. El código agrupa por rango de frío, junta las comunas y hace salir el viaje al completar 6 paradas o cuando el pedido más antiguo lleva 5 minutos. La IA recibe la decisión ya tomada, sin nombres ni direcciones, y solo la redacta. El detalle está en `docs/decisiones.md`.
- **¿Qué sigue necesitando a una persona?** Las entregas no concretadas, porque repetir el viaje sin saber qué pasó sería repetir el error; los pedidos sin ubicar en el mapa, y los que no tienen camión apto. El recuadro dice cuáles son y por qué.
- **¿Qué falta para producción?** Multi-AZ, HTTPS con dominio, permisos mínimos por rol de AWS, respaldos más largos y telemetría por cola en vez de inserción directa.

## Ensayo del plan B (pendiente de hacer)

- [ ] Detener el laboratorio y volver a iniciarlo; medir cuánto tarda en responder `/salud/` (hoy 3 a 6 min con `encender`).
- [ ] Cronometrar la demo completa y recortar a 12 minutos.
- [ ] Repartir los bloques y ensayar una vez en voz alta con las preguntas anteriores.
- [ ] Al terminar la demo: `bash aws/provision.sh destruir` para no gastar el crédito.
