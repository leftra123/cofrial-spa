from django.db import migrations, models


def marcar_institucionales(apps, schema):
    Orden = apps.get_model("pedidos", "Orden")
    Orden.objects.filter(direccion__cliente__tipo_cliente__codigo="B2B").update(comprobante="factura")


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0008_checkoutpago_ids_mp"),
    ]

    operations = [
        migrations.AddField(
            model_name="orden",
            name="comprobante",
            field=models.CharField(choices=[("boleta", "Boleta"), ("factura", "Factura")], db_default="boleta", default="boleta", max_length=8),
        ),
        migrations.AddField(
            model_name="checkoutpago",
            name="comprobante",
            field=models.CharField(choices=[("boleta", "Boleta"), ("factura", "Factura")], db_default="boleta", default="boleta", max_length=8),
        ),
        migrations.AddConstraint(
            model_name="orden",
            constraint=models.CheckConstraint(condition=models.Q(comprobante__in=["boleta", "factura"]), name="orden_comprobante_valido"),
        ),
        migrations.RunPython(marcar_institucionales, migrations.RunPython.noop),
    ]
