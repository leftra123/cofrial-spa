from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("flota", "0003_ciclo_entrega")]

    operations = [
        migrations.AddField("despacho", "decision_auto", models.TextField(blank=True, null=True)),
        migrations.AddField("despacho", "decision_ia", models.TextField(blank=True, null=True)),
    ]
