# Sesiones previas (consulta del orquestador, 25-oct-2026)

> Archivo local de trabajo: **no se commitea ni se sube** (decisión de Eric: `docs/` no se publica).
> Fuente: transcripciones de las sesiones (`list_events`, `search_session_transcripts`), `git log`, ramas locales y `gh issue list`. Solo se cuentan sesiones del proyecto Cofrial.

## 1. Sesiones y su estado

| Sesión | Tema | Qué decidió / dejó hecho | Pendiente | Rama / PR |
|---|---|---|---|---|
| Rediseño visual WareTruck (**corriendo**) | Integrador: ciclo de entrega («Estamos afuera», «Entrega no concretada»), desglose IA, fusión con `main` | Integró `ia-ciclo-entrega` (03b55d9) + `main` (PR #21, #25, #26 y Dependabot). Suite completa OK, 17 pruebas del simulador OK | Repetir ciclo con simulador real, **push y despliegue a AWS** (espera visto bueno de Eric, lab encendido y credenciales nuevas); clave de admin por confirmar | `ciclo-entrega` (7 commits fuera de `main`, incluye un «WIP… no desplegar») |
| Uso de IA en el proyecto | Coordinó a «Mejora visual» para el desglose IA y la campanita | 252/252 pruebas en `ia-ciclo-entrega` | Visto bueno de Eric en la sesión WareTruck | `ia-ciclo-entrega` |
| Mejora visual integral | Ejecutó los cambios de IA/campanita para la anterior | Commit encima de 02bc335 | En espera; la campanita tras el cambio no se vio en navegador | `claude/mejora-visual-integral-313c98` |
| Contradicciones en informe de despliegue | Lista de Sergio; Grafana sin acceso anónimo; prompt del orquestador | Tabla 3 de `03` actualizada; cuenta `visor` (commit 53af84b) | **53af84b no está en `main` ni en `ciclo-entrega`**; no desplegado | `claude/deployment-report-contradictions-1b3ccc` (sin push) |
| Revisión de evaluación PDF | Revisión contra la pauta; fusionó todos los PR | PR #21, #25, #26, #34 y Dependabot #28–#33 en `main`; Django 6.1.2 probado con 199 pruebas | Guion de defensa, D-05 a D-08 y matriz en commit propio sin push; no reconstruyó imágenes ni desplegó | `claude/revision-evaluacion-pdf-c9db5c` (dbf688a, sin push) |
| Revisión de CVEs | Parches, contenedores sin root, SECRET_KEY obligatoria, Dependabot | PR #27 fusionado | Grafana 11.6 antigua (pasar a 12.x a futuro) | fusionada |
| Seguridad en tests | 74 pruebas, bloqueo tras 5 claves malas, 503 si cae la BD, `DJANGO_ADMIN_URL`, corrige redirección abierta | Commit 839eac1 | **Sin fusionar**; base muy antigua (antes de `catalogo/0003` y `pedidos/0003`) | `claude/test-security-review-0897e3` (sin push) |
| Documentos y pagos en CRM | Boleta, factura, guía, nota de crédito, pagos, cobranza; RN-16 a RN-21; MER pasa a 27 tablas | Commit e705f43 | **Sin fusionar**; su migración `pedidos/0004` choca con `pedidos/0004_ciclo_entrega` | `claude/crm-documents-payments-4a7a2b` (sin push) |
| Iconos y logo con camión | Logo con borde en PNG, login y portada | Commit 4e6b904 | `logo-horizontal-borde.png` no está en `main` ni en `ciclo-entrega`; no se vio en navegador | `claude/cofrial-icons-logo-truck-a3b00e` (sin push) |
| Opción visual (impeccable) | Termómetro en CRM y flota | Commit 7cb98e4 | Probablemente superada por PR #22 (fase 6) y #25 (fase 7): confirmar | `claude/impeccable-visual-option-b733ec` |
| Rediseño del frontend / fases 0–7, crítica P1–P2 | Dirección «Termómetro», rendimiento, catálogo, carrito, seguimiento, CRM, flota, demo | Fusionado (PR #9, #15, #16, #20, #22, #25, #26) | — | fusionadas |
| Mejorar rutas con estados | Vacío, carga, error, sin conexión, confirmación | PR #23 fusionado | — | fusionada |
| Camión pasa de largo / discrepancia 3 vs 50 | Simulador va a la dirección; 50 camiones en 5 contenedores | PR #17 y #8 fusionados | `aws/verificar.py` exige 50 camiones; AWS no reverificado | fusionadas |
| Asignar tarea a Sergio | Issues #4–#7 con ramas `sergio/*` | Comentarios con pasos | Issues #4, #5, #6, #7 y #18 **abiertos** | — |
| Dominio en AWS sin costo | Route 53 descartado; usar DNS público de EC2 o DuckDNS/sslip.io | Queda IP | HTTPS sigue sin resolver | — |
| Cambios de temperatura en sitios | El cliente ve temperatura solo con pedido en camino | Recomendó revisar si el cliente debe ver combustible | Decisión sobre ocultar combustible | — |
| Opciones de estado en Trello / Revisión de skills | Tablero y plugins | Aplicado | — | — |

## 2. Contradicciones y conflictos detectados

| # | Conflicto | Evidencia | Qué hace falta |
|---|---|---|---|
| C1 | WareTruck va a desplegar `ciclo-entrega`, que **no trae** Grafana sin acceso anónimo | 53af84b solo en su rama; `git merge-base` | Fusionar 53af84b antes del despliegue o desplegar dos veces |
| C2 | Dos migraciones `pedidos/0004` distintas | `0004_ciclo_entrega` vs `0004_documentos_pagos` | Elegir si entra documentos y pagos; renumerar |
| C3 | RN-09 tiene dos significados | `04d` y `crm/servicios.py`: cartera por vendedor; `docs/decisiones.md`: dividir pedidos mixtos | Renumerar la regla de pedidos mixtos |
| C4 | Servidor web: el texto dice nginx, lo desplegado no | `03:59` y `04e:20` dicen «gunicorn detrás de nginx»; Tabla 3 de `03:151` dice sin nginx | Corregir 03 y 04e |
| C5 | Respaldos | `03:103` y `04e:53` prometen snapshot manual; Tabla 3 dice que `destruir` no toma snapshot final | Alinear texto o agregar snapshot al script |
| C6 | Acceso remoto | `03:51` Session Manager; Tabla 3: SSH con llave | Alinear |
| C7 | Cifras viejas | `09:88` y `guia-pruebas-aws.md:91` «57 pruebas» (hoy 199 en `main`, 252 en `ciclo-entrega`); `guia-pruebas-aws.md:62` «tres camiones» (hoy 50); `docs/codigo.md` dice Django 5.2, IA y AWS «Pendiente» | Barrido de cifras |
| C8 | AMI por SSM | `aws/README.md:25` supone parámetro público de SSM; la bitácora dice que está bloqueado | Revisar qué hace `provision.sh` hoy |
| C9 | D-05 a D-08 «Por confirmar» en `main` | La sesión de revisión PDF los dejó al día en una rama sin push | Fusionar dbf688a |
| C10 | Clave de demostración | `decisiones.md` (24-oct): «todas comparten una clave fácil, en el Anexo B»; commits d98dec8 y 0f2ecf9: sin clave por defecto, se genera al azar, ADMIN_PASSWORD aparte | Confirmar qué dice hoy el Anexo B y que no publique la clave |
| C11 | Seguridad sin fusionar | 839eac1 cubre límites de intentos y caídas de BD; `main` no lo tiene | Decidir si entra antes de la defensa (rebase grande) |
| C12 | `docs/` es evidencia del informe | `09` cita `docs/capturas-visual/`; `03`/`08` citan `docs/decisiones.md`; 39 archivos de `docs/` están versionados | Si `docs/` no se sube, mover la evidencia citada a `informe/` o dejar de citarla |
| C13 | Borradores | `03:12` y `04a:4` «Estado: borrador de redacción»; `04a:59` marca v0.1 pendiente | Quitar antes del 04-nov |

## 3. Actualización 25-oct-2026 (tarde)

- `origin/main` ya trae `ciclo-entrega` (merge 0b2c8a4, incluye 03b55d9 y el commit «WIP… no desplegar» 579c1a6) y el PR #35 (puertos configurables). Siguen fuera: 53af84b (Grafana `visor`), dbf688a, 839eac1, e705f43, 4e6b904, 7cb98e4.
- Eric autorizó a WareTruck un despliegue único (recrear-web y recrear-iot, migraciones, clave de admin nueva, verificación en AWS). El orquestador le pidió detenerse antes del paso 3 y reportar suite, si incluye 53af84b y qué migraciones aplica.
- **El guion de la defensa es solo local** (decisión de Eric): `docs/guion-defensa.md` de dbf688a no se sube.
- Avisados como orquestador: WareTruck, Mejora visual, Uso de IA, Contradicciones, Revisión PDF, Seguridad en tests, Documentos y pagos, Iconos y logo, Opción visual. No se avisó a las sesiones ya fusionadas y sin trabajo abierto.

## 4. Despliegue del 25-oct-2026 (informe de WareTruck, sin verificar por el orquestador)

- Desplegado en AWS: `main` 0b2c8a4, con el «sí, despliega todo con los 3 PR» que Eric le dio en su chat, antes del aviso del orquestador. Suite: 260/260 y simulador 17/17, ambas corridas **después** del push. Migraciones aplicadas sobre RDS: flota 0003, pedidos 0004 y 0005. La web estuvo caída unos 3 minutos.
- NO incluye: 53af84b (Grafana sigue con acceso anónimo en AWS), el commit de seguridad de Mejora visual ni los 403 de gerencia y del personal. Estos últimos están en una rama nueva sin push.
- `verificar.py --ia`: 34 de 35; falla `sergio@` (rechaza la clave de demostración).
- Publicado sin querer: `docs/ciclo-entrega.md` en `origin/main`. Además, desde antes, `docs/referencia-waretrack.md` está en GitHub, aunque `CLAUDE.md` dice que es material de terceros y no se publica.
- No hay claves literales en los `docs/` publicados ni en el Anexo B (revisado con las claves enmascaradas).

## 5. Respuestas tras el despliegue (25-oct-2026, noche)

- Clave de admin: aplicada a `admin@` y `eric@` **antes** del despliegue, con las 4 combinaciones probadas ese día; después del despliegue solo se comprobó que la nueva entra.
- Sin comparación antes/después de cuentas, órdenes, productos ni stock. Evidencia indirecta: las secuencias de orden (14 → 17–19) y de despacho (7 → 9–11) siguieron. Se pidió una línea base ahora para el próximo despliegue.
- Sin hacer: barrido de 30 GET, pantallas del cliente y del despacho en navegador, mapa antes de salir en AWS, registros de las EC2, reinicio del simulador a mitad de un viaje, reprogramación de una entrega no concretada, `sergio@`.
- Rama `navegacion-por-rol` (Mejora visual, cbb6358 + 8652231 con `docs/rutas-y-roles.md` aparte): menú y destino de inicio por rol, `/admin/` solo superusuario, 267/267, sin push.
- Redirección de `POST /avisos/pedir/` sin corregir en `main` ni en AWS. El guardia actual (`startswith("/")` y no `//`) se salta con `/\`. Severidad baja: requiere un POST con token CSRF válido. La corrige 839eac1.
- Gerencia puede armar despachos y reubicar direcciones (`POST /flota/despachar/` y `/ubicar/<id>/`), aunque el informe la deja en solo lectura.

## 6. Línea base en AWS (25-oct-2026, después del despliegue; archivo `linea_base.json` en el scratchpad de WareTruck)

Cuentas 11 (vendedores 2, gerencia 1, despachadores 1, el resto administradores y clientes); clientes 6; órdenes 19 (Entregada 14, Cancelada 3, Recibida 1, Entrega no concretada 1); productos 20; stock total 116 unidades, con varios productos en 0; camiones 50; requerimientos 19, de ellos 1 sin clasificar.

**Riesgo para la defensa:** con el stock agotado, una compra en vivo puede fallar. Reponer el stock forma parte del checklist previo a la defensa (línea F).

## 7. Preparación del segundo despliegue (25-oct-2026, noche)

- Simulación de fusiones con `git merge-tree` sobre `origin/main`: 53af84b sin choques; `navegacion-por-rol` sin choques; 839eac1 choca en 8 archivos (`docs/decisiones.md`, `cofrial/settings.py`, `crm/servicios.py`, `crm/views.py`, `pedidos/servicios.py`, `pedidos/views.py`, `templates/base.html`, `templates/tienda/base.html`).
- Los 403 de WareTruck **todavía no existen** (su worktree está limpio en `ciclo-entrega`).
- Ningún commit del paquete toca `iot/` ni trae migraciones: alcanza con `recrear-web` y no hace falta `recrear-iot`.
- El estado de AWS (`aws/.estado/`) solo está en el worktree de WareTruck: el despliegue lo ejecuta esa sesión.
- 839eac1: bloqueo tras 5 claves malas por cuenta o 20 por IP, durante 15 min; barrido de 404 con 429 por 5 min. En la defensa, toda la sala sale por la misma IP pública: riesgo de bloquear a todos.
- La línea base de stock parece mal leída (los valores coinciden con los kg del SKU). Se pidió volver a medirla con el ORM.
- `04d` no tiene una fila de «Flota / armar despacho» en la tabla de permisos: hay que agregarla con el 403 de gerencia.

## 8. Correcciones (25-oct-2026, noche)

- Stock real en AWS, medido por columna en la administración de productos: total 1333. En 0: MAR-CAM-1K (intencional) y PAV-PEC-5K (semilla 55). Bajo: COR-PIE-6K = 1 (semilla 8). El «116» era un error de lectura.
- Commit de seguridad de Mejora visual: el hash real es **5deb230** (rama `seguridad-avisos-admin`, sobre 3a5cc29), no 6c0d6d0 como se informó. Sobre `navegacion-por-rol` choca en `catalogo/views.py`, `cofrial/contexto.py`, `cofrial/urls.py`, `static/css/cofrial.css` y `tienda/base.html`; sobre 839eac1 suma `catalogo/views.py` a los choques.
- Hay tres arreglos de la misma redirección: 5deb230 (`url_has_allowed_host_and_scheme`, el estándar de Django), 839eac1 (`entradas.destino_propio`) y el que se retiró de `navegacion-por-rol`. Debe quedar uno solo.

## 9. Rama `despliegue-2` lista para aprobar (25-oct-2026, noche)

- a85cf07 en la rama local `despliegue-2` (worktree `claude/despliegue-2-d39db9`): 6 commits sobre `origin/main` 3a5cc29, con 39 archivos y ninguno de `docs/`.
- El orquestador corrió la suite completa contra Postgres 16 en un stack aparte: **363 pruebas, OK, 2 omitidas**; `makemigrations --check` sin cambios. Coincide con lo que reportó la sesión.
- Diff revisado en `pedidos/servicios.py`, `pedidos/views.py`, `flota/views.py`, `crm/servicios.py`, `cofrial/seguridad.py`, los compose de AWS, `verificar.py` y el informe. Sin defectos encontrados.
- Pendiente de Eric: aprobar el PR a `main` y el despliegue con WareTruck (línea base, snapshot `cofrial-db`, `recrear-web` y stock de pavo a 55 y cordero a 8 a mano).
- Para la sala de la defensa (hallazgos medios): los topes de registro (10/h) y soporte (20/h) son por IP; el 429 por barrido bloquea a toda la IP tras 60 «no encontrado» en 10 min; con 2 workers los límites reales se duplican.
