# 4b. Modelo de datos: MER en 3FN + diccionario

Rúbrica H1-D3 (Logrado): MER **rigurosamente normalizado** que soporte transacciones (E-commerce/CRM) **y** telemetría IoT.

## Entidades principales (diagrama ER)

```
CLIENTE ──┬─→ DIRECCION (1:N)
          ├─→ ORDEN (1:N)
          └─→ OPORTUNIDAD (1:N)

PRODUCTO ──┬─→ CATEGORIA (N:1)
           ├─→ LISTA_PRECIO (1:N)
           └─→ ORDEN_ITEM (1:N)

CATEGORIA ←── PRODUCTO (N:1)

LISTA_PRECIO ──→ PRECIO_PRODUCTO (1:N) ──→ ORDEN_ITEM

PRECIO_PRODUCTO ──→ PRODUCTO (N:1)

ORDEN ──┬─→ CLIENTE (N:1)
        ├─→ ORDEN_ITEM (1:N)
        ├─→ ESTADO_ORDEN (N:1)
        └─→ CAMION (N:1) [asignado cuando sale a ruta]

ORDEN_ITEM ──┬─→ PRODUCTO (N:1)
             ├─→ LISTA_PRECIO (N:1)
             └─→ ORDEN (N:1)

ESTADO_ORDEN ←── ORDEN (N:1)

VENDEDOR ──┬─→ OPORTUNIDAD (1:N)
           └─→ INTERACCION (1:N)

OPORTUNIDAD ──┬─→ CLIENTE (N:1)
              ├─→ VENDEDOR (N:1)
              ├─→ ETAPA_PIPELINE (N:1)
              └─→ INTERACCION (1:N)

INTERACCION ──┬─→ OPORTUNIDAD (N:1)
              └─→ VENDEDOR (N:1)

CAMION ──┬─→ TELEMETRIA (1:N)
         └─→ ORDEN (1:N) [entregas]

TELEMETRIA ──→ CAMION (N:1)
            └─→ alerta_ruptura_frio: boolean (derivada: temp_camara > rango)
```

### Diagrama ER profesional (14 entidades)

**[GENERA AQUÍ CON DRAW.IO + TU SKILL DE INFORME]**

Entidades a dibujar (relaciones en el ASCII arriba):
- CLIENTE (central) ↔ DIRECCION, ORDEN, OPORTUNIDAD
- PRODUCTO ↔ CATEGORIA, LISTA_PRECIO, ORDEN_ITEM
- ORDEN ↔ CLIENTE, ORDEN_ITEM, ESTADO_ORDEN, CAMION (NEW)
- VENDEDOR ↔ OPORTUNIDAD, INTERACCION
- OPORTUNIDAD ↔ CLIENTE, VENDEDOR, ETAPA_PIPELINE, INTERACCION
- CAMION ↔ TELEMETRIA, ORDEN
- Todas las claves foráneas (FK) explícitas

Exportar a: `informe/img/modelo-er-3fn.png`

---

## Normalización a 3FN: verificación

### 1NF (sin grupos repetitivos)
- ✅ Cada tabla tiene una PK única.
- ✅ No hay columnas multivaluadas (ej. "teléfonos" en CLIENTE).
- ✅ Cada fila tiene un valor atómico en cada columna.

### 2FN (sin dependencias parciales en PKs compuestas)
- ✅ PRECIO_PRODUCTO(lista_precio_id, producto_id, precio): tanto lista como producto determinan el precio. No hay dependencia parcial.
- ✅ ORDEN_ITEM(orden_id, producto_id, cantidad, precio_unitario_en_orden): el precio se copia en la orden (histórico, válido en 3FN).
- ✅ TELEMETRIA(camion_id, timestamp): ambas claves determinan un registro único.

### 3FN (sin dependencias transitivas)
- ✅ CLIENTE: cliente → dirección → comuna. Pero DIRECCION es una entidad propia (1:N con cliente), no una columna. Sin transitividad.
- ✅ ORDEN: orden → cliente → vendedor asignado. Pero VENDEDOR se asigna al cliente en el CRM, no en la orden. Sin transitividad.
- ✅ TELEMETRIA: no hay dependencias transitivas (solo referencia a CAMION).

**Conclusión:** el modelo está en 3FN.

---

## Diccionario de datos

### CLIENTE
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| cliente_id | INT | SÍ | — | No | Identificador único |
| nombre | VARCHAR(200) | — | — | No | Nombre legal o razón social |
| rut | VARCHAR(12) | — | — | Sí | Identificación única en Chile |
| tipo | ENUM('B2B', 'B2C') | — | — | No | Perfil de cliente |
| email | VARCHAR(100) | — | — | Sí | Contacto principal |
| credito_limite | DECIMAL(12,2) | — | — | Sí | Línea de crédito B2B |
| activo | BOOLEAN | — | — | No | Marca si está en operación (default: true) |
| creado_en | TIMESTAMP | — | — | No | Fecha de registro |

