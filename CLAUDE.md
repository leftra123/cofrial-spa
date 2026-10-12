# CLAUDE.md

Proyecto académico INACAP Temuco — Transformación Digital (TIEL15), EVA2_3.
Somos una "consultora" que moderniza a **Cofrial SpA** (frigorífico y distribución en cadena de frío, La Araucanía).
Equipo: **Eric Aguayo Quintriqueo** (GitHub `leftra123`) y **Sergio Vásquez Marimán**. Todo se escribe en español.

## Entregas
| Hito | Nota | Fecha | Qué se entrega |
|---|---|---|---|
| 1 | Nota 2 | **mié 04-nov-2026** | Informe de ingeniería: diagnóstico, propuesta, decisiones AWS, diagrama, MER 3FN, wireframes y CRM |
| 2 | Nota 3 | **jue 12-nov-2026** | Prototipo desplegado en AWS Academy + defensa técnica en vivo |

Pauta completa y rúbrica: `informe/00-pauta-y-rubrica.md`. El objetivo es **Logrado (100%) en cada dimensión**.

## Requisitos NO negociables (no se suponen ni se cambian)
- Backend en **EC2**, corriendo de forma persistente, conectado a **Amazon RDS** (BD relacional). Nada que dependa de un PC local.
- E-commerce conectado a la BD: catálogo de refrigerados, perfiles **B2B** (lista de precios institucional) y **B2C**, carrito y generación de órdenes.
- CRM conectado a la misma BD: clientes, prospectos (pipeline) y seguimiento de pedidos web.
- Simulación IoT con **contenedores Docker en un nodo EC2 dedicado**, que inserte automáticamente en la BD estos campos con estos nombres exactos:
  `camion_id` (string), `temp_camara` (float), `lat` / `long` (coordenadas), `combustible_pct` (integer), `alerta_ruptura_frio` (boolean).
- Dashboard BI **en vivo** contra la BD que cruce ventas (por canal) con alertas de ruptura de frío.
- IA externa **gratuita** (free tier) integrada en el CRM o el e-commerce (atención o clasificación de requerimientos).
- Modelo de datos en **3FN** con diccionario.

## Estructura
- `informe/` — un `.md` por sección del informe del Hito 1. Contienen los datos del caso, los criterios para Logrado y lo que vamos decidiendo. **Al cambiar código o decisiones, actualizar el `.md` correspondiente** para que el informe nunca se quede sin información.
- `docs/decisiones.md` — registro de decisiones técnicas (stack, trade-offs). Fuente para `informe/03-arquitectura-cloud.md`.
- `docs/referencia-waretrack.md` — inspiración visual de la torre de control (proyecto visto en Threads; es material de terceros y no se publica).
- `app/` — material de referencia privado (ignorado por git). **No** es la carpeta de código.
- El código irá en carpetas propias cuando se cierre el stack (ver `docs/decisiones.md`).

## Forma de trabajo
- Tablero Trello: https://trello.com/b/yrKII80H/cofrial-spa-transformaci%C3%B3n-digital
- Antes de cada tarea, recomendar el modelo de Claude adecuado para no gastar tokens de más (ver `README.md` → "Qué modelo usar").
- Nunca subir credenciales: usar `.env` (ignorado) y dejar un `.env.example`.
