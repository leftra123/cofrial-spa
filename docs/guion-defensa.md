# Guion de la defensa técnica (Hito 2, jue 12-nov-2026)

> Dura unos 12 minutos más preguntas. Cada bloque dice qué mostrar, qué decir y qué dimensión de la rúbrica del Hito 2 respalda. Las direcciones y las cuentas están en `docs/guia-pruebas-aws.md`; la clave de demostración **no** va en el repositorio.
> Reparto sugerido: **Eric** presenta los bloques 1, 2 y 4; **Sergio** los bloques 3, 5 y 6. Ambos deben poder responder todo: la rúbrica penaliza los "vacíos conceptuales".

## Antes de entrar (30 min antes)

1. Start Lab y esperar el círculo verde; credenciales nuevas; `bash aws/provision.sh estado` (todo `available` y `running`) o `encender`.
2. `python3 aws/verificar.py --ia`: todo con ✓ y un requerimiento **sin clasificar** para la demo de la IA.
3. Abrir en pestañas: `/salud/`, `/` (sin sesión), el BI en `/bi/` (con la cuenta de gerencia o admin; Grafana ya no se abre por el puerto 3000), `/flota/`, `/crm/`.
4. Plan B: capturas de `docs/capturas-visual/`, por si el laboratorio no responde.
5. Confirmar que `ANTHROPIC_API_KEY` está vacía en `aws/.estado/secretos.env`: en la defensa la IA debe ser solo la gratuita (Gemini y Groq).

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
1. Abre `/flota/`: camiones, temperatura y mapa.
2. **Armar despacho** (`/flota/despachar/`): aparecen los pedidos sin camión y los camiones libres.
3. Elige el camión y marca dos o más pedidos: el mapa traza la ruta más corta y numera el orden de entrega.
4. **Despachar y salir ahora**: los pedidos pasan a **Despachada** y la ruta por calles queda guardada (la misma que ven el camión y el cliente).
5. En la flota se ve cada camión: en base, en ruta, en la puerta del cliente o volviendo. El cliente ve su camión solo mientras va en camino.
6. Al llegar, el pedido pasa solo a **Camión en la puerta**; el cliente ve un banner en cualquier página, revisa los productos y la temperatura del viaje y confirma **Recibí mi pedido** (si algo falló, queda entregado y llega a ventas como reclamo) o explica por qué no pudo (queda **Entrega no concretada** y llega a ventas). Si no responde, se confirma sola. Cada cliente ve en su mapa solo el tramo hasta su parada, no el viaje completo.
- Regla de cadena de frío: no se mezclan refrigerado y congelado en un mismo camión.

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
- **¿Cómo sabe que está en tercera forma normal?** Dependencias funcionales por tabla en `informe/04b-modelo-datos.md`; se corrigió una dependencia transitiva en `orden`.
- **¿Usan una IA de pago?** No en la demostración. El código admite Claude como tercer proveedor opcional, pero solo entra si existe `ANTHROPIC_API_KEY`, y en AWS esa variable queda vacía. Gemini y Groq, ambos en plan gratuito, cubren el requisito.
- **¿La telemetría no llena la base?** Son unas 864 000 filas al día. `podar_telemetria` corre a diario y borra las lecturas normales de más de 7 días; las alertas, las lecturas de los viajes y la última de cada camión se conservan, porque sostienen los pedidos afectados y los reclamos. En producción iría a una base de series de tiempo.
- **¿Qué falta para producción?** Multi-AZ, HTTPS con dominio, permisos mínimos por rol de AWS, respaldos más largos y telemetría por cola en vez de inserción directa.

## Ensayo del plan B (pendiente de hacer)

- [ ] Detener el laboratorio y volver a iniciarlo; medir cuánto tarda en responder `/salud/` (hoy 3 a 6 min con `encender`).
- [ ] Cronometrar la demo completa y recortar a 12 minutos.
- [ ] Repartir los bloques y ensayar una vez en voz alta con las preguntas anteriores.
- [ ] Al terminar la demo: `bash aws/provision.sh destruir` para no gastar el crédito.