### PRODUCTO
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| producto_id | INT | SÍ | — | No | Identificador único |
| nombre | VARCHAR(150) | — | — | No | Descripción del producto (ej. "Lomo Vetado 1kg") |
| categoria_id | INT | — | SÍ (CATEGORIA) | No | Clasificación |
| temp_minima | FLOAT | — | — | No | Rango crítico inferior (°C) |
| temp_maxima | FLOAT | — | — | No | Rango crítico superior (°C) |
| costo_unitario | DECIMAL(8,2) | — | — | No | Costo para la empresa |
| activo | BOOLEAN | — | — | No | Disponible para venta (default: true) |

### LISTA_PRECIO
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| lista_precio_id | INT | SÍ | — | No | Identificador único |
| nombre | VARCHAR(100) | — | — | No | "Precio Público" o "Institución Temuco" |
| tipo | ENUM('B2B', 'B2C') | — | — | No | Aplicable a qué perfil |
| descripcion | TEXT | — | — | Sí | Notas sobre descuentos, volumen mínimo |

### PRECIO_PRODUCTO
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| lista_precio_id | INT | SÍ (compuesta) | SÍ (LISTA_PRECIO) | No | Qué lista de precios |
| producto_id | INT | SÍ (compuesta) | SÍ (PRODUCTO) | No | Qué producto |
| precio_unitario | DECIMAL(8,2) | — | — | No | Precio en esa lista |
| vigente_desde | DATE | — | — | No | Cuándo entra en vigencia |

### ORDEN
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| orden_id | INT | SÍ | — | No | Identificador único |
| cliente_id | INT | — | SÍ (CLIENTE) | No | Quién compra |
| camion_id | VARCHAR(20) | — | SÍ (CAMION) | Sí | Qué vehículo entrega (asignado cuando sale) |
| estado_orden_id | INT | — | SÍ (ESTADO_ORDEN) | No | Estado actual (Nueva, Preparando, En tránsito, Entregada) |
| fecha_creacion | TIMESTAMP | — | — | No | Cuándo se generó la orden |
| fecha_entrega_requerida | DATE | — | — | No | Cuándo lo necesita el cliente |
| tiempo_salida | TIMESTAMP | — | — | Sí | Cuándo salió del almacén (NULL si pendiente) |
| fecha_entrega_real | DATE | — | — | Sí | Cuándo se entregó (NULL si pendiente) |
| notas | TEXT | — | — | Sí | Observaciones especiales |

### ORDEN_ITEM
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| orden_id | INT | SÍ (compuesta) | SÍ (ORDEN) | No | Qué orden |
| item_numero | INT | SÍ (compuesta) | — | No | Secuencia dentro de la orden |
| producto_id | INT | — | SÍ (PRODUCTO) | No | Qué se compra |
| cantidad | INT | — | — | No | Cuántas unidades |
| precio_unitario | DECIMAL(8,2) | — | — | No | Precio pactado en el momento (histórico) |
| subtotal | DECIMAL(10,2) | — | — | No | cantidad × precio_unitario |

### VENDEDOR
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| vendedor_id | INT | SÍ | — | No | Identificador único |
| nombre | VARCHAR(150) | — | — | No | Nombre del vendedor |
| email | VARCHAR(100) | — | — | Sí | Contacto |
| activo | BOOLEAN | — | — | No | Está en operación (default: true) |

### OPORTUNIDAD
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| oportunidad_id | INT | SÍ | — | No | Identificador único |
| cliente_id | INT | — | SÍ (CLIENTE) | No | Prospecto o cliente existente |
| vendedor_id | INT | — | SÍ (VENDEDOR) | No | Quién la lleva |
| etapa_pipeline_id | INT | — | SÍ (ETAPA_PIPELINE) | No | Dónde está (Prospecto, Contactado, Propuesta, Negociación, Ganada, Perdida) |
| monto_estimado | DECIMAL(10,2) | — | — | Sí | Valor esperado de la venta |
| fecha_creacion | TIMESTAMP | — | — | No | Cuándo se registró |
| fecha_cierre | DATE | — | — | Sí | Cuándo se cerró (ganada o perdida) |

### ETAPA_PIPELINE
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| etapa_pipeline_id | INT | SÍ | — | No | Identificador único |
| nombre | VARCHAR(50) | — | — | No | "Prospecto", "Contactado", "Propuesta", "Negociación", "Ganada", "Perdida" |
| secuencia | INT | — | — | No | Orden en el flujo (1, 2, 3, ...) |

