import django.db.models.deletion
from django.db import migrations, models

SEGMENTOS = ["Hospital", "Supermercado", "Feria", "Institucional"]


def crear_segmentos(apps, schema_editor):
    Segmento = apps.get_model("clientes", "SegmentoCliente")
    for nombre in SEGMENTOS:
        Segmento.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0003_credito_giro"),
    ]

    operations = [
        migrations.CreateModel(
            name="SegmentoCliente",
            fields=[
                ("segmento_id", models.AutoField(primary_key=True, serialize=False)),
                ("nombre", models.CharField(max_length=40, unique=True)),
            ],
            options={"db_table": "segmento_cliente"},
        ),
        migrations.AddField(
            model_name="cliente",
            name="segmento",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    to="clientes.segmentocliente"),
        ),
        migrations.RunPython(crear_segmentos, migrations.RunPython.noop),
    ]
