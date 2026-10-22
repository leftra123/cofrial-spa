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

## 2026-10-16 (informe en Word)
- Se arma el informe único del Hito 1 en Word con formato APA 7 (`informe/entrega/Informe_Hito1_Cofrial_SpA.docx`) y su versión en PDF: portada, índices, resumen ejecutivo, glosario, 13 secciones, conclusiones, referencias y dos anexos. Se genera con `informe/exportar/exportar-informe.js` a partir de los archivos `.md`.
- Se verifican en línea el artículo 68 del Reglamento Sanitario de los Alimentos y la función `CompositePrimaryKey` de Django 5.2, y se agregan 11 referencias.
- Se genera la carta Gantt desde el cronograma (`informe/img/generar-gantt.py`).

## 2026-10-20 a 2026-10-22
- Rediseño visual de la aplicación (`web/`): barra lateral, tarjetas, chips de estado, filtros con contador en Mis pedidos y CRM unificado. Pantalla de flota con tarjetas por camión, viajes activos y actualización en vivo (API con Django REST Framework y axios). Auditoría con siete roles: se corrigió el menú por rol, las páginas 403 y 404 y el favicon.
- La aplicación convive en el repositorio con `backend/` (portal de otras sesiones); queda por decidir cuál es la oficial. El informe se reconstruyó con una fusión de tres vías entre `main` y las versiones desarrolladas que no estaban en GitHub (secciones 01, 02, 03, 04a, 05 y 06, carta Gantt, íconos de AWS y plan de despliegue); una fusión anterior había dejado en `main` borradores tempranos más cortos de esas secciones.
- IA: clasificación de requerimientos con Gemini (RN-14, CU-09), formulario de Soporte en el portal y botón en el CRM. Medición con la API real: 90 % con Gemini solo y 100 % (20 de 20) con Groq de respaldo. Se corrigió el modelo por defecto, que estaba retirado, y se amplió el tiempo máximo de 5 a 12 segundos.
- Despliegue en AWS Academy con `aws/provision.sh`: VPC, RDS PostgreSQL, EC2 web con IP elástica y EC2 IoT dedicada. Verificación de punta a punta sobre AWS (compras, CRM, flota, tablero de BI e IA). Desviaciones del diseño en la Tabla 3 de `03-arquitectura-cloud.md`.
- Hallazgos del proceso: el terminal del laboratorio usa un rol sin permisos para crear recursos; los parámetros públicos de SSM están bloqueados; Grafana no admite `sslmode=prefer`; un archivo de ejemplo de variables quedaba oculto por el `.gitignore`.
- Decisiones registradas en `docs/decisiones.md` (capa visual, API, IA y despliegue).

## 2026-10-22 (tarde)
- Rotación de claves de la IA: se reemplazó la clave de Gemini por una de la cuenta institucional y se agregó la de Groq. `aws/provision.sh recrear-web` recrea la instancia web con las claves nuevas sin entrar por SSH.
- Al probar Groq con la clave real se corrigieron tres defectos propios: la protección contra bots de Groq bloqueaba el identificador de Python, el modelo de respaldo elegido no existía en la cuenta y un proveedor principal lento dejaba sin tiempo al respaldo. Acierto final: 100 % (20 de 20) con Gemini y Groq de respaldo.
