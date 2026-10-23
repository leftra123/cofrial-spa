"""Fuente única del modelo de datos de Cofrial SpA.

Desde esta definición se generan el script SQL (esquema.sql), el diagrama Mermaid (er.mmd)
y el diccionario de datos de informe/04b-modelo-datos.md, de modo que los tres nunca se
contradigan. Ejecutar desde la raíz del repositorio:

    python3 informe/modelo/modelo.py          # esquema.sql, er.mmd y diccionario del informe
    python3 informe/modelo/modelo.py --png    # además exporta informe/img/mer-3fn.png (requiere Google Chrome e internet)
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def c(nombre, tipo, desc, ej, nulo=False, fk=None, uk=False, check=None, default=None):
    return dict(nombre=nombre, tipo=tipo, desc=desc, ej=ej, nulo=nulo, fk=fk, uk=uk, check=check, default=default)


def pk(nombre, desc, ej, tipo="integer"):
    return dict(nombre=nombre, tipo=tipo, desc=desc, ej=ej, nulo=False, fk=None, uk=False, check=None, default=None, pk=True)


T = []  # tablas en orden de dependencia


def tabla(nombre, grupo, desc, cols, pk_comp=None, extra=None):
    T.append(dict(nombre=nombre, grupo=grupo, desc=desc, cols=cols, pk_comp=pk_comp, extra=extra or []))


# ---------------------------------------------------------------- Geografía y catálogos de frío
tabla("region", "Geografía", "Regiones de Chile donde se entregan pedidos.", [
    pk("region_id", "Identificador de la región.", "9"),
    c("nombre", "varchar(60)", "Nombre de la región.", "La Araucanía", uk=True),
])
tabla("comuna", "Geografía", "Comunas, cada una dentro de una región. La región no se repite en la dirección.", [
    pk("comuna_id", "Identificador de la comuna.", "1"),
    c("region_id", "integer", "Región a la que pertenece.", "9", fk="region"),
    c("nombre", "varchar(60)", "Nombre de la comuna.", "Temuco"),
], extra=["UNIQUE (region_id, nombre)"])
tabla("rango_temperatura", "Cadena de frío", "Rangos de temperatura de conservación. Definen cuándo una lectura es crítica.", [
    pk("rango_temperatura_id", "Identificador del rango.", "1"),
    c("nombre", "varchar(40)", "Nombre del rango.", "Refrigerado", uk=True),
    c("temp_min_c", "numeric(5,1)", "Temperatura mínima permitida en grados Celsius.", "0.0"),
    c("temp_max_c", "numeric(5,1)", "Temperatura máxima permitida en grados Celsius.", "4.0"),
], extra=["CHECK (temp_min_c < temp_max_c)"])

# ---------------------------------------------------------------- Comercial
tabla("categoria", "Comercial", "Categorías de producto. Cada una exige un rango de temperatura de conservación.", [
    pk("categoria_id", "Identificador de la categoría.", "1"),
    c("nombre", "varchar(60)", "Nombre de la categoría.", "Cárnicos refrigerados", uk=True),
    c("rango_temperatura_id", "integer", "Rango de conservación que exige la categoría.", "1", fk="rango_temperatura"),
])
tabla("producto", "Comercial", "Productos del catálogo de refrigerados y congelados.", [
    pk("producto_id", "Identificador del producto.", "101"),
    c("sku", "varchar(30)", "Código interno único del producto.", "VAC-LOM-5K", uk=True),
    c("nombre", "varchar(120)", "Nombre comercial.", "Lomo vetado de vacuno 5 kg"),
    c("descripcion", "text", "Descripción para el catálogo.", "Corte envasado al vacío", nulo=True),
    c("categoria_id", "integer", "Categoría del producto.", "1", fk="categoria"),
    c("unidad_medida", "varchar(10)", "Unidad en que se vende.", "caja", check="unidad_medida IN ('kg','un','caja')"),
    c("stock_disponible", "integer", "Unidades disponibles en bodega. Se descuenta al generar una orden.", "120", check="stock_disponible >= 0", default="0"),
    c("activo", "boolean", "Si se muestra en el catálogo.", "true", default="true"),
])
tabla("lista_precio", "Comercial", "Listas de precios: institucional para B2B y pública para B2C.", [
    pk("lista_precio_id", "Identificador de la lista.", "1"),
    c("nombre", "varchar(60)", "Nombre de la lista.", "Institucional B2B", uk=True),
])
tabla("precio_producto", "Comercial", "Precio de cada producto en cada lista de precios.", [
    c("lista_precio_id", "integer", "Lista de precios.", "1", fk="lista_precio"),
    c("producto_id", "integer", "Producto.", "101", fk="producto"),
    c("precio_clp", "integer", "Precio unitario en pesos chilenos, sin decimales.", "38990", check="precio_clp > 0"),
], pk_comp=["lista_precio_id", "producto_id"])
tabla("tipo_cliente", "Comercial", "Tipos de cliente. Cada tipo usa una lista de precios, así el cliente no la repite.", [
    pk("tipo_cliente_id", "Identificador del tipo.", "1"),
    c("codigo", "varchar(3)", "Código del canal.", "B2B", uk=True, check="codigo IN ('B2B','B2C')"),
    c("nombre", "varchar(40)", "Nombre descriptivo.", "Institucional"),
    c("lista_precio_id", "integer", "Lista de precios que le corresponde.", "1", fk="lista_precio"),
])

# ---------------------------------------------------------------- Usuarios y clientes
tabla("usuario", "Clientes", "Cuentas de acceso al portal, al CRM y al panel. Si el framework trae su propia autenticación, reemplaza esta tabla.", [
    pk("usuario_id", "Identificador de la cuenta.", "1"),
    c("email", "varchar(120)", "Correo de acceso.", "compras@hospital.cl", uk=True),
    c("password_hash", "varchar(255)", "Contraseña cifrada (nunca en texto plano).", "pbkdf2_sha256$..."),
    c("rol", "varchar(20)", "Rol que define los permisos.", "cliente", check="rol IN ('cliente','vendedor','despachador','gerencia','admin')"),
    c("activo", "boolean", "Si la cuenta puede iniciar sesión.", "true", default="true"),
    c("creado_en", "timestamptz", "Fecha y hora de creación.", "2026-10-12 09:30:00-03", default="now()"),
])
tabla("vendedor", "CRM", "Vendedores que administran la cartera de clientes y los prospectos.", [
    pk("vendedor_id", "Identificador del vendedor.", "1"),
    c("usuario_id", "integer", "Cuenta con la que ingresa al CRM.", "7", fk="usuario", uk=True),
    c("nombre", "varchar(120)", "Nombre completo.", "María Paz Soto"),
    c("telefono", "varchar(20)", "Teléfono de contacto.", "+56912345678", nulo=True),
    c("activo", "boolean", "Si sigue en funciones.", "true", default="true"),
])
tabla("cliente", "Clientes", "Clientes B2B y B2C. Reemplaza la cartera que hoy vive en los celulares de los vendedores.", [
    pk("cliente_id", "Identificador del cliente.", "15"),
    c("usuario_id", "integer", "Cuenta de acceso al portal, si ya la tiene.", "12", fk="usuario", uk=True, nulo=True),
    c("tipo_cliente_id", "integer", "Canal del cliente (B2B o B2C).", "1", fk="tipo_cliente"),
    c("vendedor_id", "integer", "Vendedor que atiende la cuenta (aplica a B2B).", "1", fk="vendedor", nulo=True),
    c("rut", "varchar(12)", "RUT del cliente o de la empresa.", "61.973.200-4", uk=True),
    c("nombre", "varchar(120)", "Nombre de la persona o razón social.", "Hospital Regional de Temuco"),
    c("email", "varchar(120)", "Correo de contacto.", "abastecimiento@hospital.cl"),
    c("telefono", "varchar(20)", "Teléfono de contacto.", "+56452123456", nulo=True),
    c("creado_en", "timestamptz", "Fecha de alta.", "2026-10-12 09:30:00-03", default="now()"),
])
tabla("direccion", "Clientes", "Direcciones de entrega de cada cliente.", [
    pk("direccion_id", "Identificador de la dirección.", "30"),
    c("cliente_id", "integer", "Cliente dueño de la dirección.", "15", fk="cliente"),
    c("calle_numero", "varchar(150)", "Calle y número.", "Manuel Montt 115"),
    c("comuna_id", "integer", "Comuna (de ahí se obtiene la región).", "1", fk="comuna"),
    c("referencia", "varchar(150)", "Indicación para el conductor.", "Entrada de bodega, portón 2", nulo=True),
    c("es_principal", "boolean", "Si es la dirección por defecto.", "true", default="false"),
], extra=["UNIQUE (direccion_id, cliente_id)"])

# ---------------------------------------------------------------- Carrito y órdenes
tabla("carrito", "Comercial", "Carrito de compras de un cliente.", [
    pk("carrito_id", "Identificador del carrito.", "55"),
    c("cliente_id", "integer", "Cliente dueño del carrito.", "15", fk="cliente"),
    c("estado", "varchar(12)", "Estado del carrito.", "abierto", check="estado IN ('abierto','convertido','abandonado')", default="'abierto'"),
    c("creado_en", "timestamptz", "Fecha y hora de creación.", "2026-10-12 10:05:00-03", default="now()"),
])
tabla("carrito_item", "Comercial", "Productos y cantidades dentro de un carrito. El precio no se guarda: se calcula con la lista del cliente.", [
    c("carrito_id", "integer", "Carrito.", "55", fk="carrito"),
    c("producto_id", "integer", "Producto.", "101", fk="producto"),
    c("cantidad", "integer", "Cantidad solicitada.", "10", check="cantidad > 0"),
], pk_comp=["carrito_id", "producto_id"])
tabla("estado_orden", "Comercial", "Estados por los que pasa una orden.", [
    pk("estado_orden_id", "Identificador del estado.", "1"),
    c("nombre", "varchar(30)", "Nombre del estado.", "Recibida", uk=True),
    c("orden_flujo", "smallint", "Posición en el flujo del pedido.", "1", uk=True),
    c("es_final", "boolean", "Si cierra el pedido (entregada o cancelada).", "false", default="false"),
])
tabla("camion", "Logística", "Flota de camiones frigoríficos. La clave es el código que usa la telemetría (texto, según la pauta).", [
    pk("camion_id", "Código del camión, el mismo que envía la telemetría.", "CAM-01", tipo="varchar(20)"),
    c("patente", "varchar(8)", "Patente del vehículo.", "HJKL-42", uk=True),
    c("capacidad_kg", "integer", "Capacidad de carga en kilos.", "8000", check="capacidad_kg > 0"),
    c("rango_temperatura_id", "integer", "Rango en que opera su cámara.", "1", fk="rango_temperatura"),
    c("activo", "boolean", "Si está en servicio.", "true", default="true"),
])
tabla("despacho", "Logística", "Viaje de un camión con una o más órdenes. Su estado se deduce de las marcas de tiempo.", [
    pk("despacho_id", "Identificador del despacho.", "88"),
    c("camion_id", "varchar(20)", "Camión asignado.", "CAM-01", fk="camion"),
    c("programado_para", "timestamptz", "Salida planificada.", "2026-10-13 07:00:00-03"),
    c("salida_en", "timestamptz", "Salida real (vacío si aún no sale).", "2026-10-13 07:12:00-03", nulo=True),
    c("llegada_en", "timestamptz", "Cierre del viaje (vacío si sigue en ruta).", "2026-10-13 11:40:00-03", nulo=True),
], extra=["CHECK (llegada_en IS NULL OR salida_en IS NOT NULL)", "CHECK (llegada_en IS NULL OR llegada_en >= salida_en)"])
tabla("orden", "Comercial", "Órdenes de compra generadas en el portal. El cliente, el canal y el total se obtienen por consulta (vistas v_orden y v_orden_total), no se guardan.", [
    pk("orden_id", "Identificador de la orden.", "1001"),
    c("direccion_id", "integer", "Dirección de entrega. De ella se obtiene el cliente que compra.", "30", fk="direccion"),
    c("estado_orden_id", "integer", "Estado actual.", "1", fk="estado_orden"),
    c("despacho_id", "integer", "Despacho que la lleva (vacío hasta asignarla).", "88", fk="despacho", nulo=True),
    c("numero_oc", "varchar(30)", "Número de orden de compra del cliente (B2B).", "OC-2026-0457", nulo=True),
    c("creada_en", "timestamptz", "Fecha y hora de la orden.", "2026-10-12 10:20:00-03", default="now()"),
])
tabla("orden_item", "Comercial", "Líneas de una orden, con el precio vigente al momento de comprar.", [
    c("orden_id", "integer", "Orden.", "1001", fk="orden"),
    c("producto_id", "integer", "Producto.", "101", fk="producto"),
    c("cantidad", "integer", "Cantidad comprada.", "10", check="cantidad > 0"),
    c("precio_unitario_clp", "integer", "Precio pagado por unidad, copiado de la lista al comprar.", "38990", check="precio_unitario_clp > 0"),
], pk_comp=["orden_id", "producto_id"])

# ---------------------------------------------------------------- IoT
tabla("telemetria", "Logística e IoT", "Lecturas que envían los contenedores del simulador. Los nombres de campo son los que exige la pauta.", [
    pk("telemetria_id", "Identificador de la lectura.", "250311", tipo="bigint"),
    c("camion_id", "varchar(20)", "Camión que reporta (string).", "CAM-01", fk="camion"),
    c("temp_camara", "double precision", "Temperatura de la cámara en grados Celsius (float).", "3.6"),
    c("lat", "double precision", "Latitud en grados decimales.", "-38.7359", check="lat BETWEEN -90 AND 90"),
    c("long", "double precision", "Longitud en grados decimales. En SQL se escribe entre comillas.", "-72.5904", check='"long" BETWEEN -180 AND 180'),
    c("combustible_pct", "integer", "Nivel de combustible, de 0 a 100 (integer).", "64", check="combustible_pct BETWEEN 0 AND 100"),
    c("alerta_ruptura_frio", "boolean", "Verdadero si temp_camara sale del rango crítico del camión.", "false"),
    c("registrado_en", "timestamptz", "Momento de la lectura.", "2026-10-13 08:15:05-03", default="now()"),
], extra=["UNIQUE (camion_id, registrado_en)"])

# ---------------------------------------------------------------- CRM
tabla("etapa_pipeline", "CRM", "Etapas del embudo comercial.", [
    pk("etapa_id", "Identificador de la etapa.", "1"),
    c("nombre", "varchar(30)", "Nombre de la etapa.", "Propuesta enviada", uk=True),
    c("orden_etapa", "smallint", "Posición en el embudo.", "3", uk=True),
    c("es_final", "boolean", "Si cierra la oportunidad.", "false", default="false"),
    c("es_ganada", "boolean", "Si el cierre es una venta lograda.", "false", default="false"),
], extra=["CHECK (NOT es_ganada OR es_final)"])
tabla("prospecto", "CRM", "Posibles clientes que sigue un vendedor a lo largo del embudo.", [
    pk("prospecto_id", "Identificador del prospecto.", "40"),
    c("vendedor_id", "integer", "Vendedor responsable.", "1", fk="vendedor"),
    c("etapa_id", "integer", "Etapa actual del embudo.", "2", fk="etapa_pipeline"),
    c("cliente_id", "integer", "Cliente en que se convirtió (vacío mientras no se gane).", "15", fk="cliente", nulo=True),
    c("nombre_contacto", "varchar(120)", "Persona de contacto.", "Carlos Muñoz"),
    c("empresa", "varchar(120)", "Empresa u organización.", "Supermercado El Sur", nulo=True),
    c("email", "varchar(120)", "Correo de contacto.", "cmunoz@elsur.cl", nulo=True),
    c("telefono", "varchar(20)", "Teléfono de contacto.", "+56987654321", nulo=True),
    c("origen", "varchar(20)", "Cómo llegó el prospecto.", "web", check="origen IN ('web','referido','llamada','feria','otro')"),
    c("monto_estimado_clp", "integer", "Venta mensual estimada en pesos.", "2500000", nulo=True, check="monto_estimado_clp >= 0"),
    c("creado_en", "timestamptz", "Fecha de ingreso.", "2026-10-12 11:00:00-03", default="now()"),
    c("cerrado_en", "timestamptz", "Fecha de cierre (ganado o perdido); vacío mientras siga abierto.", "2026-10-20 16:00:00-03", nulo=True),
    c("motivo_perdida", "varchar(200)", "Por qué se perdió la venta; solo si el prospecto se cerró como perdido.", "Eligió otro proveedor por precio", nulo=True),
], extra=["CHECK (email IS NOT NULL OR telefono IS NOT NULL)", "CHECK (cerrado_en IS NOT NULL OR motivo_perdida IS NULL)"])
tabla("interaccion", "CRM", "Llamadas, correos, reuniones y notas registradas en la ficha de un prospecto o cliente.", [
    pk("interaccion_id", "Identificador de la interacción.", "300"),
    c("vendedor_id", "integer", "Vendedor que la registra.", "1", fk="vendedor"),
    c("prospecto_id", "integer", "Prospecto relacionado.", "40", fk="prospecto", nulo=True),
    c("cliente_id", "integer", "Cliente relacionado.", "15", fk="cliente", nulo=True),
    c("tipo", "varchar(10)", "Tipo de interacción.", "llamada", check="tipo IN ('llamada','correo','reunion','nota')"),
    c("detalle", "text", "Resumen de lo conversado.", "Se envía propuesta de precios"),
    c("registrada_en", "timestamptz", "Fecha y hora.", "2026-10-12 12:30:00-03", default="now()"),
], extra=["CHECK (prospecto_id IS NOT NULL OR cliente_id IS NOT NULL)"])
tabla("categoria_requerimiento", "CRM", "Categorías con las que se clasifican consultas y reclamos.", [
    pk("categoria_requerimiento_id", "Identificador de la categoría.", "4"),
    c("nombre", "varchar(40)", "Nombre de la categoría.", "Calidad o frío", uk=True),
])
tabla("requerimiento", "CRM", "Consultas y reclamos de clientes, clasificados por la IA.", [
    pk("requerimiento_id", "Identificador del requerimiento.", "500"),
    c("cliente_id", "integer", "Cliente que lo envía (vacío si es una consulta anónima).", "15", fk="cliente", nulo=True),
    c("orden_id", "integer", "Orden a la que se refiere.", "1001", fk="orden", nulo=True),
    c("asunto", "varchar(150)", "Asunto del mensaje.", "Llegó tibia la carga"),
    c("descripcion", "text", "Texto completo del cliente.", "El pedido llegó con la cadena de frío cortada."),
    c("categoria_requerimiento_id", "integer", "Categoría asignada por la IA (vacía si no pudo clasificar).", "4", fk="categoria_requerimiento", nulo=True),
    c("confianza_ia", "numeric(3,2)", "Seguridad de la clasificación, entre 0 y 1.", "0.91", nulo=True, check="confianza_ia BETWEEN 0 AND 1"),
    c("estado", "varchar(14)", "Estado del requerimiento.", "clasificado", check="estado IN ('sin_clasificar','clasificado','resuelto')", default="'sin_clasificar'"),
    c("creado_en", "timestamptz", "Fecha y hora de ingreso.", "2026-10-13 12:00:00-03", default="now()"),
    c("respondido_en", "timestamptz", "Fecha y hora de la primera respuesta al cliente (vacío si aún no se responde).", "2026-10-13 12:40:00-03", nulo=True),
], extra=["CHECK (respondido_en IS NULL OR respondido_en >= creado_en)"])

# ---------------------------------------------------------------- Relaciones para el diagrama
REL = [
    ("region", "||--o{", "comuna", "contiene"), ("comuna", "||--o{", "direccion", "ubica"),
    ("rango_temperatura", "||--o{", "categoria", "exige"), ("rango_temperatura", "||--o{", "camion", "opera en"),
    ("categoria", "||--o{", "producto", "agrupa"), ("lista_precio", "||--o{", "precio_producto", "fija"),
    ("producto", "||--o{", "precio_producto", "tiene"), ("lista_precio", "||--o{", "tipo_cliente", "usa"),
    ("tipo_cliente", "||--o{", "cliente", "clasifica"), ("usuario", "|o--o|", "cliente", "accede como"),
    ("usuario", "||--o|", "vendedor", "accede como"), ("vendedor", "|o--o{", "cliente", "atiende"),
    ("cliente", "||--o{", "direccion", "registra"), ("cliente", "||--o{", "carrito", "arma"),
    ("carrito", "||--o{", "carrito_item", "contiene"), ("producto", "||--o{", "carrito_item", "se agrega"),
    ("direccion", "||--o{", "orden", "recibe"),
    ("estado_orden", "||--o{", "orden", "describe"), ("despacho", "|o--o{", "orden", "transporta"),
    ("orden", "||--o{", "orden_item", "detalla"), ("producto", "||--o{", "orden_item", "se vende"),
    ("camion", "||--o{", "despacho", "realiza"), ("camion", "||--o{", "telemetria", "reporta"),
    ("vendedor", "||--o{", "prospecto", "gestiona"), ("etapa_pipeline", "||--o{", "prospecto", "ubica"),
    ("cliente", "|o--o{", "prospecto", "nace de"), ("vendedor", "||--o{", "interaccion", "registra"),
    ("prospecto", "|o--o{", "interaccion", "recibe"), ("cliente", "|o--o{", "interaccion", "recibe"),
    ("cliente", "|o--o{", "requerimiento", "envia"), ("orden", "|o--o{", "requerimiento", "motiva"),
    ("categoria_requerimiento", "|o--o{", "requerimiento", "clasifica"),
]


def claves(col, t):
    k = []
    if col.get("pk") or (t["pk_comp"] and col["nombre"] in t["pk_comp"]):
        k.append("PK")
    if col["fk"]:
        k.append(f"FK → {col['fk']}")
    if col["uk"]:
        k.append("UK")
    return ", ".join(k) or "—"


def sql_col(col, t):
    n = f'"{col["nombre"]}"' if col["nombre"] == "long" else col["nombre"]
    if col.get("pk") and not t["pk_comp"]:
        if col["tipo"] == "varchar(20)":
            return f"  {n} {col['tipo']} PRIMARY KEY"
        return f"  {n} {col['tipo']} GENERATED ALWAYS AS IDENTITY PRIMARY KEY"
    s = f"  {n} {col['tipo']}"
    if not col["nulo"]:
        s += " NOT NULL"
    if col["default"]:
        s += f" DEFAULT {col['default']}"
    if col["uk"]:
        s += " UNIQUE"
    if col["fk"]:
        pkcol = next(x["nombre"] for x in next(tt for tt in T if tt["nombre"] == col["fk"])["cols"] if x.get("pk"))
        s += f" REFERENCES {col['fk']} ({pkcol})"
    if col["check"]:
        s += f" CHECK ({col['check']})"
    return s


def generar_sql():
    out = ["-- Esquema de datos de Cofrial SpA (PostgreSQL). Generado por informe/modelo/modelo.py: no editar a mano.",
           "-- La columna \"long\" va entre comillas porque LONG es palabra reservada en SQL.", ""]
    for t in T:
        out.append(f"-- {t['desc']}")
        lines = [sql_col(c_, t) for c_ in t["cols"]]
        if t["pk_comp"]:
            lines.append(f"  PRIMARY KEY ({', '.join(t['pk_comp'])})")
        lines += [f"  {e}" for e in t["extra"]]
        out.append(f"CREATE TABLE {t['nombre']} (\n" + ",\n".join(lines) + "\n);")
        out.append("")
    out += [
        "-- Índices pensados para las consultas del dashboard y de la torre de control.",
        "CREATE INDEX idx_telemetria_camion_fecha ON telemetria (camion_id, registrado_en DESC);",
        "CREATE INDEX idx_telemetria_alerta ON telemetria (registrado_en) WHERE alerta_ruptura_frio;",
        "CREATE INDEX idx_orden_direccion ON orden (direccion_id);",
        "CREATE INDEX idx_direccion_cliente ON direccion (cliente_id);",
        "CREATE INDEX idx_orden_creada ON orden (creada_en);",
        "CREATE INDEX idx_prospecto_vendedor_etapa ON prospecto (vendedor_id, etapa_id);",
        "-- Un cliente solo puede tener un carrito abierto.",
        "CREATE UNIQUE INDEX uq_carrito_abierto ON carrito (cliente_id) WHERE estado = 'abierto';",
        "-- Una dirección principal por cliente.",
        "CREATE UNIQUE INDEX uq_direccion_principal ON direccion (cliente_id) WHERE es_principal;",
        "",
        "-- Vistas de apoyo: el cliente y el canal de una orden se obtienen por la dirección de entrega,",
        "-- y el total se calcula desde sus líneas. No se guardan en la tabla orden para mantener la 3FN.",
        "CREATE VIEW v_orden AS",
        "SELECT o.orden_id, d.cliente_id, tc.codigo AS canal, o.estado_orden_id, o.despacho_id, o.numero_oc, o.creada_en",
        "FROM orden o",
        "JOIN direccion d ON d.direccion_id = o.direccion_id",
        "JOIN cliente c ON c.cliente_id = d.cliente_id",
        "JOIN tipo_cliente tc ON tc.tipo_cliente_id = c.tipo_cliente_id;",
        "",
        "CREATE VIEW v_orden_total AS",
        "SELECT orden_id, sum(cantidad * precio_unitario_clp) AS total_clp, sum(cantidad) AS unidades",
        "FROM orden_item GROUP BY orden_id;",
        "",
    ]
    return "\n".join(out)


def generar_mermaid():
    out = ["erDiagram"]
    for a, rel, b, et in REL:
        out.append(f'  {a} {rel} {b} : "{et}"')
    for t in T:
        out.append(f"  {t['nombre']} {{")
        for col in t["cols"]:
            es_clave = col.get("pk") or (t["pk_comp"] and col["nombre"] in t["pk_comp"]) or col["fk"]
            if t["nombre"] == "telemetria" or es_clave:
                tipo = col["tipo"].split("(")[0].replace(" ", "_")
                marca = "PK" if (col.get("pk") or (t["pk_comp"] and col["nombre"] in t["pk_comp"])) else ("FK" if col["fk"] else "")
                out.append(f"    {tipo} {col['nombre']} {marca}".rstrip())
        out.append("  }")
    return "\n".join(out) + "\n"


def generar_diccionario():
    out = []
    grupos = []
    for t in T:
        if t["grupo"] not in grupos:
            grupos.append(t["grupo"])
    n = 0
    for g in grupos:
        out.append(f"### Tablas de {g}\n")
        for t in [x for x in T if x["grupo"] == g]:
            n += 1
            out.append(f"**Tabla D{n}**  \n*`{t['nombre']}`: {t['desc']}*\n")
            out.append("| Campo | Tipo | Nulo | Clave | Descripción | Ejemplo |")
            out.append("|---|---|---|---|---|---|")
            for col in t["cols"]:
                nulo = "Sí" if col["nulo"] else "No"
                out.append(f"| `{col['nombre']}` | {col['tipo']} | {nulo} | {claves(col, t)} | {col['desc']} | {col['ej']} |")
            if t["extra"] or any(col["check"] for col in t["cols"]):
                reglas = [f"`{e}`" for e in t["extra"]] + [f"`{col['check']}`" for col in t["cols"] if col["check"]]
                out.append(f"\n*Restricciones adicionales:* {'; '.join(reglas)}.")
            out.append("\n*Nota.* Elaboración propia.\n")
    return "\n".join(out)


def reemplazar(texto, marca, contenido):
    patron = re.compile(rf"(<!-- INICIO:{marca} -->\n).*?(<!-- FIN:{marca} -->)", re.S)
    if not patron.search(texto):
        raise SystemExit(f"Falta el marcador {marca} en 04b-modelo-datos.md")
    return patron.sub(lambda m: m.group(1) + contenido.rstrip("\n") + "\n" + m.group(2), texto)


def exportar_png(ancho=3000, alto=2000):
    """Dibuja el diagrama con Mermaid + ELK (trazado ortogonal) y lo captura con Chrome sin interfaz."""
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        raise SystemExit("No se encontró Google Chrome para exportar el PNG")
    pagina = (
        '<!doctype html><meta charset="utf-8"><body style="margin:0;background:#fff">'
        f'<pre class="mermaid">{html.escape(generar_mermaid())}</pre>'
        '<script type="module">'
        'import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";'
        'import elk from "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0/dist/mermaid-layout-elk.esm.min.mjs";'
        'mermaid.registerLayoutLoaders(elk);'
        'mermaid.initialize({startOnLoad:false,theme:"neutral",layout:"elk",er:{useMaxWidth:false},maxTextSize:200000});'
        'await mermaid.run();const b=document.querySelector("svg").getBoundingClientRect();document.title=Math.ceil(b.width)+"x"+Math.ceil(b.height);</script></body>'
    )
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "er.html"
        f.write_text(pagina, encoding="utf-8")
        destino = RAIZ / "informe/img/mer-3fn.png"
        medida = subprocess.run([str(chrome), "--headless=new", "--disable-gpu", "--virtual-time-budget=30000",
                                 "--dump-dom", f"file://{f}"], capture_output=True, text=True).stdout
        m = re.search(r"<title>(\d+)x(\d+)</title>", medida)
        if m:
            ancho, alto = int(m.group(1)) + 40, int(m.group(2)) + 40
        subprocess.run([str(chrome), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={ancho},{alto}", "--force-device-scale-factor=2",
                        "--virtual-time-budget=30000", f"--screenshot={destino}", f"file://{f}"],
                       check=True, capture_output=True)
    print(f"PNG exportado en {destino}")


if __name__ == "__main__":
    (RAIZ / "informe/modelo/esquema.sql").write_text(generar_sql(), encoding="utf-8")
    (RAIZ / "informe/modelo/er.mmd").write_text(generar_mermaid(), encoding="utf-8")
    md = RAIZ / "informe/04b-modelo-datos.md"
    if md.exists() and "<!-- INICIO:diccionario -->" in md.read_text(encoding="utf-8"):
        s = md.read_text(encoding="utf-8")
        s = reemplazar(s, "diagrama", "```mermaid\n" + generar_mermaid() + "```")
        s = reemplazar(s, "diccionario", generar_diccionario())
        md.write_text(s, encoding="utf-8")
    print(f"{len(T)} tablas generadas")
    if "--png" in sys.argv:
        exportar_png()
