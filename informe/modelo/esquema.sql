-- Esquema de datos de Cofrial SpA (PostgreSQL). Generado por informe/modelo/modelo.py: no editar a mano.
-- La columna "long" va entre comillas porque LONG es palabra reservada en SQL.

-- Regiones de Chile donde se entregan pedidos.
CREATE TABLE region (
  region_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(60) NOT NULL UNIQUE
);

-- Comunas, cada una dentro de una región. La región no se repite en la dirección.
CREATE TABLE comuna (
  comuna_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  region_id integer NOT NULL REFERENCES region (region_id),
  nombre varchar(60) NOT NULL,
  UNIQUE (region_id, nombre)
);

-- Rangos de temperatura de conservación. Definen cuándo una lectura es crítica.
CREATE TABLE rango_temperatura (
  rango_temperatura_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(40) NOT NULL UNIQUE,
  temp_min_c numeric(5,1) NOT NULL,
  temp_max_c numeric(5,1) NOT NULL,
  CHECK (temp_min_c < temp_max_c)
);

-- Categorías de producto. Cada una exige un rango de temperatura de conservación.
CREATE TABLE categoria (
  categoria_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(60) NOT NULL UNIQUE,
  rango_temperatura_id integer NOT NULL REFERENCES rango_temperatura (rango_temperatura_id)
);

-- Productos del catálogo de refrigerados y congelados.
CREATE TABLE producto (
  producto_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sku varchar(30) NOT NULL UNIQUE,
  nombre varchar(120) NOT NULL,
  descripcion text,
  categoria_id integer NOT NULL REFERENCES categoria (categoria_id),
  unidad_medida varchar(10) NOT NULL CHECK (unidad_medida IN ('kg','un','caja')),
  stock_disponible integer NOT NULL DEFAULT 0 CHECK (stock_disponible >= 0),
  activo boolean NOT NULL DEFAULT true
);

-- Listas de precios: institucional para B2B y pública para B2C.
CREATE TABLE lista_precio (
  lista_precio_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(60) NOT NULL UNIQUE
);

-- Precio de cada producto en cada lista de precios.
CREATE TABLE precio_producto (
  lista_precio_id integer NOT NULL REFERENCES lista_precio (lista_precio_id),
  producto_id integer NOT NULL REFERENCES producto (producto_id),
  precio_clp integer NOT NULL CHECK (precio_clp > 0),
  PRIMARY KEY (lista_precio_id, producto_id)
);

-- Tipos de cliente. Cada tipo usa una lista de precios, así el cliente no la repite.
CREATE TABLE tipo_cliente (
  tipo_cliente_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo varchar(3) NOT NULL UNIQUE CHECK (codigo IN ('B2B','B2C')),
  nombre varchar(40) NOT NULL,
  lista_precio_id integer NOT NULL REFERENCES lista_precio (lista_precio_id),
  dias_credito smallint NOT NULL DEFAULT 0 CHECK (dias_credito >= 0)
);

-- Cuentas de acceso al portal, al CRM y al panel. Si el framework trae su propia autenticación, reemplaza esta tabla.
CREATE TABLE usuario (
  usuario_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email varchar(120) NOT NULL UNIQUE,
  password_hash varchar(255) NOT NULL,
  rol varchar(20) NOT NULL CHECK (rol IN ('cliente','vendedor','despachador','gerencia','admin')),
  activo boolean NOT NULL DEFAULT true,
  creado_en timestamptz NOT NULL DEFAULT now()
);

-- Vendedores que administran la cartera de clientes y los prospectos.
CREATE TABLE vendedor (
  vendedor_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  usuario_id integer NOT NULL UNIQUE REFERENCES usuario (usuario_id),
  nombre varchar(120) NOT NULL,
  telefono varchar(20),
  activo boolean NOT NULL DEFAULT true
);

-- Clientes B2B y B2C. Reemplaza la cartera que hoy vive en los celulares de los vendedores.
CREATE TABLE cliente (
  cliente_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  usuario_id integer UNIQUE REFERENCES usuario (usuario_id),
  tipo_cliente_id integer NOT NULL REFERENCES tipo_cliente (tipo_cliente_id),
  vendedor_id integer REFERENCES vendedor (vendedor_id),
  rut varchar(12) NOT NULL UNIQUE,
  nombre varchar(120) NOT NULL,
  email varchar(120) NOT NULL,
  telefono varchar(20),
  giro varchar(80),
  creado_en timestamptz NOT NULL DEFAULT now()
);

-- Direcciones de entrega de cada cliente.
CREATE TABLE direccion (
  direccion_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cliente_id integer NOT NULL REFERENCES cliente (cliente_id),
  calle_numero varchar(150) NOT NULL,
  comuna_id integer NOT NULL REFERENCES comuna (comuna_id),
  referencia varchar(150),
  es_principal boolean NOT NULL DEFAULT false,
  UNIQUE (direccion_id, cliente_id)
);

