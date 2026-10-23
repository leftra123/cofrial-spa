# 2. Propuesta de valor y resolución de conflictos

> Rúbrica H1-D1 (Logrado): demostrar cómo la arquitectura **neutraliza cada dolor**, erradicando los pedidos por WhatsApp y el papel.
> **Estado: borrador de redacción**, pendiente de validación del equipo. Las cifras de beneficio son supuestos ilustrativos que se apoyan en los de `01-diagnostico.md`.

## Propuesta de valor en una frase

Cofrial pasa de operar a ciegas con datos dispersos a operar con **un dato único y en línea**: cada pedido nace en un canal propio, cada camión informa su temperatura y su posición, y cada cliente y prospecto queda registrado en la empresa y no en un celular.

## La solución en dos frentes

La propuesta equilibra un Front-Office comercial, que captura la demanda, con un Back-Office logístico y cloud, que protege los datos y vigila la operación. Ambos escriben y leen de la misma base de datos, que es lo que elimina los silos.

**Tabla 1**
*Componentes de la solución y el dolor que ataca cada uno*

| Frente | Componente | Qué hace | Dolor que ataca |
|---|---|---|---|
| Front-Office | E-commerce B2B/B2C | Catálogo con precio según perfil, carrito y órdenes | Pedidos por teléfono y correo |
| Front-Office | CRM | Clientes, prospectos, embudo y seguimiento de pedidos web | Cartera en celulares, sin métricas |
| Front-Office | IA gratuita | Clasifica requerimientos y asiste en el catálogo | Atención lenta y desordenada |
| Back-Office | AWS (EC2 y RDS) | Aplicación persistente y base de datos con respaldos automáticos | Servidor único sin respaldo |
| Back-Office | IoT con Docker | Telemetría de los camiones (temperatura, posición, combustible) | Última milla a ciegas |
| Back-Office | Dashboard BI | Cruza ventas por canal con alertas de cadena de frío | Decisiones sin datos |

*Nota.* Elaboración propia.

## Matriz dolor, causa raíz, solución e indicador

**Tabla 2**
*Cómo la arquitectura neutraliza cada dolor, con su evidencia en el prototipo y su indicador*

| Dolor | Causa raíz (`01-diagnostico.md`) | Componente que lo resuelve | Cómo se demuestra en el Hito 2 | Indicador sugerido |
|---|---|---|---|---|
| Servidor único sin respaldo | Sin arquitectura que proteja el dato | EC2 + RDS con respaldos automáticos | Aplicación y base de datos corriendo en AWS | Disponibilidad; tiempo de recuperación |
| Excel incomunicados | Sin fuente oficial del dato | Una sola base de datos para ventas, inventario y logística | Una orden web descuenta stock y se ve en el CRM | Diferencias de inventario |
| Camiones sin trazabilidad | La flota no emite datos | IoT: `lat` y `long` cada pocos segundos | Mapa con la posición en vivo | Porcentaje de entregas a tiempo |
| Ruptura de frío no detectada | La temperatura no se mide | IoT: `temp_camara` y `alerta_ruptura_frio` | Alerta visible en el dashboard apenas ocurre | Mermas por ruptura de frío |
| Coordinación por WhatsApp y llamadas | Único canal conversacional | Dashboard y CRM como canal oficial | Pedido y estado visibles en el CRM | Pedidos fuera del sistema |
| Pedidos por teléfono o correo | Sin punto de entrada propio | E-commerce B2B/B2C | Flujo catálogo, carrito y orden | Pedidos digitales sobre el total |
| Cartera en celulares | El conocimiento es de la persona | CRM con embudo | Un prospecto avanza de etapa en el CRM | Tasa de conversión |
| Atención lenta | Mensajes sin clasificar | IA gratuita (clasificación) | Un requerimiento se clasifica solo | Tiempo de primera respuesta |

*Nota.* Elaboración propia.

## Cómo se erradican los pedidos por WhatsApp y el papel

Quitar una herramienta informal no basta si las personas siguen necesitándola. La propuesta combina cinco mecanismos, de modo que usar la plataforma sea más cómodo que el canal informal:

**Tabla 3**
*Mecanismos para sustituir los canales informales*

| Mecanismo | Qué cambia | Control |
|---|---|---|
| Un solo punto de entrada | Todo pedido nace en el portal o lo ingresa el vendedor en el CRM | Pedidos fuera del sistema |
| Estado visible y en línea | El cliente y el vendedor consultan el pedido sin llamar ni escribir | Consultas de estado por canales informales |
| Alertas automáticas | El despachador se entera por el sistema y no por un llamado del conductor | Tiempo entre la ruptura y la acción |
| Cuentas institucionales | Cada interacción queda ligada a una cuenta de la empresa y no a un teléfono personal | Interacciones registradas en el CRM |
| Regla de gobierno | "Un pedido que no está en el sistema no existe": no se prepara ni se despacha | Cumplimiento por área |

