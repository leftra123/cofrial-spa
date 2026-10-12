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
