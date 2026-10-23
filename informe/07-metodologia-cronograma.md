# Metodología, cronograma, gestión en Trello, equipo y riesgos

## Metodología

El equipo adopta Kanban (Anderson, 2010) como método de trabajo diario: el flujo se hace visible en un tablero y el trabajo en curso se limita. Los dos hitos de la pauta funcionan como cierres de iteración, de modo que se toma de Scrum solo la idea de revisar y ajustar en cada uno.

**Tabla 1**
*Enfoques de metodología considerados*

| Enfoque | Fortaleza | Limitación | Decisión |
|---|---|---|---|
| Kanban | Flujo visible y continuo; encaja con un tablero y dos personas | No fija iteraciones | Adoptada para el día a día |
| Scrum | Iteraciones con revisión | Ceremonias costosas para dos personas en cinco semanas | Complementaria: se toman los hitos como "sprints" |
| Cascada | Planificación simple | No absorbe cambios; el Hito 2 depende de aprender en el camino | Descartada |

Nota. Elaboración propia.

## Gestión en Trello

Tablero: https://trello.com/b/yrKII80H/cofrial-spa-transformaci%C3%B3n-digital

**Tabla 2**
*Listas del tablero de Trello y su uso*

| Lista | Uso |
|---|---|
| Inicio del proyecto | Kickoff, roles, herramientas |
| Decisiones (elegir stack) | Alternativas por votar; al cerrarse pasan a `08-herramientas.md` |
| Hito 1 · Informe | Backlog del informe, una tarjeta por sección |
| Hito 2 · Despliegue | Backlog del prototipo |
| En curso / En revisión / Terminado | Flujo Kanban |

Nota. Elaboración propia.

## Herramientas de gestión evaluadas

**Tabla 3**
*Herramientas de gestión evaluadas*

| Herramienta | Fortaleza | Limitación | Decisión |
|---|---|---|---|
| Trello | Gratis, simple, lo conocen ambos, se integra con asistentes de IA | Sin Gantt nativo en el plan gratuito | Adoptada |
| GitHub Projects | Vinculado al código | Menos cómodo para tareas del informe | Complementaria (issues del código) |
| Jira | Muy completo | Curva de aprendizaje alta para dos personas | Descartada |
| Notion | Flexible | Gestión de tareas menos directa | Descartada |

Nota. Elaboración propia.

## Cronograma (base para la carta Gantt)

**Tabla 4**
*Cronograma de actividades*

| Actividad | Responsable | Inicio | Término | Semana |
|---|---|---|---|---|
| Kickoff, roles, herramientas | Ambos | 13-oct | 15-oct | S1 |
| Elección de stack | Ambos | 13-oct | 15-oct | S1 |
| Prueba de EC2 y RDS en el Learner Lab | Sergio | 14-oct | 18-oct | S1 |
| Diagnóstico y BPMN AS-IS | Eric | 16-oct | 20-oct | S1-S2 |
| Propuesta de valor y BPMN TO-BE | Eric | 20-oct | 22-oct | S2 |
| Borrador del MER | Sergio | 19-oct | 23-oct | S2 |
| Esqueleto del proyecto Django | Eric | 21-oct | 25-oct | S2 |
| Evaluación de herramientas y memoria AWS | Sergio | 23-oct | 26-oct | S2-S3 |
| Diagrama de arquitectura | Sergio | 24-oct | 26-oct | S3 |
| MER 3FN final y diccionario | Sergio | 26-oct | 27-oct | S3 |
| Casos de uso, wireframes y journeys | Eric | 26-oct | 29-oct | S3 |
| Pipeline CRM | Eric | 28-oct | 29-oct | S3 |
| Simulador IoT local | Sergio | 27-oct | 1-nov | S3 |
| Integración y revisión del informe | Ambos | 30-oct | 2-nov | S3-S4 |
| Entrega Hito 1 | Ambos | 4-nov | 4-nov | S4 |
| VPC, EC2 y RDS definitivos | Sergio | 5-nov | 6-nov | S5 |
| E-commerce y CRM conectados | Eric | 5-nov | 9-nov | S5 |
| IoT en EC2 dedicada | Sergio | 6-nov | 9-nov | S5 |
| Dashboard BI | Sergio | 9-nov | 10-nov | S5 |
| Integración de IA | Eric | 9-nov | 10-nov | S5 |
| Pruebas integrales y ensayo de defensa | Ambos | 10-nov | 11-nov | S5 |
| Entrega Hito 2 y defensa | Ambos | 12-nov | 12-nov | S5 |

Nota. Elaboración propia. La carta Gantt de la Figura 1 se genera a partir de esta tabla.

**Figura 1**
*Carta Gantt del proyecto*

![Carta Gantt del proyecto](img/gantt.png)

*Nota.* Elaboración propia a partir del cronograma de actividades. El color indica quién es responsable de cada actividad; las líneas rojas marcan los dos hitos de entrega.

## Equipo y matriz RACI

**Tabla 5**
*Matriz de responsabilidades (RACI)*

| Actividad | Eric Aguayo Quintriqueo | Sergio Vásquez Marimán |
|---|---|---|
| Diagnóstico, propuesta y BPMN | R/A | C |
| Casos de uso, canales y CRM | R/A | C |
| Evaluación de herramientas y memoria AWS | C | R/A |
| Diagrama de arquitectura y MER | C | R/A |
| E-commerce, CRM e IA | R/A | I |
| AWS, IoT y BI | I | R/A |
| Revisión final y defensa | R | R/A |

Nota. R: responsable, A: aprueba, C: consultado, I: informado. Elaboración propia.

## Matriz de riesgos

**Tabla 6**
*Matriz de riesgos del proyecto*

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| La sesión del Learner Lab se cierra y detiene las instancias | Alta | Alto | Servicios con reinicio automático; guion para levantar todo en menos de 10 minutos antes de la defensa |
| La IP pública cambia al reiniciar | Alta | Medio | Elastic IP o URL actualizada en el `.env` |
| Solo hay 8 días entre los hitos | Alta | Alto | Adelantar el esqueleto del código y el simulador IoT a las semanas 2 y 3 |
| La API de IA gratuita alcanza su límite | Media | Medio | Manejo de error y una segunda API de respaldo (ver `08-herramientas.md`) |
| Créditos de AWS Academy insuficientes | Baja | Alto | Instancias pequeñas y apagarlas al terminar cada sesión |
| Errores de normalización en el MER | Media | Alto | Revisión cruzada contra la checklist de 3FN antes del 27-oct |
| Imágenes Docker construidas en un Mac con chip Apple no corren en las EC2, que son x86 | Media | Alto | Construir con `--platform linux/amd64` y probar el contenedor antes de desplegar |
| Diferencias entre macOS y Linux: mayúsculas en nombres de archivo, puertos ocupados y versiones de Python o PostgreSQL | Media | Medio | Desarrollar y probar dentro de contenedores con las mismas versiones que en AWS; nombrar los archivos en minúsculas |

Nota. Elaboración propia.
