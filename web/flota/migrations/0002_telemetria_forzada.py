from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("flota", "0001_initial")]
    operations = [migrations.AddField(model_name="telemetria", name="forzada", field=models.BooleanField(default=False, db_default=False))]
