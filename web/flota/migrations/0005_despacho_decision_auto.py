from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("flota", "0004_escenario_simulador")]

    operations = [
        migrations.AddField("despacho", "decision_auto", models.TextField(blank=True, null=True)),
        migrations.AddField("despacho", "decision_ia", models.TextField(blank=True, null=True)),
    ]
