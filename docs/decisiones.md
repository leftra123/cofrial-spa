# Decisiones técnicas

Cada decisión se vota en Trello (lista "Decisiones") y, una vez cerrada, se anota aquí con su trade-off.
Esto alimenta `informe/03-arquitectura-cloud.md`. La evaluación con criterios ponderados está en `informe/08-herramientas.md`.

| # | Tema | Adoptada | Alternativa descartada | Trade-off |
|---|---|---|---|---|
| D-01 | Web (e-commerce + CRM + API) | Astro en modo servidor (@astrojs/node) | Astro + Express | Un solo proyecto, un solo despliegue, menor curva de aprendizaje |
| D-02 | Motor de BD en RDS | PostgreSQL | MySQL | Datos geográficos, series de tiempo e integración con Grafana |
| D-03 | Acceso a datos | SQL directo con la librería postgres | ORM Drizzle / Prisma | El MER del informe se convierte tal cual en el script de creación |
| D-04 | Simulador IoT | Node/TypeScript en Docker, docker compose | Python en Docker | Un solo lenguaje en todo el proyecto |
| D-05 | Dashboard BI | Grafana en Docker | Metabase / Chart.js propio | Refresco cada 5 s (en vivo), mapa para lat/long, y sin pagar |
| D-06 | IA gratuita | Google Gemini API (free tier) | Groq / Hugging Face | Calidad en español; Groq queda de respaldo si se alcanza límite |
| D-07 | Despliegue | EC2 Ubuntu + Docker Compose; EC2 IoT aparte; RDS privada | Elastic Beanstalk | Lo exige la pauta; deja visible la configuración de red |
| D-08 | Extra visual | Torre de control con mapa Leaflet 2D | Vista isométrica 3D con Three.js | Alcanzable en plazo; 3D solo si lo obligatorio está listo antes del 10-nov |

Nota. Adoptadas por la pauta EVA2_3 y confirmadas por criterios ponderados en `informe/08-herramientas.md`.
