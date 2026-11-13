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

## Sitio en línea

**https://www.cofrialspa.shop**: balanceador de AWS (ALB) en dos zonas, dos servidores web y RDS PostgreSQL Multi-AZ. Usa un certificado de Amazon (ACM). `http://` y `cofrialspa.shop` sin `www` redirigen ahí.

> Solo abre mientras el laboratorio de AWS Academy está encendido (sesiones de 4 horas). Para encenderlo: `bash aws/activar.sh` (pide las credenciales del laboratorio, enciende y verifica). Fuera de esa ventana no responde, aunque la dirección sea correcta.

En local, con `docker compose up`, las mismas rutas viven en `http://localhost:8000` (o en el puerto de `WEB_PUERTO`).

## Direcciones

Sin sesión, una ruta protegida lleva a `/cuenta/entrar/`. Con una cuenta que no tiene permiso, muestra «No puedes ver esta sección» (403).

### Públicas (sin sesión)
| Dirección | Qué es |
|---|---|
| [`/`](https://www.cofrialspa.shop/) | Inicio de la tienda (con sesión, cada rol cae en su pantalla) |
| [`/portada/`](https://www.cofrialspa.shop/portada/) | Portada pública, también con sesión abierta |
| [`/catalogo/`](https://www.cofrialspa.shop/catalogo/) | Catálogo de refrigerados y congelados, con filtros; `/catalogo/<id>/` es la ficha de un producto |
| [`/cuenta/entrar/`](https://www.cofrialspa.shop/cuenta/entrar/) | Ingreso |
| [`/cuenta/registro/`](https://www.cofrialspa.shop/cuenta/registro/) | Crear cuenta de cliente particular (B2C) |
| [`/cuenta/registro/empresa/`](https://www.cofrialspa.shop/cuenta/registro/empresa/) | Pedir cuenta de empresa (B2B): queda pendiente hasta que ventas la aprueba en el CRM |
| [`/cuenta/recuperar/`](https://www.cofrialspa.shop/cuenta/recuperar/) | Recuperar la clave por correo |
| [`/legal/terminos/`](https://www.cofrialspa.shop/legal/terminos/) | Términos; también `privacidad`, `cookies`, `devoluciones` y `licencias` |

### Clientes (B2C y B2B)
| Dirección | Qué es |
|---|---|
| `/carrito/` | Carrito, dirección de entrega, boleta o factura, y pago (Mercado Pago u orden de compra a 30 días) |
| `/pedidos/` | Mis pedidos, con pestañas por estado |
| `/pedidos/<id>/` | Detalle del pedido: etapas, **mapa en vivo con el tiempo de llegada**, temperatura del viaje y recepción (aceptar o rechazar por línea) |
| `/seguimiento/` | «Seguir mi pedido»: abre el pedido en curso más reciente |
| `/soporte/` | Soporte con IA: el reclamo se clasifica solo y llega al CRM |
| `/avisos/` | Avisos de stock pedidos |
| `/cuenta/mis-datos/` | Descargar o eliminar los datos propios |
| `/cuenta/clave/` | Cambiar la clave |

### Equipo comercial: CRM (administrador, gerencia y vendedores)
| Dirección | Qué es |
|---|---|
| `/crm/` | Panel con las ventas por canal (al despachador lo lleva a las alertas de frío) |
| `/crm/embudo/` | Embudo de prospectos; `/crm/prospectos/nuevo/` crea uno (admin y vendedores) |
| `/crm/clientes/` | Cartera; `/crm/clientes/<id>/` es la ficha con pedidos web, interacciones y direcciones. Cada vendedor ve solo su cartera |
| `/crm/solicitudes/` | Cuentas de empresa por aprobar |
| `/crm/requerimientos/` | Reclamos y consultas clasificados por IA; en cada uno, «Clasificar con IA» |
| `/crm/ia/` | Cómo funciona la IA: flujo, proveedores (Gemini y Groq de respaldo) y resultados |
| `/crm/cobranza/` | Facturas, pagos, notas de crédito y clientes morosos |
| `/crm/demanda/` | Demanda por producto (también la ve el despachador) |
| `/crm/alertas/` | Pedidos afectados por ruptura de frío (también la ve el despachador) |

### Flota y despacho (administrador, gerencia y despachador)
| Dirección | Qué es |
|---|---|
| `/flota/` | **Mapa nocturno de la flota** (OpenFreeMap): detalle por zoom con la rueda, ida y vuelta de cada viaje, alertas de frío y tarjetas de los 50 camiones en vivo |
| `/flota/despachar/` | Armar un despacho: camión propuesto y mejor orden de entrega. Gerencia lo ve pero no lo confirma |
| `/flota/por-despachar/` | Contador de pedidos listos para salir |
| `/flota/despacho-auto/` | Estado del despacho automático |

### Dirección (administrador y gerencia)
| Dirección | Qué es |
|---|---|
| `/torre/` | **Torre de control**: negocio, cadena de frío y rúbrica en vivo en una pantalla |
| `/bi/` | Panel BI en Grafana: ventas por canal cruzadas con alertas de frío. Gerencia mira y el administrador edita; Grafana no tiene puerto propio abierto |

### Administración (solo administrador)
| Dirección | Qué es |
|---|---|
| `/operacion/` | Panel de administración propio: `stock/`, `productos/`, `ordenes/`, `cuentas/`, `datos/` (tablas de la base) y `sistema/` (probar la IA, podar telemetría) |
| `/demo/` | Modo demostración: forzar una ruptura de frío, acelerar el tiempo o pedir un escenario con palabras (la IA lo traduce para el simulador) |
| Admin de Django | Ruta configurable con `DJANGO_ADMIN_URL` (por defecto `/admin/`) |

### API y estado
| Dirección | Quién | Qué devuelve |
|---|---|---|
| [`/api/productos/`](https://www.cofrialspa.shop/api/productos/) | Público | Catálogo en JSON; `/api/productos/<sku>/` un producto |
| `/api/flota/` | Administrador, gerencia y despachador | Camiones y su última lectura (`camion_id`, `temp_camara`, `lat`, `long`, `combustible_pct`, `alerta_ruptura_frio`) |
| `/api/pedidos/`, `/api/pedidos/<id>/seguimiento/`, `/api/pedidos/<id>/ruta/` | Cliente con sesión, solo sus pedidos | Sus órdenes, el seguimiento del camión y el tramo de ruta hasta su dirección (nunca las paradas de otros clientes) |
| [`/salud/`](https://www.cofrialspa.shop/salud/) | Público | Estado de web, base, IoT, Grafana, IA y pagos (en versiones anteriores al PR #97 responde `{"estado": "ok"}`) |
| [`/health`](https://www.cofrialspa.shop/health) | Público | Chequeo que usa el balanceador (incluye la base) |

## Cuentas de prueba

Las claves **no están en el repositorio**. El equipo las calcula desde su `secretos.env` con `python3 web/clientes/cuentas_demo.py` y las entrega aparte. Detalle en [`docs/cuentas-y-permisos.md`](docs/cuentas-y-permisos.md).

| Usuario | Rol | Para probar |
|---|---|---|
| `ana@correo.test`, `sergio@cofrial.cl` | Cliente particular (B2C) | Precio público, carrito, boleta, Soporte con IA, seguimiento |
| `abastecimiento@hospital.test`, `felipe@cofrial.cl` | Cliente institucional (B2B) | Precio institucional, orden de compra, factura |
| `abastecimiento@hospitalangol.test`, `…hospitalvillarrica.test`, `…hospitalpucon.test` | Cliente B2B regional | Reparto lejos del frigorífico (Angol, corredor de los lagos) |
| `vendedora@cofrial.cl`, `vendedor2@cofrial.cl` | Vendedores | CRM; cada uno ve solo su cartera |
| `gerencia@cofrial.cl` | Gerencia | Lee todo (CRM, flota, Torre, BI); no modifica |
| `despacho@cofrial.cl` | Despachador | Flota, despachos y alertas de frío |
| `admin@cofrial.cl`, `eric@cofrial.cl` | Administrador | Todo, incluidos `/operacion/` y `/demo/` |

## Cómo probar

### 1. A mano, paso a paso
[`docs/guia-pruebas-aws.md`](docs/guia-pruebas-aws.md) trae 29 pruebas en orden, con la cuenta, lo que debe pasar y la dimensión de la rúbrica que respalda: base y salud, e-commerce B2B/B2C, CRM, cadena de frío e IoT, BI, IA, permisos, resiliencia y cuentas creadas por el usuario. Los bordes que un profesor probaría están en [`docs/matriz-casos-de-uso.md`](docs/matriz-casos-de-uso.md).

### 2. Verificador automático contra el sitio
Solo necesita Python 3. Lee el sitio y no crea datos, salvo `--compra-ensayo` y `--ia`:

```bash
python3 aws/verificar.py https://www.cofrialspa.shop             # punta a punta: ingreso de las 13 cuentas y las pantallas de cada una
python3 aws/verificar.py https://www.cofrialspa.shop --ia        # además envía un reclamo y espera la clasificación de la IA
python3 aws/verificar.py https://www.cofrialspa.shop --infra     # además lee de AWS: ALB en dos zonas, dos web sanas, RDS Multi-AZ
python3 aws/verificar.py https://www.cofrialspa.shop --defensa   # todo lo anterior y la rúbrica D1 a D5 de la Torre en verde
python3 aws/verificar.py https://www.cofrialspa.shop --compra-ensayo   # compra B2B y B2C reales (crea pedidos y descuenta stock)
```

Necesita la clave de demostración en la variable `DEMO_PASSWORD` (o `CLAVE_UNICA_DEMO`).

### 3. Pruebas automáticas del código (local, sin AWS)
Con Docker, en una base aislada, para no tocar otro stack:

```bash
docker compose build web
docker compose run --rm -e DEMO_PASSWORD= -e ADMIN_PASSWORD= web python manage.py test --noinput      # suite completa, unos 20 min
docker compose run --rm -e DEMO_PASSWORD= -e ADMIN_PASSWORD= web python manage.py test --noinput pedidos.tests_seguimiento_comprador   # un módulo
```

Las variables vacías son a propósito: con una clave definida, cada cuenta deriva otra clave y fallan los ingresos de prueba.

| Área | Módulos (`web/<app>/tests*.py`) |
|---|---|
| Tienda y catálogo | `catalogo.tests`, `catalogo.tests_entrega_cliente`, `catalogo.tests_seguridad_avisos` |
| Compra, pagos y documentos | `pedidos.tests`, `pedidos.tests_casos_compra`, `pedidos.tests_mercadopago`, `pedidos.tests_comprobante`, `pedidos.tests_documentos`, `pedidos.tests_total_con_iva`, `pedidos.tests_morosos` |
| Entrega y seguimiento del cliente | `pedidos.tests_entrega`, `pedidos.tests_recepcion_parcial`, `pedidos.tests_seguimiento_comprador`, `pedidos.tests_ruta_cliente`, `pedidos.tests_revision_aviso`, `pedidos.tests_quien_recibe`, `pedidos.tests_ruptura_cliente`, `pedidos.tests_tarjetas_cof`, `pedidos.tests_temperatura_sin_lecturas` |
| CRM e IA | `crm.tests`, `crm.tests_casos_cartera`, `crm.tests_demo_ia`, `crm.tests_niveles`, `crm.tests_nav` |
| Flota, rutas e IoT | `flota.tests`, `flota.tests_autodespacho`, `flota.tests_dos_camaras`, `flota.tests_escenarios`, `flota.tests_regional`, `flota.tests_rutas`, `flota.tests_casos_viaje`, `flota.tests_por_despachar`, `flota.tests_vigente`, `flota.tests_retencion` |
| Torre de control | `torre.tests_vistas`, `torre.tests_pulso`, `torre.tests_rubrica`, `torre.tests_geo` |
| Administración | `operacion.tests`, `operacion.tests_datos`, `operacion.tests_ordenes`, `operacion.tests_productos`, `operacion.tests_cuentas_estado`, `operacion.tests_sistema` |
| Cuentas, permisos y seguridad | `cofrial.tests_seguridad`, `cofrial.tests_rutas`, `cofrial.tests_403_por_rol`, `cofrial.tests_cuentas`, `cofrial.tests_casos_sesion`, `cofrial.tests_navegacion`, `cofrial.tests_avisos_equipo`, `cofrial.tests_legal`, `cofrial.tests_bi`, `cofrial.tests_iconos`, `cofrial.tests` |
| Clientes y datos de muestra | `clientes.tests`, `clientes.tests_segmento`, `clientes.tests_muestra`, `clientes.tests_precarga`, `clientes.tests_docs_cuentas` |
| Estado del sistema | `salud.tests` |

Fuera de Django:

```bash
(cd iot && CAMION_ID=CAM-01 python3 -m unittest test_simulador)   # simulador IoT: movimiento del camión y paradas
python3 aws/test_verificar.py       # el propio verificador, sin red
bash aws/test_provision_ha.sh       # despliegue con alta disponibilidad, con una AWS falsa
bash aws/test_activar.sh            # el encendido de cada sesión del laboratorio
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
| Esqueleto del proyecto web (Django) | Eric | adelanta H2-D2 |

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
| **Entrega Hito 2 — jue 12-nov · defensa movida al dom 15-nov** | Eric + Sergio | |

### Extras para destacar (después de cumplir lo obligatorio)
- **Torre de control** al estilo WareTrack: mapa con los camiones en vivo, KPIs y panel de detalle.
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

## Estructura del repositorio
```
web/       Aplicación Django: tienda, pedidos, CRM, flota, torre de control, operación y salud
iot/       Simulador de los camiones (Docker, nodo EC2 dedicado)
aws/       Despliegue en AWS Academy (provision.sh, activar.sh, verificar.py) y su compose
grafana/   Panel BI (tablero y generador)
docker/    Configuración de apoyo para el entorno local
informe/   Secciones del informe del Hito 1
docs/      Decisiones técnicas, guías de prueba y referencias
CLAUDE.md  Contexto para Claude Code
```
