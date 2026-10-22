# Verificación contra la pauta del Hito 1

> Matriz de trazabilidad entre lo que exige el PDF del curso (`INACAP Temuco - EVA2_3 Transformación Digital.pdf`, verificado contra `00-pauta-y-rubrica.md` el 16-oct-2026) y lo que contiene el repositorio.
> Estado de cada exigencia: **Cubierto** (hay contenido que responde al criterio), **Parcial** (existe, pero falta validar o completar) o **Falta**. "Cubierto" significa que el contenido responde al criterio de la rúbrica; la nota la decide el docente.

## 1. Estructura obligatoria del informe (PDF, sección 3)

**Tabla 1**
*Exigencias de estructura del Hito 1 y dónde se atienden*

| Exigencia del PDF | Archivo | Estado | Observación |
|---|---|---|---|
| 1. Diagnóstico y análisis del dolor: vulnerabilidad on-premises, última milla con Shadow IT y ausencia de canales | `01-diagnostico.md` | Cubierto | Árbol de problemas, cinco porqués por dolor, ciclo de refuerzo y modelo de impacto con supuestos |
| 2. Propuesta de valor: cómo la arquitectura Front-Office + Back-Office ataca y erradica cada dolor, incluidos WhatsApp y el papel | `02-propuesta-valor.md`, `05-procesos-bpmn.md` | Cubierto | Matriz dolor, causa raíz, solución e indicador; mecanismos para sustituir canales informales; seis procesos BPMN |
| 3. Memoria de decisiones cloud: por qué EC2, RDS, subredes, VPC y seguridad, con trade-offs | `03-arquitectura-cloud.md`, `08-herramientas.md` | Cubierto | Siete decisiones con alternativas, lo que se gana y se cede; restricciones del Learner Lab |
| 4a. Diagrama de arquitectura cloud: topología completa de red y servicios | `04a-diagrama-arquitectura.md` | Cubierto | Región, VPC, subredes públicas y privadas, IGW, tablas de ruteo, Security Groups, EC2, RDS, IA externa y actores |
| 4b. MER en 3FN y diccionario, para transacciones E-commerce/CRM y telemetría IoT | `04b-modelo-datos.md`, `informe/modelo/` | Cubierto | 25 tablas, verificación tabla por tabla, diccionario completo y script validado en PostgreSQL |
| 4c. Wireframes y flujos de usuario (user journeys) del portal con perfiles B2B y B2C | `04c-canales-b2b-b2c.md` | Cubierto | Seis wireframes del portal y dos journeys diferenciados |
| 4d. Estados del pipeline comercial del CRM | `04d-crm.md` | Cubierto | Diagrama de etapas y transiciones, reglas y permisos por rol |
| Calendario del PDF: "Mockups de canales digitales" | `04c`, `04d` | Parcial | Se entregan wireframes de baja fidelidad (el PDF los llama wireframes en la sección 3 y mockups en el calendario) |
| «El informe técnico ejecutivo debe estructurarse bajo una pauta de consultoría» | `README.md` del informe | **Falta** | Hoy existen las secciones por separado; falta armar el documento único con portada, índices, resumen ejecutivo, glosario, conclusiones y referencias |

*Nota.* Elaboración propia.

## 2. Rúbrica del Hito 1: criterio de «Logrado» frente a la evidencia

**Tabla 2**
*Cumplimiento de cada dimensión de la rúbrica del Hito 1*

