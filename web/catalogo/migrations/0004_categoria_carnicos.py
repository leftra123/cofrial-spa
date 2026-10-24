from django.db import migrations


def volver(apps, schema_editor):
    """«Carnes» vuelve a llamarse «Cárnicos refrigerados»: describe mejor la categoría (vacuno y cerdo en frío, separada de las aves).
    Renombra la misma fila, sin tocar productos. Si ya existe «Cárnicos refrigerados», no hace nada."""
    Categoria = apps.get_model("catalogo", "Categoria")
    if not Categoria.objects.filter(nombre="Cárnicos refrigerados").exists():
        Categoria.objects.filter(nombre="Carnes").update(nombre="Cárnicos refrigerados")


def deshacer(apps, schema_editor):
    apps.get_model("catalogo", "Categoria").objects.filter(nombre="Cárnicos refrigerados").update(nombre="Carnes")


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0003_categoria_carnes")]
    operations = [migrations.RunPython(volver, deshacer)]
