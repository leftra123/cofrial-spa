from django.db import migrations

NUEVO_FLUJO = [("Recibida", 1, False), ("Confirmada", 2, False), ("En preparación", 3, False), ("Despachada", 4, False),
               ("Camión en la puerta", 5, False), ("Entregada", 6, True), ("Entrega no concretada", 7, False), ("Cancelada", 8, True)]


def estados(apps, schema_editor):
    """Agrega «Camión en la puerta» y «Entrega no concretada» y renumera el flujo. En una base nueva no hay estados aún (los crea
    cargar_demo con este mismo orden); en una existente se renumera en dos pasos porque orden_flujo es único."""
    Estado = apps.get_model("pedidos", "EstadoOrden")
    if not Estado.objects.exists():
        return
    for e in Estado.objects.all():
        e.orden_flujo += 100
        e.save(update_fields=["orden_flujo"])
    for nombre, flujo, final in NUEVO_FLUJO:
        e = Estado.objects.filter(nombre=nombre).first()
        if e is None:
            Estado.objects.create(nombre=nombre, orden_flujo=flujo, es_final=final)
        else:
            e.orden_flujo, e.es_final = flujo, final
            e.save(update_fields=["orden_flujo", "es_final"])


class Migration(migrations.Migration):
    dependencies = [("pedidos", "0004_ciclo_entrega")]
    operations = [migrations.RunPython(estados, migrations.RunPython.noop)]
