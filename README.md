# Cofrial SpA · Del caos operativo a la cadena de frío inteligente

Proyecto de arquitectura y prototipado de transformación digital para **Comercializadora y Frigoríficos Araucanía (Cofrial SpA)**.
INACAP Temuco · Transformación Digital (TIEL15) · Evaluación sumativa EVA2_3.

**Equipo consultor:** Eric Aguayo · Sergio Vázquez Marimán
**Tablero:** [Trello](https://trello.com/b/yrKII80H/cofrial-spa-transformaci%C3%B3n-digital)

## La solución en una línea
Un ecosistema en AWS que une el **Front-Office comercial** (e-commerce B2B/B2C + CRM + asistente IA) con el **Back-Office logístico** (telemetría IoT de los 50 camiones + dashboard BI), todo sobre una sola base de datos en RDS.

```
 Clientes B2B/B2C ──► E-commerce ─┐
 Vendedores ───────► CRM + IA ────┼──► EC2 (backend) ──► RDS (PostgreSQL) ◄── EC2 IoT (Docker: 50 camiones simulados)
 Gerencia ─────────► Dashboard BI ┘                          ▲
                                                             └── BI lee en vivo ventas × alertas de frío
```

## Cronograma hacia el "Logrado"

### Semana 1 · 13–18 oct · Arranque
| Tarea | Responsable |
|---|---|
| Kickoff, roles y lectura de la rúbrica | Eric + Sergio |
| Elegir stack (lista "Decisiones" en Trello) | Eric + Sergio |
| Repo, AWS Academy y carpetas | Eric |
| Probar Learner Lab: levantar una EC2 y una RDS de prueba | Sergio |

### Semana 2 · 19–25 oct · Informe: problema y propuesta
| Tarea | Responsable | Dimensión de la rúbrica |
|---|---|---|
| 1. Diagnóstico del dolor | Eric | H1-D1 |
| 2. Propuesta de valor (matriz dolor → solución → indicador) | Eric | H1-D1 |
| Borrador del MER | Sergio | H1-D3 |
| Esqueleto del proyecto web (Astro) | Eric | adelanta H2-D2 |

### Semana 3 · 26 oct–1 nov · Informe: ingeniería
| Tarea | Responsable | Dimensión |
|---|---|---|
| 3. Memoria de decisiones AWS (trade-offs) | Sergio | H1-D2 |
| 4a. Diagrama de arquitectura | Sergio | H1-D3 |
| 4b. MER 3FN + diccionario (final) | Sergio | H1-D3 |
| 4c. Wireframes + user journeys B2B/B2C | Eric | H1-D4 |
| 4d. Pipeline y flujos del CRM | Eric | H1-D4 |
| Simulador IoT funcionando en local | Sergio | adelanta H2-D3 |

### Semana 4 · 2–4 nov · Cierre Hito 1
| Tarea | Responsable |
|---|---|
| Integrar y revisar el informe contra la rúbrica | Eric + Sergio |
| **Entrega Hito 1 — mié 04-nov** | Eric + Sergio |

### Semana 5 · 5–12 nov · Hito 2 (solo 8 días: por eso el código parte antes)
| Tarea | Responsable | Dimensión |
|---|---|---|
| VPC + EC2 + RDS definitivos | Sergio | H2-D1 |
| E-commerce: catálogo, B2B/B2C, carrito, órdenes | Eric | H2-D2 |
| CRM: clientes, prospectos, pedidos | Eric | H2-D2 |
| IoT Docker en EC2 dedicada | Sergio | H2-D3 |
| Dashboard BI en vivo | Sergio | H2-D4 |
| IA gratuita en CRM/e-commerce | Eric | H2-D5 |
| Pruebas integrales y ensayo de defensa | Eric + Sergio | H2-D5 |
| **Entrega Hito 2 + defensa — jue 12-nov** | Eric + Sergio | |

### Extras para destacar (después de cumplir lo obligatorio)
- **Torre de control** al estilo WareTrack: mapa con los camiones en vivo, KPIs y panel de detalle (`docs/referencia-waretrack.md`).
- Alertas de ruptura de frío visibles en el CRM, para avisar al cliente afectado.
- Respaldos automáticos de RDS documentados como respuesta al dolor del servidor sin respaldo.

## Qué modelo de Claude usar
Para no gastar tokens de más:

| Tarea | Modelo |
|---|---|
| Mover tarjetas en Trello, renombrar, preguntas rápidas, cambios de una línea | **Haiku 4.5** |
| Programar en el día a día (páginas Astro, SQL, Docker), redactar `.md` | **Sonnet 5** |
| Decisiones de arquitectura, diseño del MER 3FN, errores difíciles en AWS, revisión final contra la rúbrica | **Opus 5.5** |

Se cambia con `/model` en Claude Code.

## Estructura del repositorio
```
informe/   Secciones del informe del Hito 1 (fuente para la redacción final)
docs/      Decisiones técnicas y referencias
CLAUDE.md  Contexto para Claude Code
```
