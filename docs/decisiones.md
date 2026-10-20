# Decisiones técnicas

Cada decisión se vota en Trello (lista "Decisiones") y, una vez cerrada, se anota aquí con su trade-off.
Esto alimenta `informe/03-arquitectura-cloud.md`. La evaluación con criterios ponderados está en `informe/08-herramientas.md`.

Criterios: **fácil de aprender para dos personas**, gratis, que funcione en AWS Academy y que sume puntos en la rúbrica.

| # | Tema | Decisión | Alternativas | Estado |
|---|---|---|---|---|
| D-01 | Web (e-commerce + CRM + API) | **Django con plantillas (HTMX y Tailwind)**: ORM con migraciones, autenticación, grupos B2B/B2C y panel de administración como CRM base | React + Django REST Framework (empate técnico) / Next.js / Astro | **Adoptada** el 15-oct (elegida por Claude por delegación de Eric; Sergio debe confirmarla) |
| D-02 | Motor de BD en RDS | **PostgreSQL** | MySQL | Adoptada (sin objeciones; Django y Grafana lo soportan de forma nativa) |
| D-03 | Acceso a datos | **ORM de Django con migraciones**. `informe/modelo/esquema.sql` queda como diseño de referencia validado | SQL directo / Drizzle / Prisma | **Adoptada** el 15-oct, consecuencia de D-01 |
| D-04 | Simulador IoT | **Python en Docker**, `docker compose` con varios contenedores (camiones) | Node/TypeScript en Docker | **Adoptada** el 15-oct, consecuencia de D-01 (un solo lenguaje) |
| D-05 | Dashboard BI | **Grafana** en Docker (gratis, actualización cada 5 s, mapa para `lat`/`long`) + torre de control propia como extra | Metabase (más simple, refresco más lento) / Chart.js propio | Por confirmar |
| D-06 | IA gratuita | **Google Gemini API (free tier)** para clasificar requerimientos y asistente del catálogo | Groq (Llama, free tier) / Hugging Face | Por confirmar |
| D-07 | Despliegue | EC2 Ubuntu + Docker Compose; EC2 IoT aparte; RDS en subred privada | Elastic Beanstalk | Por confirmar |
| D-08 | Extra visual | Torre de control con mapa **Leaflet** (2D, simple) inspirada en WareTrack | Vista isométrica 3D con Three.js (más vistosa, más riesgo) | Por confirmar |
| D-09 | Cuentas de clientes | Inicio de sesión propio sobre la tabla `usuario` (PBKDF2 de Django, límite de intentos, sesión renovada al entrar); registro público solo B2C | `django.contrib.auth` (`auth_user`) | **Adoptada** el 20-oct (prototipo). Mantiene las 25 tablas del MER; si se quiere el panel de administración de Django como CRM, habrá que migrar a `auth_user` |

> El modelo de datos (25 tablas en 3FN) y su script SQL están en `informe/modelo/` (ver `informe/04b-modelo-datos.md`). Con Django, las tablas se generan desde modelos y migraciones con la misma estructura; el script SQL sirve para revisar el diseño y probar consultas.

## Por qué esta combinación
- **Un solo lenguaje (Python)** para web, API, cálculos e IoT: lo que aprende uno le sirve al otro y el simulador comparte herramientas con la aplicación.
- **Django** entrega ORM con migraciones, autenticación, permisos por grupo y un panel de administración. Esas cuatro piezas son justo las que exigen el e-commerce y el CRM, y con otro framework habría que armarlas a mano en cinco semanas.
- **PostgreSQL + Django:** el MER del informe se convierte en modelos y migraciones; Django y Grafana soportan PostgreSQL de forma nativa.
- **Grafana** cumple "en vivo" sin programar gráficos y tiene un panel de mapa que muestra los camiones.
- **Defensa:** si preguntan por qué no React o Next.js, la rúbrica evalúa el negocio, la conexión a la base de datos y la estabilidad del despliegue, no el framework de la vista; Django permitió gastar el tiempo en eso.

## Registro de decisiones cerradas

**D-01 Web: Django con plantillas (15-oct-2026).** Puntaje 4,75 frente a React + Django REST Framework (4,65, empate técnico), Astro (4,35) y Next.js (4,30); ver Tabla 4 de `informe/08-herramientas.md`. Trade-off: se renuncia al ecosistema de React y a una interfaz más rica a cambio de una sola aplicación, menos piezas que desplegar y un panel de administración listo como CRM base. Si más adelante se necesita una interfaz más dinámica, HTMX cubre la mayoría de los casos y la API se puede exponer con Django REST Framework sin rehacer el modelo.

**D-03 Acceso a datos: ORM de Django (15-oct-2026).** Consecuencia de D-01. Las tablas de clave compuesta (`precio_producto`, `carrito_item`, `orden_item`) se implementan con `CompositePrimaryKey` (Django 5.2 o superior) o, si la versión no lo permite, con clave autogenerada más restricción de unicidad sobre el par; ambas mantienen la 3FN. La tabla `usuario` se reemplaza por la autenticación de Django.

**D-04 Simulador IoT: Python en Docker (15-oct-2026).** Consecuencia de D-01: Python es el lenguaje común y los contenedores usan una imagen ligera. Puntaje 4,90 frente a 4,40 de Node/TypeScript; ver Tabla 5 de `informe/08-herramientas.md`.

## Estado de la implementación
El scaffold está en `backend/` (Django 5.2, `psycopg` 3 y `python-dotenv`; configuración por variables de entorno, ver `.env.example`). Aún no hay modelos: el esquema vive en `informe/modelo/esquema.sql`.

> Sincronizado con `informe/03-arquitectura-cloud.md` y `informe/08-herramientas.md` (Tablas 4 y 5: Django 4,75; Python 4,90). Los puntajes son un borrador que Sergio debe validar, sobre todo C3 (facilidad de aprendizaje).
