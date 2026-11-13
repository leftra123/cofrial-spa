from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0004_segmento_cliente"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AceptacionLegal",
            fields=[
                ("aceptacion_id", models.AutoField(primary_key=True, serialize=False)),
                ("version", models.CharField(max_length=20)),
                ("aceptado_en", models.DateTimeField(auto_now_add=True)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "aceptación de términos",
                "verbose_name_plural": "aceptaciones de términos",
                "db_table": "aceptacion_legal",
            },
        ),
    ]
