# Código del sistema (Hito 2)

Esqueleto funcional, probado en local con Docker. Sigue el diseño del informe (`informe/modelo/esquema.sql` y decisiones D-01 a D-04 de `docs/decisiones.md`).

## Estructura

| Carpeta | Contenido |
|---|---|
| `web/` | Django 5.2: una app por módulo del modelo (`catalogo`, `clientes`, `pedidos`, `flota`, `crm`), panel de administración como CRM base y vista de catálogo con precio según el perfil B2B o B2C |
| `iot/` | Simulador de un camión (Python): lee su rango de temperatura de la base e inserta lecturas con los seis campos de la pauta |
| `grafana/` | Tablero de BI: configuración de la fuente de datos, tablero provisionado y el script que lo genera |
| `docker-compose.yml` | Entorno local completo: PostgreSQL, web, tres camiones y Grafana |
| `.env.example` | Variables necesarias; se copia a `.env` (ignorado por git) |

## Cómo se levanta en un computador del equipo

```bash
cp .env.example .env        # completar DB_PASSWORD y DEMO_PASSWORD
docker compose up -d --build
```

La web queda en `http://localhost:8000` (catálogo en `/catalogo/`, CRM en `/crm/`, administración en `/admin/`), el tablero en `http://localhost:3000` y la base en el puerto 5433. El contenedor web aplica las migraciones y carga datos de demostración al arrancar; los camiones esperan a que su registro exista y empiezan a insertar lecturas.

Pruebas (con la base encendida): `docker compose up -d db && docker compose run --rm --no-deps web python manage.py test --noinput`.

La lógica de negocio está en `web/pedidos/servicios.py` y `web/crm/servicios.py`; las vistas solo llaman a esas funciones. Usuarios de demo: `ana@correo.test` (B2C), `abastecimiento@hospital.test` (B2B), `vendedora@cofrial.cl`, `vendedor2@cofrial.cl`, `gerencia@cofrial.cl`, `despacho@cofrial.cl` y `admin`; la contraseña es `DEMO_PASSWORD` del `.env`.

## Qué está hecho y qué falta

| Parte | Estado |
|---|---|
| 25 tablas del modelo como modelos Django, con las restricciones del esquema (CHECK, únicos parciales) y las vistas `v_orden` y `v_orden_total` | Hecho y probado |
| Simulador IoT: inserta `camion_id`, `temp_camara`, `lat`, `long`, `combustible_pct`, `alerta_ruptura_frio`; la alerta sale del rango del camión en la base; simula rupturas de frío | Hecho y probado con 3 camiones |
| Catálogo con lista de precios por perfil | Hecho |
| Imágenes construidas para x86 (las EC2 del laboratorio no son ARM) | Verificado con `--platform linux/amd64` |
| Carrito y órdenes del portal: precio por perfil (RN-01), stock transaccional con bloqueo (RN-02), un carrito abierto (RN-03), dirección propia (RN-04), orden de compra B2B (RN-05), precio congelado (RN-06), cancelación por estado con reposición de stock (RN-07) y «repetir último pedido» (RN-08). Pantallas: catálogo con «Agregar», carrito, confirmación, mis pedidos, detalle y cancelación. El vendedor avanza o cancela órdenes desde el panel de administración | Hecho; 19 pruebas automáticas (incluida la compra simultánea de la última unidad) y prueba de punta a punta por HTTP |
| Registro de clientes nuevos (B2C) desde el portal | Pendiente; hoy los clientes se crean desde el administrador o la carga de demo |
| CRM (`/crm/`): panel con indicadores, embudo por etapas, ficha del prospecto con interacciones y movimiento de etapa, cartera y ficha del cliente con pedidos web y alerta de frío, pedido a nombre del cliente, bandeja de requerimientos con clasificación manual y seguimiento de alertas. Reglas RN-09 (cartera por vendedor), RN-10 (sin saltos de etapa), RN-11 (perder exige motivo; ganar crea el cliente B2B), RN-12 (interacciones), RN-13 (alerta de frío sobre las órdenes del viaje) y RN-15. Permisos por rol según la Tabla 2 del informe (vendedor, gerencia, despachador, administrador); los clientes del portal no entran | Hecho; 15 pruebas del CRM (34 en total) y verificación en vivo: una ruptura de frío del simulador aparece en la ficha del cliente y en la vista del despachador |
| Clasificación automática con IA (Gemini, respaldo Groq; RN-14, umbral 0,60). Hoy el vendedor clasifica a mano | Pendiente |
| Tablero Grafana en vivo (`grafana/`, puerto 3000): ventas por canal cruzadas con alertas de ruptura de frío en una misma línea de tiempo, ventas en riesgo, temperatura por camión, mapa de la flota y pedidos afectados. Se actualiza cada 5 s; lee la base con un usuario de solo lectura (`grafana_ro`) que crea `preparar_bi`; el tablero se regenera con `python3 grafana/generar_dashboard.py` | Hecho y verificado con datos reales del simulador |
| Despliegue en AWS (VPC, EC2 web, EC2 IoT, RDS) | Pendiente; lo ejecutan Eric y Sergio con sus credenciales del laboratorio |

## Diferencias deliberadas con el diseño

- Las tablas de clave compuesta (`precio_producto`, `carrito_item`, `orden_item`) usan clave autogenerada más restricción de unicidad sobre el par, la salida que prevé D-03 (el panel de administración de Django 5.2 no soporta claves compuestas). La 3FN se mantiene.
- La tabla `usuario` se reemplaza por la autenticación de Django; `vendedor` y `cliente` se enlazan a ese usuario.
