# Evaluación de herramientas (criterios ponderados)

> Aporta a H1-D2. Sigue el método de TRAZO: criterios y pesos definidos antes de evaluar, alternativas puntuadas de 1 a 5 y puntaje ponderado.
> Objetivo: dejar argumentado por qué se usan las herramientas que sugiere la pauta (AWS Academy, EC2, RDS, Docker, IA gratuita) frente a sus alternativas, aunque la pauta no exija esta comparación.
> **Estado: borrador.** Los puntajes son una propuesta inicial que el equipo debe validar. Al cerrar una decisión en Trello se actualiza aquí y en `docs/decisiones.md`.

## Criterios

**Tabla 1**
*Criterios de evaluación y ponderación aplicados a todas las decisiones*

| Criterio | Qué mide | Peso |
|---|---|---|
| C1 Cumplimiento de la pauta | Si cumple lo que la pauta exige. Puntaje 2 o menos es eliminatorio: la alternativa se descarta aunque sume más. | 30 % |
| C2 Viabilidad en el plazo | Si se puede construir y probar antes del 12 de noviembre. | 20 % |
| C3 Facilidad de aprendizaje | Esfuerzo para un equipo de dos personas que aprende mientras construye. | 15 % |
| C4 Costo cero | Que no genere gastos fuera de los créditos de AWS Academy. | 15 % |
| C5 Compatibilidad con AWS Academy | Que funcione con los permisos y las restricciones del Learner Lab. | 10 % |
| C6 Escalabilidad y evolución | Que el diseño sirva si Cofrial lo llevara a producción con 50 camiones reales. | 10 % |

*Nota.* Elaboración propia. Cada alternativa se puntúa de 1 a 5 por criterio; el puntaje final es el promedio ponderado.

## Cómputo del backend

**Tabla 2**
*Puntuación ponderada: cómputo del backend*

| Criterio (peso) | Amazon EC2 | Elastic Beanstalk | AWS Lambda | Servidor local |
|---|---|---|---|---|
| C1 Cumplimiento de la pauta (30 %) | 5 | 3 | 2 | 1 |
| C2 Viabilidad en el plazo (20 %) | 4 | 4 | 3 | 3 |
| C3 Facilidad de aprendizaje (15 %) | 4 | 3 | 2 | 3 |
| C4 Costo cero (15 %) | 5 | 5 | 5 | 2 |
| C5 Compatibilidad con AWS Academy (10 %) | 5 | 3 | 3 | 1 |
| C6 Escalabilidad y evolución (10 %) | 4 | 4 | 5 | 1 |
| **Puntaje ponderado** | **4,55** | **3,60** | **3,05** | **1,85** |
| **Decisión** | Adoptada | Descartada | Descartada | Descartada (eliminatorio) |

*Nota.* Elaboración propia.

**Conclusión.** La pauta exige EC2 con el backend persistente. Beanstalk crea EC2 por debajo, pero oculta la configuración que la rúbrica pide justificar (subredes y seguridad). Lambda no es un backend persistente. El servidor local es justamente el dolor que se busca eliminar.

## Base de datos relacional

**Tabla 3**
*Puntuación ponderada: base de datos relacional*

| Criterio (peso) | RDS PostgreSQL | RDS MySQL | PostgreSQL en EC2 | DynamoDB |
|---|---|---|---|---|
| C1 Cumplimiento de la pauta (30 %) | 5 | 5 | 2 | 1 |
| C2 Viabilidad en el plazo (20 %) | 4 | 4 | 3 | 3 |
| C3 Facilidad de aprendizaje (15 %) | 4 | 4 | 3 | 2 |
| C4 Costo cero (15 %) | 5 | 5 | 5 | 5 |
| C5 Compatibilidad con AWS Academy (10 %) | 5 | 5 | 4 | 4 |
| C6 Escalabilidad y evolución (10 %) | 5 | 4 | 3 | 5 |
| **Puntaje ponderado** | **4,65** | **4,55** | **3,10** | **2,85** |
| **Decisión** | Adoptada | Complementaria (alternativa válida) | Descartada | Descartada (eliminatorio) |

*Nota.* Elaboración propia.

**Conclusión.** La pauta exige RDS relacional. PostgreSQL y MySQL quedan casi empatados; PostgreSQL gana por su manejo de datos geográficos y series de tiempo, útiles para la telemetría, y por su integración con Grafana. Instalar la BD en EC2 obliga a gestionar respaldos a mano, que es el dolor original. DynamoDB no es relacional.

## Framework web (e-commerce, CRM y API)

**Tabla 4**
*Puntuación ponderada: framework web (e-commerce, crm y api)*