| Dimensión | Qué exige «Logrado (100 %)» | Trampa que baja a 60 % | Evidencia | Brecha |
|---|---|---|---|---|
| 1. Diagnóstico y justificación | Analizar en profundidad y argumentar con solidez técnica y de negocio cómo la solución neutraliza **cada** dolor | Repetir el caso sin análisis crítico | Causa raíz común, riesgos técnicos y regulatorios, cinco porqués, modelo de impacto; la matriz de `02` conecta cada dolor con su componente y su indicador | Las cifras son supuestos ilustrativos; validar con datos de Cofrial |
| 2. Decisiones de arquitectura cloud | Justificar VPC, subredes, seguridad, cómputo y persistencia RDS, **argumentando trade-offs** | Listar servicios AWS sin razones ni coherencia con el caso | Cada decisión tiene alternativa, ganancia, costo y riesgo; se amarra al caso (hospitales, respaldos, Learner Lab) y a restricciones verificadas | Verificar duración de sesión y créditos en el laboratorio; que Sergio revise y pueda defender |
| 3. Topología cloud y MER 3FN | Diagrama profesional y MER rigurosamente normalizado para transacciones **y** telemetría | Errores de normalización o diagramas desconectados de la realidad | Diagrama con restricciones reales del Learner Lab (Single-AZ, `LabRole`, regiones); MER con dependencias funcionales por tabla, BCNF, tres redundancias justificadas; corregida una dependencia transitiva; esquema probado | Quitar «v0.1 borrador» del bloque de título del diagrama antes de entregar |
| 4. Canales y CRM | Journeys avanzados B2B y B2C y arquitectura funcional del CRM que erradica el Shadow IT | Describir el sitio o el CRM sin flujos ni lógica de negocio | Journeys con pantalla, dato y regla por etapa; 15 reglas de negocio numeradas; permisos, pipeline con transiciones, eventos entre componentes e indicadores; tabla de prácticas informales sustituidas | Validar con un vendedor de Cofrial; las emociones de los journeys son estimaciones |

*Nota.* Elaboración propia. Fuente de los criterios: PDF del curso, sección 5.

## 3. Coherencia del diseño con las exigencias del Hito 2

El Hito 1 debe dejar un diseño que el Hito 2 pueda construir sin rehacerlo. Se verificó punto por punto:

**Tabla 3**
*Exigencias del Hito 2 y cómo las anticipa el diseño del Hito 1*

| Exigencia del PDF (sección 4) | Cómo la anticipa el diseño | Estado |
|---|---|---|
| EC2 con backend persistente conectada a RDS | EC2 `t3.small` con Docker Compose y reinicio automático; RDS PostgreSQL en subred privada | Cubierto |
| E-commerce con catálogo de refrigerados, perfiles B2B (lista institucional) y B2C, carrito y órdenes | `tipo_cliente → lista_precio`, `precio_producto`, `carrito`, `orden`; reglas RN-01 a RN-08; especificación de CU-04 | Cubierto |
| CRM para gestionar clientes, prospectos y seguimiento de pedidos web | Módulos, permisos, pipeline y consultas; especificación de CU-07 | Cubierto |
| IoT con contenedores Docker en un nodo dedicado, con los campos `camion_id` (String), `temp_camara` (Float), `lat` y `long`, `combustible_pct` (Integer), `alerta_ruptura_frio` (Boolean) | EC2 aparte; tabla `telemetria` con los seis nombres exactos y tipos; `alerta_ruptura_frio` verdadero si la lectura sale del rango del camión; especificación de CU-11 | Cubierto |
| Dashboard en tiempo real que cruce ventas y pedidos por canal con alertas de frío | Grafana; consultas 1 a 4 de `consultas_bi.sql` cruzan ventas por canal con alertas | Cubierto |
| IA externa gratuita integrada en CRM o e-commerce | Gemini (free tier) con respaldo Groq; especificación de CU-09 con falla controlada | Cubierto |

*Nota.* Elaboración propia. Verificado contra la tabla de telemetría de `04b-modelo-datos.md` y el script `informe/modelo/esquema.sql`.

## 4. Lo que va más allá de la pauta

- **Evaluación ponderada de las herramientas** con criterio eliminatorio (`08-herramientas.md`), que el PDF no pide pero respalda cada decisión.
- **Modelo de datos validado en una base real:** el script carga sin errores, las consultas del dashboard devuelven los montos esperados y 15 inserciones inválidas son rechazadas por la propia base.
- **Criterios de aceptación** por caso de uso crítico: son las pruebas del Hito 2.
- **Limitaciones declaradas** del prototipo frente a producción (alta disponibilidad, HTTP, permisos, inserción directa de telemetría), que ayudan en la defensa.
- **Restricciones del Learner Lab** contrastadas con un documento oficial de AWS.
- **Figuras reproducibles:** los diagramas y el esquema se regeneran con scripts; si cambia una decisión, no hay que redibujar.

