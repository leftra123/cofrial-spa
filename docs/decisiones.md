# Decisiones técnicas

Cada decisión se vota en Trello (lista "🗳️ Decisiones") y, una vez cerrada, se anota aquí con su trade-off.
Esto alimenta `informe/03-arquitectura-cloud.md`.

Criterios: **fácil de aprender para dos personas**, gratis, que funcione en AWS Academy y que sume puntos en la rúbrica.

| # | Tema | Propuesta recomendada | Alternativas | Estado |
|---|---|---|---|---|
| D-01 | Web (e-commerce + CRM + API) | **Astro en modo servidor** (`@astrojs/node`): páginas y API en un solo proyecto TypeScript | Astro (front) + Express (API aparte) | 🗳️ por votar |
| D-02 | Motor de BD en RDS | **PostgreSQL** | MySQL | 🗳️ |
| D-03 | Acceso a datos | **SQL directo** (archivos `.sql` = el MER del informe) con la librería `postgres` | ORM Drizzle / Prisma | 🗳️ |
| D-04 | Simulador IoT | **Node/TypeScript en Docker**, `docker compose` con varios contenedores (camiones) | Python en Docker | 🗳️ |
| D-05 | Dashboard BI | **Grafana** en Docker (gratis, actualización cada 5 s, mapa para `lat`/`long`) + torre de control propia como extra | Metabase (más simple, refresco más lento) / Chart.js propio | 🗳️ |
| D-06 | IA gratuita | **Google Gemini API (free tier)** para clasificar requerimientos y asistente del catálogo | Groq (Llama, free tier) / Hugging Face | 🗳️ |
| D-07 | Despliegue | EC2 Ubuntu + Docker Compose; EC2 IoT aparte; RDS en subred privada | Elastic Beanstalk | 🗳️ |
| D-08 | Extra visual | Torre de control con mapa **Leaflet** (2D, simple) inspirada en WareTrack | Vista isométrica 3D con Three.js (más vistosa, más riesgo) | 🗳️ |

## Por qué esta combinación
- **Un solo lenguaje (TypeScript)** para web, API e IoT: lo que aprende uno le sirve al otro.
- **Astro** fue la elección de Eric para la vista; en modo servidor también expone la API, así que no hace falta un segundo proyecto.
- **PostgreSQL + SQL directo:** el MER del informe se convierte tal cual en el script de la BD, y en la defensa se explica sin magia.
- **Grafana** cumple "en vivo" sin programar gráficos y tiene un panel de mapa que muestra los camiones.

## Registro de decisiones cerradas
_(vacío)_
