# Pauta y rúbrica (transcripción del PDF del profesor)

**Asignatura:** Transformación Digital (TIEL15) · INACAP Sede Temuco
**Evaluación:** Sumativa integral (Nota 2 y Nota 3) — Proyecto de Arquitectura y Prototipado de Transformación Digital Operativa (Unidad 02)
**Modalidad:** grupal, máximo 4 integrantes.

## Calendario
- **Hito 1 (Nota 2) — miércoles 04-nov-2026:** informe de ingeniería, diagnóstico del dolor, decisiones de arquitectura cloud, modelado de datos (E-commerce + CRM + IoT) y mockups de canales digitales.
- **Hito 2 (Nota 3) — jueves 12-nov-2026:** despliegue funcional en AWS Academy, e-commerce con carrito, CRM operativo, simulación IoT con Docker y dashboard BI.

## El caso: Cofrial SpA
Comercializadora y Frigoríficos Araucanía. Más de 30 años en La Araucanía. Procesa, almacena en frío y distribuye cárnicos, perecibles e insumos refrigerados a hospitales, supermercados, ferias y clientes institucionales de la macrozona sur. Arrastra una deuda tecnológica que la tiene "al borde de la quiebra técnica" frente a competidores digitalizados.

### Los tres focos críticos
1. **Infraestructura on-premises vulnerable y silos.** Un único servidor físico en una bodega central, sin redundancia eléctrica ni respaldos automatizados. Contabilidad usa un sistema cerrado; bodega y operaciones controlan existencias en planillas Excel locales e incomunicadas → discrepancias de inventario permanentes.
2. **Caos de última milla y Shadow IT extrema.** 50 camiones frigoríficos sin GPS en tiempo real ni registro automático de temperatura. Rutas y carga coordinadas por llamadas y grupos de WhatsApp personales → alta tasa de entregas fallidas y pérdidas millonarias semanales por mermas al romperse la cadena de frío sin que nadie lo note.
3. **Sin canales digitales ni CRM.** No hay sitio transaccional ni portal de atención. Pedidos institucionales por teléfono o correos desordenados. Los vendedores manejan la cartera en sus teléfonos personales, sin embudo de ventas ni métricas de conversión.

### Misión
Como consultora de ingeniería de software y cloud: diseñar, estructurar y prototipar un ecosistema equilibrado entre el **Front-Office comercial (E-commerce + CRM)** y el **Back-Office logístico-cloud (AWS + IoT + BI)**.

## Hito 1 — contenido obligatorio del informe
1. **Diagnóstico y análisis del dolor:** desglose analítico de on-premises, colapso de última milla por Shadow IT y ausencia de canales digitales.
2. **Propuesta de valor y resolución de conflictos:** cómo la arquitectura Front-Office + Back-Office ataca cada dolor y erradica los pedidos por WhatsApp y el papel.
3. **Memoria y decisiones de arquitectura cloud (trade-offs):** por qué EC2, RDS, y las decisiones de subredes, VPC y seguridad.
4. **Ingeniería gráfica y modelamiento:**
   - Diagrama de arquitectura cloud (topología completa de red y servicios).
   - MER en 3FN + diccionario (transacciones E-commerce/CRM + telemetría IoT).
   - Arquitectura de canales y flujos CRM: wireframes y user journeys del portal (perfiles B2B y B2C) y estados del pipeline del CRM.

## Hito 2 — exigencias prácticas
- **AWS Academy:** EC2 con el backend corriendo de forma persistente, conectado a RDS.
- **E-commerce:** conectado a la BD en la nube; catálogo de refrigerados, perfiles B2B (precios institucionales) / B2C, carrito y generación de órdenes.
- **CRM:** gestión de clientes, prospectos y seguimiento de los pedidos de la web.
- **IoT con Docker en EC2 (nodo dedicado):** inyección automatizada a la BD de `camion_id` (String), `temp_camara` (Float), `lat` / `long`, `combustible_pct` (Integer), `alerta_ruptura_frio` (Boolean, true si excede el rango crítico).
- **BI + IA (costo cero):** dashboard en tiempo real que cruce métricas comerciales (ventas, pedidos por canal) con alertas de cadena de frío; IA externa gratuita integrada en CRM o e-commerce para atención o clasificación de requerimientos.

## Rúbrica — qué exige "Logrado (100%)"
Medianamente logrado = 60 %. No logrado = 0 %.

### Hito 1
| Dim. | Criterio | Logrado (100%) | Trampa que baja a 60% |
|---|---|---|---|
| D1 | Diagnóstico del dolor y justificación | Analiza en profundidad y argumenta con solidez técnica **y de negocio** cómo la solución neutraliza **cada** dolor | Repetir el caso sin análisis crítico |
| D2 | Decisiones de arquitectura cloud | Justifica con rigor VPC, subredes, seguridad, cómputo y RDS, **argumentando trade-offs** | Listar servicios AWS de forma teórica sin razones ni coherencia con el caso |
| D3 | Topología cloud y MER 3FN | Diagrama profesional + MER rigurosamente normalizado para transacciones **y** telemetría IoT | Errores de normalización o diagramas desconectados de la realidad |
| D4 | Arquitectura de canales y CRM | User journeys avanzados B2B/B2C + arquitectura funcional del CRM **que erradica el Shadow IT** | Describir el sitio o CRM sin flujos ni lógica de negocio |

### Hito 2
| Dim. | Criterio | Logrado (100%) | Trampa que baja a 60% |
|---|---|---|---|
| D1 | Despliegue AWS Academy | EC2 y RDS funcionales, estables y conectados en la nube | Servicios inestables, sin conectividad persistente o dependientes de local |
| D2 | E-commerce y CRM | Sitio con carrito, pedidos B2B/B2C y CRM conectados a la BD en la nube | Maquetas HTML estáticas o ventas desconectadas de la BD central |
| D3 | IoT con Docker en EC2 | Contenedores que inyectan automáticamente los parámetros exigidos | Datos estáticos, Excel o inserciones manuales |
| D4 | Dashboard BI | Panel conectado en vivo que cruza ventas con cadena de frío | Gráficos estáticos o métricas aisladas |
| D5 | IA (costo cero) y defensa | API pública de IA funcionando + demostración sólida en vivo | Fallas críticas en la demo o vacíos conceptuales en la defensa |
