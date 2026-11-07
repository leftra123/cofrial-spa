# Guion de la defensa técnica (Hito 2, jue 12-nov-2026)

> Dura unos 12 minutos más preguntas. Cada bloque dice qué mostrar, qué decir y qué dimensión de la rúbrica del Hito 2 respalda. Las direcciones y las cuentas están en `docs/guia-pruebas-aws.md`; la clave de demostración **no** va en el repositorio.
> Reparto sugerido: **Eric** presenta los bloques 1, 2 y 4; **Sergio** los bloques 3, 5 y 6. Ambos deben poder responder todo: la rúbrica penaliza los "vacíos conceptuales".

## Antes de entrar (30 min antes)

1. Start Lab y esperar el círculo verde; credenciales nuevas; `bash aws/provision.sh estado` (todo `available` y `running`) o `encender`.
2. `python3 aws/verificar.py --ia`: todo con ✓ y un requerimiento **sin clasificar** para la demo de la IA.
3. Abrir en pestañas: `/salud/`, `/` (sin sesión), el BI en `/bi/` (con la cuenta de gerencia o admin; Grafana ya no se abre por el puerto 3000), `/flota/`, `/crm/`.
4. Plan B: capturas de `docs/capturas-visual/`, por si el laboratorio no responde.
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
6. Al llegar, el pedido pasa solo a **Camión en la puerta**; el cliente confirma **Recibí mi pedido** o explica por qué no pudo (queda **Entrega no concretada** y llega a ventas). Si no responde, se confirma sola.
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

**Tablero BI:** Grafana en `/bi/` cruza ventas por canal con alertas de ruptura de frío y se refresca solo; lo ven admin (edita) y gerencia (solo mira), el resto recibe acceso denegado.

## Preguntas probables

- **¿Por qué Django y no FastAPI, React o Node?** La pauta deja libre el stack y evalúa negocio, conexión a la base y estabilidad. Django entrega ORM con migraciones, autenticación, permisos por grupo y un admin que sirve de CRM base, con un solo lenguaje (Python) también para el simulador. La API JSON se expuso con Django REST Framework sin cambiar el modelo (`docs/decisiones.md`, D-01).
- **¿Por qué EC2 y no Lambda o Elastic Beanstalk?** Backend persistente, Docker Compose conocido por el equipo y control de la red; ver `informe/03-arquitectura-cloud.md`.
- **¿Por qué la base va en subred privada?** Es el activo de la empresa; solo la alcanzan las dos EC2 por Security Group.
- **¿Qué pasa si la IA falla o está saturada?** Prueba en cascada de modelos, luego Groq; si todo falla, el requerimiento queda "sin clasificar".
- **¿Cómo sabe que está en tercera forma normal?** Dependencias funcionales por tabla en `informe/04b-modelo-datos.md`; se corrigió una dependencia transitiva en `orden`.
- **¿Usan una IA de pago?** No en la demostración. El código admite Claude como tercer proveedor opcional, pero solo entra si existe `ANTHROPIC_API_KEY`, y en AWS esa variable queda vacía. Gemini y Groq, ambos en plan gratuito, cubren el requisito.
- **¿La telemetría no llena la base?** Son unas 864 000 filas al día. `podar_telemetria` corre a diario y borra las lecturas normales de más de 7 días; las alertas, las lecturas de los viajes y la última de cada camión se conservan, porque sostienen los pedidos afectados y los reclamos. En producción iría a una base de series de tiempo.
- **¿Quién decide en el despacho automático, la IA?** No. El código agrupa por rango de frío, junta las comunas y hace salir el viaje al completar 6 paradas o cuando el pedido más antiguo lleva 5 minutos. La IA recibe la decisión ya tomada, sin nombres ni direcciones, y solo la redacta. El detalle está en `docs/decisiones.md`.
- **¿Qué sigue necesitando a una persona?** Las entregas no concretadas, porque repetir el viaje sin saber qué pasó sería repetir el error; los pedidos sin ubicar en el mapa, y los que no tienen camión apto. El recuadro dice cuáles son y por qué.
- **¿Qué falta para producción?** Multi-AZ, HTTPS con dominio, permisos mínimos por rol de AWS, respaldos más largos y telemetría por cola en vez de inserción directa.

## Ensayo del plan B (pendiente de hacer)

- [ ] Detener el laboratorio y volver a iniciarlo; medir cuánto tarda en responder `/salud/` (hoy 3 a 6 min con `encender`).
- [ ] Cronometrar la demo completa y recortar a 12 minutos.
- [ ] Repartir los bloques y ensayar una vez en voz alta con las preguntas anteriores.
- [ ] Al terminar la demo: `bash aws/provision.sh destruir` para no gastar el crédito.