*Nota.* Elaboración propia.

## Beneficios cuantificados con supuestos explícitos

Siguiendo el modelo de `01-diagnostico.md` (escenario base: 5 % de viajes con ruptura, 15 viajes afectados por semana, 22,5 millones de pesos de pérdida semanal), se estima cuánto cambia si el despachador recibe la alerta a tiempo. El parámetro nuevo es la proporción de rupturas en que el despachador alcanza a actuar (desviar, reprogramar o cambiar de camión).

**Tabla 4**
*Ahorro semanal según la capacidad de reacción ante la alerta (ilustrativo)*

| Rupturas en que se alcanza a actuar | Pérdida semanal con la plataforma | Ahorro semanal |
|---|---|---|
| 40 % | 13,5 millones de pesos | 9,0 millones de pesos |
| 60 % | 9,0 millones de pesos | 13,5 millones de pesos |
| 80 % | 4,5 millones de pesos | 18,0 millones de pesos |

*Nota.* Elaboración propia. Pérdida actual de referencia: 22,5 millones de pesos semanales (Tabla 6 de `01-diagnostico.md`). Todos los valores son ilustrativos y se reemplazan con datos reales de Cofrial.

El costo de la solución se calcula en una etapa posterior; el prototipo se construye con los créditos de AWS Academy, por lo que no genera gasto. Para una operación real habría que estimar el costo mensual de las instancias, la base de datos, los sensores y el desarrollo, y compararlo con el ahorro del escenario que la empresa considere realista.

## Alcance y límites de la propuesta

Declarar los límites forma parte de la defensa:

- **Contabilidad.** El sistema contable cerrado no se integra en el prototipo. La ruta propuesta es exportar las ventas desde la base de datos central (archivo plano) como primer paso, y evaluar una integración directa cuando el proveedor lo permita.
- **IoT simulado.** Los datos de telemetría son sintéticos. En producción los camiones llevarían sensores con una pasarela hacia la base de datos, y la inserción directa a la base se reemplazaría por una API de ingesta (ver `03-arquitectura-cloud.md`).
- **Seguridad.** El prototipo expone HTTP porque no hay dominio propio; en producción corresponde HTTPS.
- **Cambio cultural.** La tecnología no cambia hábitos por sí sola; por eso se incluye una hoja de ruta de adopción.

## Hoja de ruta de adopción

**Tabla 5**
*Fases de adopción propuestas para Cofrial*

| Fase | Qué ocurre | Criterio para avanzar |
|---|---|---|
| 0. Preparación | Cargar clientes, productos y precios; definir rangos de temperatura; capacitar | Datos maestros cargados y revisados |
| 1. Piloto | Dos vendedores y cinco camiones operan solo con la plataforma, en paralelo con el método actual | Cero pedidos del piloto fuera del sistema durante dos semanas |
| 2. Extensión | Se suman el resto de los vendedores y la flota completa | Porcentaje de pedidos digitales sobre el total por encima del umbral acordado |
| 3. Cierre de canales informales | Los pedidos por WhatsApp y teléfono se redirigen al portal o al vendedor en el CRM | Pedidos fuera del sistema cercanos a cero |

*Nota.* Elaboración propia. Los umbrales se acuerdan con la gerencia de Cofrial.

**Riesgos de adopción y su mitigación**

**Tabla 6**
*Riesgos de adopción por grupo de usuarios*

| Grupo | Riesgo | Mitigación |
|---|---|---|
| Vendedores | Resisten entregar su cartera personal | La cartera se asigna a su nombre en el CRM; los indicadores y las comisiones se calculan sobre lo registrado |
| Conductores | Ven el sensor como vigilancia | Comunicar que protege la carga y a ellos ante reclamos injustos; datos de uso acotado |
| Clientes institucionales | Prefieren seguir llamando | Durante la transición el vendedor ingresa el pedido en su nombre; el portal se muestra como una ventaja |
| Contabilidad | Mantiene la doble digitación | Exportación periódica desde la base central como primer paso |

*Nota.* Elaboración propia.

## Pendiente

- [ ] Validar con Cofrial los supuestos de beneficio y los umbrales de adopción.
- [ ] Estimar el costo mensual de una operación real, para completar la comparación costo y beneficio.
- [ ] Revisar la redacción final con la skill `informe-apa7-tecnico`.

## Notas del equipo