-- Carrito de compras de un cliente.
CREATE TABLE carrito (
  carrito_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cliente_id integer NOT NULL REFERENCES cliente (cliente_id),
  estado varchar(12) NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto','convertido','abandonado')),
  creado_en timestamptz NOT NULL DEFAULT now()
);

-- Productos y cantidades dentro de un carrito. El precio no se guarda: se calcula con la lista del cliente.
CREATE TABLE carrito_item (
  carrito_id integer NOT NULL REFERENCES carrito (carrito_id),
  producto_id integer NOT NULL REFERENCES producto (producto_id),
  cantidad integer NOT NULL CHECK (cantidad > 0),
  PRIMARY KEY (carrito_id, producto_id)
);

-- Estados por los que pasa una orden.
CREATE TABLE estado_orden (
  estado_orden_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(30) NOT NULL UNIQUE,
  orden_flujo smallint NOT NULL UNIQUE,
  es_final boolean NOT NULL DEFAULT false
);

-- Flota de camiones frigoríficos. La clave es el código que usa la telemetría (texto, según la pauta).
CREATE TABLE camion (
  camion_id varchar(20) PRIMARY KEY,
  patente varchar(8) NOT NULL UNIQUE,
  capacidad_kg integer NOT NULL CHECK (capacidad_kg > 0),
  rango_temperatura_id integer NOT NULL REFERENCES rango_temperatura (rango_temperatura_id),
  activo boolean NOT NULL DEFAULT true
);

-- Viaje de un camión con una o más órdenes. Su estado se deduce de las marcas de tiempo.
CREATE TABLE despacho (
  despacho_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  camion_id varchar(20) NOT NULL REFERENCES camion (camion_id),
  programado_para timestamptz NOT NULL,
  salida_en timestamptz,
  llegada_en timestamptz,
  CHECK (llegada_en IS NULL OR salida_en IS NOT NULL),
  CHECK (llegada_en IS NULL OR llegada_en >= salida_en)
);

-- Órdenes de compra generadas en el portal. El cliente, el canal y el total se obtienen por consulta (vistas v_orden y v_orden_total), no se guardan.
CREATE TABLE orden (
  orden_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  direccion_id integer NOT NULL REFERENCES direccion (direccion_id),
  estado_orden_id integer NOT NULL REFERENCES estado_orden (estado_orden_id),
  despacho_id integer REFERENCES despacho (despacho_id),
  numero_oc varchar(30),
  oc_pendiente boolean NOT NULL DEFAULT false,
  creada_en timestamptz NOT NULL DEFAULT now()
);

-- Líneas de una orden, con el precio vigente al momento de comprar.
CREATE TABLE orden_item (
  orden_id integer NOT NULL REFERENCES orden (orden_id),
  producto_id integer NOT NULL REFERENCES producto (producto_id),
  cantidad integer NOT NULL CHECK (cantidad > 0),
  precio_unitario_clp integer NOT NULL CHECK (precio_unitario_clp > 0),
  PRIMARY KEY (orden_id, producto_id)
);

-- Documentos tributarios simulados de una orden: boleta, factura, guía de despacho y nota de crédito. El monto es una foto de lo vendido, igual que el precio de la línea. Una orden tiene a lo más una boleta, una factura y una guía (índice único parcial sobre orden y tipo).
CREATE TABLE documento (
  documento_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tipo varchar(14) NOT NULL CHECK (tipo IN ('boleta','factura','guia_despacho','nota_credito')),
  folio integer NOT NULL,
  orden_id integer NOT NULL REFERENCES orden (orden_id),
  referencia_id integer REFERENCES documento (documento_id),
  monto_clp integer,
  vence_en date,
  motivo varchar(200),
  emitido_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tipo, folio),
  CHECK (tipo <> 'nota_credito' OR (referencia_id IS NOT NULL AND motivo IS NOT NULL)),
  CHECK (tipo = 'guia_despacho' OR monto_clp > 0)
);

-- Pagos recibidos contra una boleta o factura. El saldo de un documento es su monto menos los pagos y las notas de crédito. Un monto negativo es una devolución.
CREATE TABLE pago (
  pago_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  documento_id integer NOT NULL REFERENCES documento (documento_id),
  monto_clp integer NOT NULL CHECK (monto_clp <> 0),
  medio varchar(14) NOT NULL CHECK (medio IN ('webpay','transferencia','cheque','efectivo','devolucion')),
  referencia varchar(60),
  pagado_en timestamptz NOT NULL DEFAULT now()
);

-- Lecturas que envían los contenedores del simulador. Los nombres de campo son los que exige la pauta.
CREATE TABLE telemetria (
  telemetria_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  camion_id varchar(20) NOT NULL REFERENCES camion (camion_id),
  temp_camara double precision NOT NULL,
  lat double precision NOT NULL CHECK (lat BETWEEN -90 AND 90),
  "long" double precision NOT NULL CHECK ("long" BETWEEN -180 AND 180),
  combustible_pct integer NOT NULL CHECK (combustible_pct BETWEEN 0 AND 100),
  alerta_ruptura_frio boolean NOT NULL,
  registrado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (camion_id, registrado_en)
);

