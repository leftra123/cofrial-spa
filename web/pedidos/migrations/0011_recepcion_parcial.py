from django.db import migrations, models
from django.db.models import F, Q

VISTA_CON_RECHAZO = """
CREATE OR REPLACE VIEW v_orden_total AS
SELECT orden_id, sum((cantidad - cantidad_rechazada) * precio_unitario_clp) AS total_clp, sum(cantidad - cantidad_rechazada) AS unidades,
       sum(cantidad_rechazada * precio_unitario_clp) AS rechazado_clp, sum(cantidad_rechazada) AS unidades_rechazadas
FROM orden_item GROUP BY orden_id;
"""
VISTA_ANTERIOR = """
DROP VIEW v_orden_total;
CREATE VIEW v_orden_total AS
SELECT orden_id, sum(cantidad * precio_unitario_clp) AS total_clp, sum(cantidad) AS unidades
FROM orden_item GROUP BY orden_id;
"""
RECHAZADA = "Rechazada en recepción"
FLUJO = 9


def crear_estado(apps, schema_editor):
    """Una base nueva aún no tiene estados: los crea cargar_demo, con este mismo orden."""
    Estado = apps.get_model("pedidos", "EstadoOrden")
    if Estado.objects.exists():
        Estado.objects.get_or_create(nombre=RECHAZADA, defaults={"orden_flujo": FLUJO, "es_final": True})


def quitar_estado(apps, schema_editor):
    apps.get_model("pedidos", "EstadoOrden").objects.filter(nombre=RECHAZADA, orden__isnull=True).delete()


class Migration(migrations.Migration):
    """RN-23, recepción parcial. Lo rechazado se guarda por línea; lo aceptado se calcula. La vista v_orden_total pasa a sumar lo
    aceptado para que el tablero de BI vea ventas reales, y entrega aparte lo rechazado. Con CREATE OR REPLACE conserva los permisos de grafana_ro."""

    dependencies = [("pedidos", "0010_orden_comprobante")]

    operations = [
        migrations.AddField(model_name="ordenitem", name="cantidad_rechazada", field=models.IntegerField(db_default=0, default=0)),
        migrations.AddField(
            model_name="ordenitem",
            name="motivo_rechazo",
            field=models.CharField(blank=True, choices=[("temperatura", "Los productos llegaron tibios o descongelados"), ("faltante", "Faltan o sobran productos"),
                                                        ("danado", "Producto dañado o en mal estado"), ("otro", "Otro problema")],
                                   db_default="", default="", max_length=12),
        ),
        migrations.AddConstraint(
            model_name="ordenitem",
            constraint=models.CheckConstraint(condition=Q(cantidad_rechazada__gte=0, cantidad_rechazada__lte=F("cantidad")), name="orden_item_rechazo_en_rango"),
        ),
        migrations.AddConstraint(
            model_name="ordenitem",
            constraint=models.CheckConstraint(condition=Q(cantidad_rechazada=0, motivo_rechazo="") | Q(cantidad_rechazada__gt=0, motivo_rechazo__in=["temperatura", "faltante", "danado", "otro"]),
                                              name="orden_item_rechazo_con_motivo"),
        ),
        migrations.RunSQL(VISTA_CON_RECHAZO, VISTA_ANTERIOR),
        migrations.RunPython(crear_estado, quitar_estado),
    ]
