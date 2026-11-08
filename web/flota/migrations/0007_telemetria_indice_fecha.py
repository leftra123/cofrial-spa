from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Índice por fecha para el sondeo de la Torre. Se crea sin bloquear la tabla: el simulador sigue insertando mientras tanto."""

    atomic = False      # CREATE INDEX CONCURRENTLY no corre dentro de una transacción

    dependencies = [
        ('flota', '0006_ajuste_simulador'),
    ]

    operations = [
        AddIndexConcurrently(
            model_name='telemetria',
            index=models.Index(fields=['-registrado_en'], name='idx_telemetria_fecha'),
        ),
    ]