### CATEGORIA
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| categoria_id | INT | SÍ | — | No | Identificador único |
| nombre | VARCHAR(100) | — | — | No | Ej. "Carnes rojas", "Aves", "Productos procesados" |
| descripcion | TEXT | — | — | Sí | Detalles de la categoría |

### DIRECCION
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| direccion_id | INT | SÍ | — | No | Identificador único |
| cliente_id | INT | — | SÍ (CLIENTE) | No | A quién pertenece |
| calle | VARCHAR(150) | — | — | No | Dirección completa o domicilio |
| numero | VARCHAR(10) | — | — | Sí | Número de calle |
| ciudad | VARCHAR(100) | — | — | No | Localidad (Temuco, Villarrica, etc.) |
| region | VARCHAR(100) | — | — | No | Región administrativa |
| codigo_postal | VARCHAR(10) | — | — | Sí | Código postal |
| es_principal | BOOLEAN | — | — | No | Dirección de entrega por defecto (default: false) |

### ESTADO_ORDEN
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| estado_orden_id | INT | SÍ | — | No | Identificador único |
| nombre | VARCHAR(50) | — | — | No | "Nueva", "Preparando", "En tránsito", "Entregada", "Cancelada" |
| secuencia | INT | — | — | No | Orden en el flujo (1, 2, 3, ...) |

### CAMION
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| camion_id | VARCHAR(20) | SÍ | — | No | Patente o código único (ej. "TR-2205") |
| modelo | VARCHAR(100) | — | — | Sí | Marca/modelo del vehículo |
| capacidad_kg | INT | — | — | Sí | Capacidad de carga |
| temperatura_rango_min | FLOAT | — | — | No | Rango configurado mínimo (°C) |
| temperatura_rango_max | FLOAT | — | — | No | Rango configurado máximo (°C) |
| activo | BOOLEAN | — | — | No | En operación (default: true) |

### TELEMETRIA
| Campo | Tipo | PK | FK | Nulo | Descripción |
|---|---|---|---|---|---|
| camion_id | VARCHAR(20) | SÍ (compuesta) | SÍ (CAMION) | No | ID del camión (exigido por pauta) |
| timestamp | TIMESTAMP | SÍ (compuesta) | — | No | Cuándo se registró (exigido; permite series de tiempo) |
| temp_camara | FLOAT | — | — | No | Temperatura en °C (exigido por pauta) |
| lat | FLOAT | — | — | No | Latitud (exigido por pauta; SQL usa comillas: "lat") |
| long | FLOAT | — | — | No | Longitud (exigido por pauta; SQL usa comillas: "long") |
| combustible_pct | INT | — | — | No | Porcentaje de combustible 0-100 (exigido por pauta) |
| alerta_ruptura_frio | BOOLEAN | — | — | No | Bandera: true si temp fuera del rango (exigido por pauta) |

Nota. Campos exigidos por la pauta EVA2_3: camion_id, temp_camara, lat, long, combustible_pct, alerta_ruptura_frio. Otros son de negocio. Elaboración propia.

---

## Scripts SQL de creación (borrador)

Estas tablas se crean en RDS PostgreSQL. El script completo va en el repositorio en `db/schema.sql` antes del Hito 2.

```sql
-- Ejemplo (sin todas las constraints):
CREATE TABLE cliente (
  cliente_id SERIAL PRIMARY KEY,
  nombre VARCHAR(200) NOT NULL,
  rut VARCHAR(12),
  tipo ENUM('B2B', 'B2C') NOT NULL,
  email VARCHAR(100),
  credito_limite DECIMAL(12,2),
  activo BOOLEAN DEFAULT true,
  creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE telemetria (
  camion_id VARCHAR(20) NOT NULL,
  timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  temp_camara FLOAT NOT NULL,
  lat FLOAT NOT NULL,
  "long" FLOAT NOT NULL,  -- comillas porque es palabra reservada
  combustible_pct INT NOT NULL CHECK (combustible_pct >= 0 AND combustible_pct <= 100),
  alerta_ruptura_frio BOOLEAN NOT NULL DEFAULT false,
  PRIMARY KEY (camion_id, timestamp),
  FOREIGN KEY (camion_id) REFERENCES camion(camion_id)
);
```

Nota. Borrador. El script completo incluye índices, constraints y comentarios. Elaboración propia.

---

## Siguientes pasos

1. **Validar el MER** con Sergio antes de crear las tablas.
2. **Generar el script SQL completo** en `db/schema.sql`.
3. **Cargar el schema en RDS** durante el Hito 2.
4. **Seed data:** cargar productos, listas de precios y clientes de prueba.

Nota. Elaboración propia.
