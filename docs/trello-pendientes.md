# Actualización del tablero de Trello (preparada el 22-oct-2026)

Estado de cada tarjeta según lo verificado en `main`. Objetivo: que el tablero muestre **solo lo que falta**. La conexión con Trello estaba caída al preparar este documento, por eso las acciones se listan para aplicarlas a mano.

## 1. Pasar a Hecho (o marcar completas)

| Tarjeta | Evidencia |
|---|---|
| Despliegue cloud: VPC + EC2 + RDS en AWS Academy | Instalación creada con `aws/provision.sh`, verificada de punta a punta; Tabla 10 de `informe/03-arquitectura-cloud.md` |
| Preparar el despliegue: compose de AWS, variables y guion de arranque | `aws/docker-compose.web.yml`, `aws/docker-compose.iot.yml`, `aws/provision.sh` y `aws/README.md` |
| E-commerce: catálogo, perfiles B2B/B2C, carrito y órdenes | Compra B2B y B2C probada sobre AWS; 57 pruebas |
| CRM operativo: clientes, prospectos y seguimiento de pedidos | Probado sobre AWS |
| Simulación IoT con Docker en EC2 dedicada | Contenedores en la EC2 dedicada insertando en RDS los 6 campos exigidos |
| Dashboard BI en tiempo real (ventas x cadena de frío) | 12 consultas con datos reales; ventas por canal B2B y B2C |
| Integración de IA de costo cero (CRM o E-commerce) | Gemini con la API real, acierto 90 % (18 de 20) |
| IA: clasificar requerimientos con Gemini (RN-14) | `web/crm/ia.py`; formulario de Soporte; botón en el CRM |
| Rediseño visual de la app (estilo Fleet Dispatch) + pantalla de Flota | Publicado en `main`; **ya no queda "abrir el PR"** |

## 2. Dejar abiertas, con la descripción actualizada

| Tarjeta | Qué falta |
|---|---|
| Portal: registro de clientes nuevos (B2C) y formulario de requerimientos | Formulario de requerimientos **hecho** (sección Soporte). Falta el registro de clientes B2C y "Mis datos" en `web/` |
| Pruebas integrales y ensayo de la defensa técnica | Pruebas integrales sobre AWS **hechas**. Falta el guion de la demo, repartir quién explica cada parte y ensayar el apagado y encendido del laboratorio (plan B) |
| ENTREGA HITO 2 (Nota 3) + defensa | 12-nov. Preparar la demo: dejar sin clasificar el requerimiento de ejemplo para clasificarlo en vivo con la IA |
| Evaluación de herramientas con criterios ponderados | Validar los puntajes entre ambos; agregado el resultado real de la IA (Tabla 7) |
| 3. Memoria de decisiones de arquitectura cloud | Sergio debe revisarla; agregada la Tabla 10 (diseño frente a lo desplegado) |
| 4a. Diagrama de arquitectura cloud | Reflejar en el diagrama las diferencias de la Tabla 10; quitar "v0.1 borrador"; **subir los diagramas profesionales de Sergio** (ver sección 3) |
| 4b. MER en 3FN + diccionario | Revisión de Sergio y decidir qué versión gana: hay un arreglo ORDEN-CAMION y tablas maestro en un commit local sin subir (sección 3) |
| Metodología: Gantt, Trello, RACI y matriz de riesgos | Generar la carta Gantt y una captura del tablero |
| Integrar, redactar y revisar el informe completo | Armar el informe único; el Word de la carpeta "Entrega Hito 1" puede estar desactualizado frente al informe en `main` (nuevas secciones: Tabla 10, CU-09, estado del Hito 2) |
| Revisión final del informe antes de entregar | Leer páginas 9 a 74 y el anexo; sustituir "prototipo" por el sistema desplegado; actualizar CU-09 a 12 s (**ya está en el informe en markdown, falta en el Word**) |
| ENTREGA HITO 1 (Nota 2) | 04-nov |
| ACTUALIZAR: stack elegido es Django | Sergio confirma Django y Python; cerrar las tarjetas D-01, D-02/03 y D-04; votar D-05; D-06 queda **resuelta en la práctica** (Gemini y respaldo Groq) y D-07/08 también (EC2 y Docker Compose) |
| IMPORTANTE: Reunión, validar criterios ponderados y votar stack | Sigue abierta |

## 3. Tarjetas nuevas a crear

1. **Decidir cuál es la app oficial: `backend/` o `web/`.** Conviven en `main` con modelos distintos. Fecha sugerida antes del 06-nov.
2. **Subir los 4 commits locales de Sergio y resolver conflictos en `informe/04a` y `04b`.** Están solo en la copia local de `main` (diagramas profesionales y el arreglo ORDEN-CAMION). Hay que decidir qué versión del informe gana.
3. **Configurar `GROQ_API_KEY` como respaldo de la IA.** Dos de 20 consultas no tuvieron respuesta de Google; el respaldo sube la disponibilidad.
4. **Respaldar `aws/.estado/secretos.env` fuera de la carpeta de trabajo.** Contiene las claves de la base, de Grafana y de demo.
5. **Destruir los recursos de AWS al terminar la demo** (`bash aws/provision.sh destruir`) para no gastar el crédito del laboratorio.
6. **Investigar el SSH de la EC2 web nueva** (la conexión se reinicia antes del saludo). No bloquea nada hoy.
7. **HTTPS en la instalación de AWS** (opcional): el laboratorio no trae dominio ni certificado; hoy los formularios viajan por HTTP.
