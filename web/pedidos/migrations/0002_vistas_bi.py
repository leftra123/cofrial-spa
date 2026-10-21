from django.db import migrations

# Vistas de apoyo del diseño (informe/modelo/esquema.sql): el cliente y el canal de una orden salen de la
# dirección de entrega y el total de sus líneas; no se guardan en la tabla orden para mantener la 3FN.
VISTAS = """
CREATE VIEW v_orden AS
SELECT o.orden_id, d.cliente_id, tc.codigo AS canal, o.estado_orden_id, o.despacho_id, o.numero_oc, o.creada_en
FROM orden o
JOIN direccion d ON d.direccion_id = o.direccion_id
JOIN cliente c ON c.cliente_id = d.cliente_id
JOIN tipo_cliente tc ON tc.tipo_cliente_id = c.tipo_cliente_id;

CREATE VIEW v_orden_total AS
SELECT orden_id, sum(cantidad * precio_unitario_clp) AS total_clp, sum(cantidad) AS unidades
FROM orden_item GROUP BY orden_id;
"""


class Migration(migrations.Migration):
    dependencies = [("pedidos", "0001_initial")]
    operations = [migrations.RunSQL(VISTAS, "DROP VIEW v_orden_total; DROP VIEW v_orden;")]
