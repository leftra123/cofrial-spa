# Guion de la defensa técnica (Hito 2, jue 12-nov-2026)

> Dura unos 12 minutos más preguntas. Cada bloque dice qué mostrar, qué decir y qué dimensión de la rúbrica del Hito 2 respalda. Las direcciones y las cuentas están en `docs/guia-pruebas-aws.md`; la clave de demostración **no** va en el repositorio.
> Reparto sugerido: **Eric** presenta los bloques 1, 2 y 4; **Sergio** los bloques 3, 5 y 6. Ambos deben poder responder todo: la rúbrica penaliza los "vacíos conceptuales".

## Antes de entrar (30 min antes)

1. Start Lab y esperar el círculo verde; credenciales nuevas; `bash aws/provision.sh estado` (todo `available` y `running`) o `encender`.
2. `python3 aws/verificar.py --ia`: todo con ✓ y un requerimiento **sin clasificar** para la demo de la IA.
3. Abrir en pestañas: `/salud/`, `/` (sin sesión), Grafana `:3000`, `/flota/`, `/crm/`.
4. Plan B: capturas de `docs/capturas-visual/`, por si el laboratorio no responde.

## Guion

| # | Bloque | Qué mostrar | Qué decir (idea clave) | Rúbrica |
|---|---|---|---|---|
| 1 | Problema y solución (1 min) | `informe/img/arquitectura-cloud.drawio.png` | Los tres dolores comparten una causa: no hay un dato único. Una base central en RDS a la que escriben el portal y los camiones, y de la que leen el CRM y el BI | H1 |
| 2 | Despliegue persistente (2 min) | `/salud/` con `{"estado": "ok"}`; consola de las dos EC2 y RDS | Backend en EC2 con Docker Compose y reinicio automático; RDS PostgreSQL en subred privada; nada depende de un PC local. Declarar límites: Single-AZ, HTTP, `LabRole` | D1 |
| 3 | E-commerce B2B y B2C (3 min) | Comprar como `ana@correo.test` y como `abastecimiento@hospital.test`: **mismo producto, otro precio**; la OC es obligatoria en B2B | Lista de precios por tipo de cliente; carrito y orden persisten en la base. Cancelar y mostrar que el stock se repone | D2 |
| 4 | CRM (2 min) | Con `vendedora@cofrial.cl`: la orden web recién creada aparece en la ficha del Hospital; un prospecto no avanza sin interacción | Erradica el Shadow IT: la cartera es de la empresa y cada vendedor ve solo la suya | D2 |
| 5 | IoT y dashboard (3 min) | `/flota/` con "En vivo · cada 5 s"; `/api/flota/`; Grafana con ventas por canal y alertas; hacer una compra y ver el gráfico cambiar en 5 a 10 s | Contenedores Docker en la EC2 dedicada insertan `camion_id`, `temp_camara`, `lat`, `long`, `combustible_pct` y `alerta_ruptura_frio` directo en RDS; el tablero cruza ventas con cadena de frío | D3, D4 |
| 6 | IA gratuita en vivo (2 min) | En el CRM, clasificar el requerimiento de ejemplo con el botón de IA | Gemini en free tier con respaldo Groq; guarda la confianza, umbral 0,60 y tope de 5 s; si falla, queda "sin clasificar" y no se pierde (RN-14). Medido: 20 de 20 con respaldo | D5 |

## Preguntas probables

- **¿Por qué Django y no FastAPI, React o Node?** La pauta deja libre el stack y evalúa negocio, conexión a la base y estabilidad. Django entrega ORM con migraciones, autenticación, permisos por grupo y un admin que sirve de CRM base, con un solo lenguaje (Python) también para el simulador. La API JSON se expuso con Django REST Framework sin cambiar el modelo (`docs/decisiones.md`, D-01).
- **¿Por qué EC2 y no Lambda o Elastic Beanstalk?** Backend persistente, Docker Compose conocido por el equipo y control de la red; ver `informe/03-arquitectura-cloud.md`.
- **¿Por qué la base va en subred privada?** Es el activo de la empresa; solo la alcanzan las dos EC2 por Security Group.
- **¿Qué pasa si la IA falla o está saturada?** Prueba en cascada de modelos, luego Groq; si todo falla, el requerimiento queda "sin clasificar".
- **¿Cómo sabe que está en tercera forma normal?** Dependencias funcionales por tabla en `informe/04b-modelo-datos.md`; se corrigió una dependencia transitiva en `orden`.
- **¿Qué falta para producción?** Multi-AZ, HTTPS con dominio, permisos mínimos por rol de AWS, respaldos más largos y telemetría por cola en vez de inserción directa.

## Ensayo del plan B (pendiente de hacer)

- [ ] Detener el laboratorio y volver a iniciarlo; medir cuánto tarda en responder `/salud/` (hoy 3 a 6 min con `encender`).
- [ ] Cronometrar la demo completa y recortar a 12 minutos.
- [ ] Repartir los bloques y ensayar una vez en voz alta con las preguntas anteriores.
- [ ] Al terminar la demo: `bash aws/provision.sh destruir` para no gastar el crédito.
