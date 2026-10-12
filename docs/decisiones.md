# Decisiones técnicas

Cada decisión se vota en Trello (lista "Decisiones") y, una vez cerrada, se anota aquí con su trade-off.
Esto alimenta `informe/03-arquitectura-cloud.md`. La evaluación con criterios ponderados está en `informe/08-herramientas.md`.

Criterios: **fácil de aprender para dos personas**, gratis, que funcione en AWS Academy y que sume puntos en la rúbrica.

| # | Tema | Propuesta recomendada | Alternativas | Estado |
|---|---|---|---|---|
| D-01 | Web (e-commerce + CRM + API) | **Django + plantillas (HTMX y Tailwind)**: ORM con migraciones, autenticación, grupos B2B/B2C y panel de administración como CRM base | React + Django REST Framework (empate técnico) / Next.js / Astro | Por votar (reabierta 12-oct: ver Tabla 4 de `informe/08-herramientas.md`) |
| D-02 | Motor de BD en RDS | **PostgreSQL** | MySQL | Por votar |
| D-03 | Acceso a datos | **SQL directo** (archivos `.sql` = el MER del informe) con la librería `postgres` | ORM Drizzle / Prisma | Por votar |
| D-04 | Simulador IoT | **Node/TypeScript en Docker**, `docker compose` con varios contenedores (camiones) | Python en Docker | Por votar |
| D-05 | Dashboard BI | **Grafana** en Docker (gratis, actualización cada 5 s, mapa para `lat`/`long`) + torre de control propia como extra | Metabase (más simple, refresco más lento) / Chart.js propio | Por votar |
| D-06 | IA gratuita | **Google Gemini API (free tier)** para clasificar requerimientos y asistente del catálogo | Groq (Llama, free tier) / Hugging Face | Por votar |
| D-07 | Despliegue | EC2 Ubuntu + Docker Compose; EC2 IoT aparte; RDS en subred privada | Elastic Beanstalk | Por votar |
| D-08 | Extra visual | Torre de control con mapa **Leaflet** (2D, simple) inspirada en WareTrack | Vista isométrica 3D con Three.js (más vistosa, más riesgo) | Por votar |

> Si D-01 pasa a Django, D-03 (acceso a datos) y D-04 (simulador IoT) deben revisarse: el ORM de Django reemplazaría al SQL directo, y Python pasaría a ser el lenguaje común con el simulador.

## Por qué esta combinación
- **Un solo lenguaje (TypeScript)** para web, API e IoT: lo que aprende uno le sirve al otro.
- **Astro** fue la elección de Eric para la vista; en modo servidor también expone la API, así que no hace falta un segundo proyecto.
- **PostgreSQL + SQL directo:** el MER del informe se convierte tal cual en el script de la BD, y en la defensa se explica sin magia.
- **Grafana** cumple "en vivo" sin programar gráficos y tiene un panel de mapa que muestra los camiones.

## Registro de decisiones cerradas
_(vacío)_
