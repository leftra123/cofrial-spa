from django.db import migrations, models


def credito_b2b(apps, schema_editor):
    """Las instituciones (B2B) pagan a 30 días; el público general paga al comprar."""
    apps.get_model("clientes", "TipoCliente").objects.filter(codigo="B2B").update(dias_credito=30)


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0002_direccion_ubicacion"),
    ]

    operations = [
        migrations.AddField(model_name="tipocliente", name="dias_credito",
                            field=models.PositiveSmallIntegerField(db_default=0, default=0)),
        migrations.AddField(model_name="cliente", name="giro",
                            field=models.CharField(blank=True, max_length=80)),
        migrations.RunPython(credito_b2b, migrations.RunPython.noop),
    ]