-- Etapas del embudo comercial.
CREATE TABLE etapa_pipeline (
  etapa_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(30) NOT NULL UNIQUE,
  orden_etapa smallint NOT NULL UNIQUE,
  es_final boolean NOT NULL DEFAULT false,
  es_ganada boolean NOT NULL DEFAULT false,
  CHECK (NOT es_ganada OR es_final)
);

-- Posibles clientes que sigue un vendedor a lo largo del embudo.
CREATE TABLE prospecto (
  prospecto_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  vendedor_id integer NOT NULL REFERENCES vendedor (vendedor_id),
  etapa_id integer NOT NULL REFERENCES etapa_pipeline (etapa_id),
  cliente_id integer REFERENCES cliente (cliente_id),
  nombre_contacto varchar(120) NOT NULL,
  empresa varchar(120),
  email varchar(120),
  telefono varchar(20),
  origen varchar(20) NOT NULL CHECK (origen IN ('web','referido','llamada','feria','otro')),
  monto_estimado_clp integer CHECK (monto_estimado_clp >= 0),
  creado_en timestamptz NOT NULL DEFAULT now(),
  cerrado_en timestamptz,
  motivo_perdida varchar(200),
  CHECK (email IS NOT NULL OR telefono IS NOT NULL),
  CHECK (cerrado_en IS NOT NULL OR motivo_perdida IS NULL)
);

-- Llamadas, correos, reuniones y notas registradas en la ficha de un prospecto o cliente.
CREATE TABLE interaccion (
  interaccion_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  vendedor_id integer NOT NULL REFERENCES vendedor (vendedor_id),
  prospecto_id integer REFERENCES prospecto (prospecto_id),
  cliente_id integer REFERENCES cliente (cliente_id),
  tipo varchar(10) NOT NULL CHECK (tipo IN ('llamada','correo','reunion','nota')),
  detalle text NOT NULL,
  registrada_en timestamptz NOT NULL DEFAULT now(),
  CHECK (prospecto_id IS NOT NULL OR cliente_id IS NOT NULL)
);

-- Categorías con las que se clasifican consultas y reclamos.
CREATE TABLE categoria_requerimiento (
  categoria_requerimiento_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(40) NOT NULL UNIQUE
);

-- Consultas y reclamos de clientes, clasificados por la IA.
CREATE TABLE requerimiento (
  requerimiento_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cliente_id integer REFERENCES cliente (cliente_id),
  orden_id integer REFERENCES orden (orden_id),
  asunto varchar(150) NOT NULL,
  descripcion text NOT NULL,
  categoria_requerimiento_id integer REFERENCES categoria_requerimiento (categoria_requerimiento_id),
  confianza_ia numeric(3,2) CHECK (confianza_ia BETWEEN 0 AND 1),
  estado varchar(14) NOT NULL DEFAULT 'sin_clasificar' CHECK (estado IN ('sin_clasificar','clasificado','resuelto')),
  creado_en timestamptz NOT NULL DEFAULT now(),
  respondido_en timestamptz,
  CHECK (respondido_en IS NULL OR respondido_en >= creado_en)
);

-- Índices pensados para las consultas del dashboard y de la torre de control.
CREATE INDEX idx_telemetria_camion_fecha ON telemetria (camion_id, registrado_en DESC);
CREATE INDEX idx_telemetria_alerta ON telemetria (registrado_en) WHERE alerta_ruptura_frio;
CREATE INDEX idx_orden_direccion ON orden (direccion_id);
CREATE INDEX idx_direccion_cliente ON direccion (cliente_id);
CREATE INDEX idx_orden_creada ON orden (creada_en);
CREATE INDEX idx_prospecto_vendedor_etapa ON prospecto (vendedor_id, etapa_id);
-- Un cliente solo puede tener un carrito abierto.
CREATE UNIQUE INDEX uq_carrito_abierto ON carrito (cliente_id) WHERE estado = 'abierto';
-- Una dirección principal por cliente.
CREATE UNIQUE INDEX uq_direccion_principal ON direccion (cliente_id) WHERE es_principal;

-- Vistas de apoyo: el cliente y el canal de una orden se obtienen por la dirección de entrega,
-- y el total se calcula desde sus líneas. No se guardan en la tabla orden para mantener la 3FN.
CREATE VIEW v_orden AS
SELECT o.orden_id, d.cliente_id, tc.codigo AS canal, o.estado_orden_id, o.despacho_id, o.numero_oc, o.creada_en
FROM orden o
JOIN direccion d ON d.direccion_id = o.direccion_id
JOIN cliente c ON c.cliente_id = d.cliente_id
JOIN tipo_cliente tc ON tc.tipo_cliente_id = c.tipo_cliente_id;

CREATE VIEW v_orden_total AS
SELECT orden_id, sum(cantidad * precio_unitario_clp) AS total_clp, sum(cantidad) AS unidades
FROM orden_item GROUP BY orden_id;
