# Bitácora del proyecto

Registro breve de avances y acuerdos (sirve para el informe y la defensa).

## 2026-10-12
- Se crea el tablero de Trello y la estructura del repositorio.
- Equipo: Eric Aguayo Quintriqueo y Sergio Vásquez Marimán.
- Se transcribe la pauta en `00-pauta-y-rubrica.md`.
- Las propuestas de stack quedan para elegir en Trello (lista "Decisiones").

## 2026-10-12 (tarde)
- Se redactan los trade-offs de la memoria de arquitectura (`03-arquitectura-cloud.md`): red, seguridad, cómputo, RDS, IoT, disponibilidad y respaldos, más la tabla de limitaciones del prototipo.
- Se verifican las restricciones del Learner Lab con el documento de AWS (versión 2021).
- D-01 (web) se reabre: Django con plantillas y React + Django REST Framework quedan en empate técnico (Tabla 4 de `08-herramientas.md`).
- Diagrama de arquitectura v0.1 en draw.io (para el informe) y archify (para la defensa).
- Se redacta el MER en 3FN con diccionario de datos (`04b-modelo-datos.md`): 25 tablas, verificación tabla por tabla, desnormalizaciones controladas y reglas de negocio no expresables en el esquema.
- Se corrige una dependencia transitiva detectada al revisar: el cliente de una orden se obtiene por su dirección de entrega (vista `v_orden`), no se guarda en `orden`.
- El esquema se valida en PostgreSQL 16: script, datos de prueba, consultas del dashboard y 13 rechazos de datos inválidos (`informe/modelo/`).

## 2026-10-15
- Se adopta la web en Django con plantillas (D-01), ORM de Django (D-03) y simulador IoT en Python (D-04); se actualizan decisiones, Tablas 4, 5 y 9 de `08-herramientas.md`, README, cronograma y diagramas. Eric delegó la elección a Claude; Sergio debe confirmarla.
- Se redactan los borradores de la dimensión H1-D1: diagnóstico con árbol de problemas, cinco porqués y modelo de impacto (`01`), propuesta de valor con mecanismos y hoja de ruta de adopción (`02`) y seis procesos BPMN AS-IS y TO-BE (`05`).
- Las figuras de D1 se generan con `informe/img/generar-figuras-d1.py`.

## 2026-10-16
- Al diseñar el pipeline del CRM se agregan tres campos al modelo: `prospecto.cerrado_en`, `prospecto.motivo_perdida` y `requerimiento.respondido_en`, sin los cuales no se podía exigir el motivo de pérdida, medir la conversión del mes ni el tiempo de primera respuesta. Se agregan cuatro consultas al dashboard y se revalida el esquema en PostgreSQL.
- Se redactan los borradores de D4: canales (`04c`), CRM (`04d`) y casos de uso (`06`) con wireframes, user journeys, arquitectura funcional, pipeline y especificaciones.
- Se verifica el repositorio contra el PDF original de la pauta (`09-verificacion-pauta.md`): las cuatro dimensiones del Hito 1 tienen contenido que responde al criterio; la brecha principal es armar el informe único.
