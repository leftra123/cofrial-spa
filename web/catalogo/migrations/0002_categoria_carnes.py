from django.db import migrations


def renombrar(apps, schema_editor):
    """«Cárnicos refrigerados» pasa a llamarse «Carnes» (como se dice en las tiendas chilenas). Si ya existe «Carnes», no toca nada."""
    Categoria = apps.get_model("catalogo", "Categoria")
    if not Categoria.objects.filter(nombre="Carnes").exists():
        Categoria.objects.filter(nombre="Cárnicos refrigerados").update(nombre="Carnes")


def deshacer(apps, schema_editor):
    apps.get_model("catalogo", "Categoria").objects.filter(nombre="Carnes").update(nombre="Cárnicos refrigerados")


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0001_initial")]
    operations = [migrations.RunPython(renombrar, deshacer)]
