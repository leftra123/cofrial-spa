from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_requerimiento_desglose'),
    ]

    operations = [
        migrations.AddField(
            model_name='requerimiento',
            name='canal',
            field=models.CharField(choices=[('soporte', 'Soporte'), ('asistente', 'Asistente de IA')], db_default='soporte', default='soporte', max_length=10),
        ),
        migrations.AddField(
            model_name='requerimiento',
            name='respuesta_ia',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='requerimiento',
            name='resuelto_por',
            field=models.CharField(blank=True, choices=[('ia', 'IA'), ('persona', 'Persona')], default='', max_length=8),
        ),
    ]