| Criterio (peso) | Django + plantillas (HTMX y Tailwind) | React + Django REST Framework | Next.js (React y Tailwind) | Astro (modo servidor) |
|---|---|---|---|---|
| C1 Cumplimiento de la pauta (30 %) | 5 | 5 | 5 | 5 |
| C2 Viabilidad en el plazo (20 %) | 5 | 4 | 3 | 3 |
| C3 Facilidad de aprendizaje (15 %) | 4 | 4 | 3 | 4 |
| C4 Costo cero (15 %) | 5 | 5 | 5 | 5 |
| C5 Compatibilidad con AWS Academy (10 %) | 5 | 5 | 5 | 5 |
| C6 Escalabilidad y evolución (10 %) | 4 | 5 | 5 | 4 |
| **Puntaje ponderado** | **4,75** | **4,65** | **4,30** | **4,35** |
| **Decisión** | Adoptada | Complementaria (empate técnico) | Descartada | Descartada |

*Nota.* Elaboración propia. Borrador pendiente de validación del equipo. En C2 se mide también cuánto código hay que escribir: Django trae ORM con migraciones, autenticación, grupos de permisos y un panel de administración; Next.js y Astro obligan a elegir y armar cada una de esas piezas. En C3 se asume que Eric ya trabajó con React y Django REST Framework; la experiencia de Sergio está por confirmar y puede mover este criterio.

**Conclusión.** Django con plantillas (4,75) y React con Django REST Framework (4,65) quedan en un empate técnico. Con Django, el MER en 3FN se convierte directo en modelos y migraciones, y el panel de administración da el CRM base (clientes, prospectos, pedidos) sin escribir interfaz. Python además sirve para los cálculos (listas de precios, mermas, umbrales de cadena de frío) y para el simulador IoT, con un solo lenguaje. React con Django REST Framework conserva esas ventajas del backend (el panel de administración sigue disponible como CRM base) y suma el ecosistema de React; su costo es mantener y desplegar dos aplicaciones, con CORS, autenticación por token y validaciones duplicadas. Si los dos integrantes ya dominan React, esa opción es defendible; si no, Django con plantillas ahorra tiempo. Next.js y Astro quedan atrás porque no traen autenticación, ORM ni panel de administración. El puntaje previo de Astro (4,75) se corrigió: puntuaba alto en plazo y facilidad por ser una elección previa, sin considerar el código que faltaba escribir.

## Simulación IoT

**Tabla 5**
*Puntuación ponderada: simulación iot*

| Criterio (peso) | Docker + Node/TypeScript | Docker + Python | AWS IoT Core | Inserción manual o Excel |
|---|---|---|---|---|
| C1 Cumplimiento de la pauta (30 %) | 5 | 5 | 2 | 1 |
| C2 Viabilidad en el plazo (20 %) | 4 | 5 | 2 | 5 |
| C3 Facilidad de aprendizaje (15 %) | 3 | 5 | 2 | 5 |
| C4 Costo cero (15 %) | 5 | 5 | 4 | 5 |
| C5 Compatibilidad con AWS Academy (10 %) | 5 | 5 | 2 | 5 |
| C6 Escalabilidad y evolución (10 %) | 4 | 4 | 5 | 1 |
| **Puntaje ponderado** | **4,40** | **4,90** | **2,60** | **3,40** |
| **Decisión** | Complementaria (alternativa válida) | Adoptada | Descartada | Descartada (eliminatorio) |

*Nota.* Elaboración propia.

**Conclusión.** La pauta exige contenedores Docker en una EC2 dedicada con inyección automatizada. Con Django adoptado para la web (Tabla 4), Python gana porque web e IoT comparten lenguaje: el equipo aprende una sola herramienta, el simulador usa una imagen ligera de Python y se ahorra mantener una segunda cadena de dependencias. Antes de elegir Django, Node/TypeScript puntuaba más (4,75 contra 4,55) solo por esa misma razón. IoT Core es el servicio de producción, pero no reemplaza el requisito de Docker y sus permisos en el Learner Lab son inciertos. La carga manual baja la nota a 60 %.

## Dashboard de BI

**Tabla 6**
*Puntuación ponderada: dashboard de bi*

| Criterio (peso) | Grafana | Metabase | Gráficos propios (Chart.js) | Amazon QuickSight |
|---|---|---|---|---|
| C1 Cumplimiento de la pauta (30 %) | 5 | 4 | 4 | 3 |
| C2 Viabilidad en el plazo (20 %) | 4 | 5 | 3 | 2 |
| C3 Facilidad de aprendizaje (15 %) | 4 | 5 | 3 | 2 |
| C4 Costo cero (15 %) | 5 | 5 | 5 | 1 |
| C5 Compatibilidad con AWS Academy (10 %) | 5 | 5 | 5 | 1 |
| C6 Escalabilidad y evolución (10 %) | 4 | 3 | 3 | 5 |
| **Puntaje ponderado** | **4,55** | **4,50** | **3,80** | **2,35** |
| **Decisión** | Adoptada | Complementaria | Complementaria (torre de control) | Descartada |

*Nota.* Elaboración propia.

**Conclusión.** Grafana y Metabase quedan casi empatados. Grafana gana en lo que pesa más, la rúbrica: refresco cada pocos segundos ("en vivo") y un panel de mapa para lat/long. Metabase es más simple de armar. Los gráficos propios se reservan para la torre de control. QuickSight es de pago y su disponibilidad en el Learner Lab no está garantizada.