## 5. Brechas para llegar a «Logrado», por prioridad

1. **Armar el informe único** (la única exigencia sin cubrir): portada, índices, resumen ejecutivo, glosario, secciones en el orden del PDF, conclusiones y referencias APA 7; renumerar tablas y figuras de forma continua. Redacción final con la skill `informe-apa7-tecnico`.
2. **Revisión de Sergio** sobre `03`, `04a`, `04b` y `08`, de los que figura como responsable.
3. **Votar las decisiones pendientes** (D-05 a D-08) y confirmar D-01, D-03 y D-04.
4. **Validar supuestos con Cofrial**: los de impacto (`01`), los de adopción (`02`), la orden de compra obligatoria y las emociones de los journeys.
5. **Quitar las marcas de borrador** del bloque de título del diagrama de arquitectura.
6. **Carta Gantt y captura del tablero de Trello** como figuras de gestión (`07-metodologia-cronograma.md`).
7. **Referencias:** documento de AWS del Learner Lab, Reglamento Sanitario de los Alimentos (verificar artículos) y las herramientas citadas.
8. **Decidir el nivel de fidelidad** de los mockups: los wireframes cumplen la sección 3 del PDF; si el docente espera mockups de alta fidelidad por el calendario, habría que elevarlos.

## Notas del equipo


## Estado de implementación del Hito 2 (verificado el 22-oct-2026 sobre AWS)

**Tabla 4**
*Exigencias del Hito 2 frente a lo construido y verificado sobre la instalación en AWS Academy*

| Exigencia | Evidencia | Estado |
|---|---|---|
| EC2 y RDS funcionales y estables | `aws/`; instalación creada con `provision.sh`: EC2 web, EC2 IoT y RDS PostgreSQL 16 respondiendo; ver Tabla 3 de `03-arquitectura-cloud.md` | Cubierto |
| E-commerce conectado a la base: catálogo, B2B/B2C, carrito y órdenes | `web/catalogo`, `web/pedidos`; compra B2B y B2C probada sobre AWS; 57 pruebas automáticas | Cubierto |
| CRM: clientes, prospectos y seguimiento de pedidos web | `web/crm`; embudo, interacciones, pedido a nombre del cliente y alertas, probados sobre AWS | Cubierto |
| IoT con Docker, con los 6 campos exactos | `iot/simulador.py`; contenedores en la EC2 dedicada insertando en RDS; tipos correctos y alerta coherente con el rango | Cubierto |
| Dashboard en vivo que cruza ventas con alertas de frío | `grafana/`; 12 consultas con datos reales; ventas por canal B2B y B2C; capturas en `docs/capturas-visual/` | Cubierto |
| IA gratuita integrada, con falla controlada | `web/crm/ia.py`; Gemini con la API real y respaldo Groq; acierto medido de 90 % (18 de 20); detalle en CU-09 | Cubierto, con margen estrecho |

*Nota.* Elaboración propia. La nota la decide el docente; «Cubierto» indica que la evidencia responde al criterio.

**Pendientes del Hito 2:** configurar Groq como respaldo de la IA (aumentaría la disponibilidad), preparar el guion de la defensa y ensayar el apagado y encendido del laboratorio.

**Pendientes del Hito 1** (siguen vigentes, ver sección 5): armar el informe único, la revisión de Sergio sobre 03, 04a, 04b y 08, votar las decisiones D-05 a D-08 y quitar las marcas de borrador del diagrama. Además, `04a-diagrama-arquitectura.md` describe el diseño; las diferencias con lo desplegado están en la Tabla 3 de `03-arquitectura-cloud.md` y deberían reflejarse en el diagrama final.
