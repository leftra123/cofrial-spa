# 4b. Modelo de datos (MER en 3FN + diccionario)

> Rúbrica H1-D3 (Logrado): MER **rigurosamente normalizado** que soporte transacciones (E-commerce/CRM) **y** telemetría IoT.

## Entidades candidatas (borrador para discutir)
**Comercial (E-commerce)**
- `categoria`, `producto` (con rango de temperatura de conservación), `lista_precio` (B2B institucional / B2C), `precio_producto` (producto × lista)
- `cliente` (tipo B2B/B2C, RUT), `direccion`
- `carrito`, `carrito_item`
- `orden`, `orden_item`, `estado_orden`

**CRM**
- `vendedor`, `prospecto`, `etapa_pipeline`, `oportunidad`, `interaccion` (llamada, correo, nota)
- `requerimiento` (consulta o reclamo, con la categoría que asigna la IA)

**Logística e IoT**
- `camion` (patente, capacidad), `despacho` (orden ↔ camión), `telemetria`

## Tabla de telemetría: nombres EXACTOS exigidos
| Campo | Tipo | Nota |
|---|---|---|
| `camion_id` | string (FK a `camion`) | obligatorio |
| `temp_camara` | float | obligatorio |
| `lat` | float / numeric | obligatorio |
| `long` | float / numeric | obligatorio (en SQL conviene escribirlo entre comillas: `"long"`) |
| `combustible_pct` | integer (0–100) | obligatorio |
| `alerta_ruptura_frio` | boolean | obligatorio: true si `temp_camara` sale del rango crítico |
| `registrado_en` | timestamp | agregado nuestro, necesario para series de tiempo |

## Verificación de 3FN (checklist)
- [ ] Cada tabla tiene PK; sin grupos repetitivos (1FN)
- [ ] Sin dependencias parciales en tablas con PK compuesta (2FN), ej. `precio_producto`
- [ ] Sin dependencias transitivas (3FN), ej. la comuna no se guarda con la región
- [ ] El precio de la orden se copia en `orden_item` (es histórico, no rompe 3FN: justificarlo)

## Diccionario de datos
Formato por tabla: campo · tipo · nulo · clave · descripción · ejemplo. _Pendiente._

## Notas del equipo