## Servicio de IA de costo cero

**Tabla 7**
*Puntuación ponderada: servicio de ia de costo cero*

| Criterio (peso) | Google Gemini API (free tier) | Groq (free tier) | Hugging Face Inference | OpenAI API |
|---|---|---|---|---|
| C1 Cumplimiento de la pauta (30 %) | 5 | 5 | 4 | 1 |
| C2 Viabilidad en el plazo (20 %) | 5 | 5 | 3 | 5 |
| C3 Facilidad de aprendizaje (15 %) | 4 | 4 | 3 | 4 |
| C4 Costo cero (15 %) | 5 | 5 | 5 | 1 |
| C5 Compatibilidad con AWS Academy (10 %) | 5 | 5 | 5 | 5 |
| C6 Escalabilidad y evolución (10 %) | 4 | 3 | 3 | 5 |
| **Puntaje ponderado** | **4,75** | **4,65** | **3,80** | **3,05** |
| **Decisión** | Adoptada | Complementaria (respaldo) | Descartada | Descartada (eliminatorio) |

*Nota.* Elaboración propia.

**Conclusión.** La pauta exige costo cero. Gemini y Groq ofrecen capas gratuitas con buena calidad en español; Groq queda como respaldo si se alcanza el límite. OpenAI no tiene capa gratuita permanente, por lo que incumple el requisito.

## Diagramas de arquitectura

**Tabla 8**
*Puntuación ponderada: herramienta para el diagrama de arquitectura cloud*

| Criterio (peso) | draw.io | Lucidchart (plan gratuito) | Mermaid | archify (HTML interactivo) |
|---|---|---|---|---|
| C1 Cumplimiento de la pauta (30 %) | 5 | 4 | 2 | 3 |
| C2 Viabilidad en el plazo (20 %) | 5 | 4 | 5 | 4 |
| C3 Facilidad de aprendizaje (15 %) | 4 | 4 | 4 | 4 |
| C4 Costo cero (15 %) | 5 | 2 | 5 | 5 |
| C5 Compatibilidad con AWS Academy (10 %) | 5 | 5 | 5 | 5 |
| C6 Escalabilidad y evolución (10 %) | 4 | 3 | 3 | 3 |
| **Puntaje ponderado** | **4,75** | **3,70** | **3,75** | **3,85** |
| **Decisión** | Adoptada | Descartada | Descartada (eliminatorio) | Complementaria (defensa en vivo) |

*Nota.* Elaboración propia. Borrador pendiente de validación del equipo. En C1 se evaluó si genera un diagrama de topología con los íconos oficiales de AWS, que pide la rúbrica H1-D3. En C5 todas puntúan 5 porque ninguna depende de los permisos del Learner Lab. El puntaje de archify en C1 se verificó probándolo con el mismo diagrama: no incluye íconos oficiales de AWS y solo agrupa por región y Security Group, sin cajas de VPC, subredes ni zonas de disponibilidad. A cambio entrega un HTML interactivo (zoom, modo claro y oscuro, exportar) que pasó sus 9 validaciones de calidad.

**Conclusión.** draw.io gana porque es gratuito, trae la librería oficial de íconos AWS y guarda el diagrama como archivo `.drawio` editable que se versiona en git, de modo que cualquiera del equipo lo corrige sin depender de Claude. Mermaid se descarta por no tener íconos oficiales de AWS, lo que lo deja bajo el mínimo de C1. Lucidchart pierde por el límite de su plan gratuito. archify queda como complemento para animar el flujo en la defensa del Hito 2.

## Síntesis de decisiones

**Tabla 9**
*Resumen de las decisiones adoptadas y sus alternativas descartadas*

| Componente | Adoptada | Alternativa más cercana | Por qué se prefiere |
|---|---|---|---|
| Cómputo | Amazon EC2 | Elastic Beanstalk | Lo exige la pauta y deja visible la configuración de red y seguridad |
| Base de datos | RDS PostgreSQL | RDS MySQL | Datos geográficos, series de tiempo e integración con Grafana |
| Web | Django + plantillas (HTMX y Tailwind) | React + Django REST Framework | ORM, autenticación y panel de administración incluidos; Python para cálculos e IoT |
| IoT | Docker + Python | Docker + Node/TypeScript | Mismo lenguaje que la web (Django) y menos dependencias que mantener |
| BI | Grafana | Metabase | Refresco en vivo y panel de mapa |
| IA | Gemini (free tier) | Groq (free tier) | Calidad en español; Groq queda de respaldo |
| Gestión | Trello | GitHub Projects | Ya en uso; GitHub queda para issues del código |
| Procesos | BPMN 2.0 dibujado en draw.io | Flujograma | Carriles por responsable; mismo programa que el diagrama de arquitectura |
| Diagrama de arquitectura | draw.io (diagrams.net) con íconos oficiales de AWS | archify (HTML interactivo) | Gratis, archivo `.drawio` editable y versionable en git, exporta PNG y SVG |

*Nota.* Elaboración propia.
