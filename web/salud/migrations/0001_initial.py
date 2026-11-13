from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ChequeoServicio',
            fields=[
                ('chequeo_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('servicio', models.CharField(max_length=20)),
                ('momento', models.DateTimeField()),
                ('estado', models.CharField(choices=[('ok', 'Operativo'), ('degradado', 'Degradado'), ('caido', 'Caído')], max_length=10)),
                ('ms', models.IntegerField(blank=True, null=True)),
                ('detalle', models.CharField(blank=True, max_length=80)),
            ],
            options={
                'db_table': 'chequeo_servicio',
                'indexes': [models.Index(fields=['servicio', '-momento'], name='idx_chequeo_servicio_momento'), models.Index(fields=['-momento'], name='idx_chequeo_momento')],
            },
        ),
    ]
