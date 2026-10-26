# Cofrial SpA · Del caos operativo a la cadena de frío inteligente

Proyecto de arquitectura y prototipado de transformación digital para **Comercializadora y Frigoríficos Araucanía (Cofrial SpA)**.
INACAP Temuco · Transformación Digital (TIEL15) · Evaluación sumativa EVA2_3.

**Equipo consultor:** Eric Aguayo Quintriqueo · Sergio Vásquez Marimán
**Tablero:** [Trello](https://trello.com/b/yrKII80H/cofrial-spa-transformaci%C3%B3n-digital)

## La solución en una línea
Un ecosistema en AWS que une el **Front-Office comercial** (e-commerce B2B/B2C + CRM + asistente IA) con el **Back-Office logístico** (telemetría IoT de los 50 camiones + dashboard BI), todo sobre una sola base de datos en RDS.

```
 Clientes B2B/B2C ──► E-commerce ─┐
 Vendedores ───────► CRM + IA ────┼──► EC2 (backend) ──► RDS (PostgreSQL) ◄── EC2 IoT (Docker: 50 camiones simulados)
 Gerencia ─────────► Dashboard BI ┘                          ▲
                                                             └── BI lee en vivo ventas × alertas de frío
```

## Avance y calendario actualizado

Al 25-oct-2026 están implementados la aplicación Django, CRM, simulación de cincuenta camiones en cinco contenedores, Grafana, clasificación IA, asistente de tienda, OC diferida, compra dividida por conservación y cierre de viajes. La instalación base tiene registro AWS del 22 de octubre; la revisión actual se verifica por separado.

El cronograma vigente está en `informe/07-metodologia-cronograma.md`, con Gantt y trabajo restante de revalidación, correcciones y defensa. Hito 1: **jueves 05-nov-2026**, fecha del foro adoptada por el equipo. Hito 2: **jueves 12-nov-2026**. Las decisiones implementadas están en `docs/decisiones.md` y las comprobaciones en `docs/revision-hito1-2026-10-25.md`.

### Extras para destacar (después de cumplir lo obligatorio)
- **Torre de control** al estilo WareTrack: mapa con los camiones en vivo, KPIs y panel de detalle (`docs/referencia-waretrack.md`).
- Alertas de ruptura de frío visibles en el CRM, para avisar al cliente afectado.
- Respaldos automáticos de RDS documentados como respuesta al dolor del servidor sin respaldo.

## Qué modelo de Claude usar
Para no gastar tokens de más:

| Tarea | Modelo |
|---|---|
| Mover tarjetas en Trello, renombrar, preguntas rápidas, cambios de una línea | **Haiku 4.5** |
| Programar en el día a día (vistas Django, SQL, Docker), redactar `.md` | **Sonnet 5** |
| Decisiones de arquitectura, diseño del MER 3FN, errores difíciles en AWS, revisión final contra la rúbrica | **Opus 5.5** |

Se cambia con `/model` en Claude Code.

## Código y documentación operativa

| Carpeta / archivo | Contenido |
|---|---|
| `web/` | Aplicación Django (e-commerce, CRM, flota, APIs) |
| `iot/` | Simulador de telemetría (50 camiones en Docker) |
| `aws/` | Compose y scripts para Learner Lab (`aws/README.md`) |
| `informe/` | Secciones del informe del Hito 1 |
| `docs/codigo.md` | Resumen del sistema y arranque local |
| `docs/credenciales-y-cuentas.md` | Dónde viven las claves (sin subirlas a Git) |
| `docs/guia-pruebas-aws.md` | Recorrido de prueba sobre la instalación en la nube |
| `CLAUDE.md` | Contexto para asistentes de código |

## Arranque local (Docker)

El dashboard de BI del proyecto es **Grafana** (no Power BI): consulta PostgreSQL en vivo y cruza ventas por canal con alertas de frío.

```bash
cp .env.example .env   # completar DB_PASSWORD, DEMO_PASSWORD y las tres claves Grafana (ver abajo)
docker compose --env-file .env up -d --build
```

| Servicio | URL local (puertos por defecto) |
|---|---|
| Portal | http://localhost:8000 |
| Grafana | http://localhost:3000 |

Grafana **no admite acceso anónimo**. En `.env` deben estar `GRAFANA_DB_PASSWORD` (usuario SQL de solo lectura), `GRAFANA_PASSWORD` (cuenta **admin**, edita tableros) y `GRAFANA_VISOR_PASSWORD` (cuenta **visor**, solo mirar; la crea el servicio `grafana-visor` al levantar Compose). Detalle en `docs/codigo.md` y `docs/credenciales-y-cuentas.md`.

## Instalación en AWS Academy

Guía completa: **`aws/README.md`**. Tras `bash aws/provision.sh`, las claves quedan en `aws/.estado/secretos.env` (ignorado por git). El tablero publica en `http://IP-ELASTICA:3000`: entrar como **visor** para la demo o **admin** para editar. Si Grafana pide login y las claves no funcionan, quien opera la EC2 web debe completar `GRAFANA_PASSWORD` y `GRAFANA_VISOR_PASSWORD` en `secretos.env` (o en el `.env` de la máquina) y ejecutar `bash aws/provision.sh recrear-web`. Pruebas ordenadas: `docs/guia-pruebas-aws.md`.
