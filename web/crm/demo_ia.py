"""El requerimiento que se clasifica en vivo en la defensa (rúbrica D5). Un solo lugar para su texto: lo siembra cargar_demo y lo
restablece el comando restablecer_demo_ia, de modo que ambos dejan exactamente lo mismo."""
from clientes.muestra import SUPERMERCADOS_DEL_SUR       # RUT del cliente que lo envía
from crm.models import Requerimiento

ASUNTO = "Mi pedido llegó tibio"
DESCRIPCION = "El camión llegó con la carga sin la temperatura adecuada y rechazamos dos cajas. Necesitamos reposición urgente."

# Lo que la clasificación (o una persona) escribe y la siembra deja vacío o en su valor inicial.
_INICIAL = {"categoria_requerimiento": None, "categoria_ia": None, "confianza_ia": None, "desglose": None,
            "clasificado_manual": False, "estado": "sin_clasificar", "respondido_en": None}


def restablecer(cliente):
    """Deja el requerimiento de la demo del cliente como lo siembra cargar_demo. Idempotente.
    Devuelve (resultado, otros): «creado», «restablecido» o «sin cambios», y cuántos más hay con el mismo asunto (no se tocan).
    Con duplicados restablece el más antiguo."""
    propios = list(Requerimiento.objects.filter(cliente=cliente, asunto=ASUNTO).order_by("pk"))
    if not propios:
        Requerimiento.objects.create(cliente=cliente, asunto=ASUNTO, descripcion=DESCRIPCION)
        return "creado", 0
    r = propios[0]
    esperado = {"descripcion": DESCRIPCION, **_INICIAL}
    cambios = {campo: valor for campo, valor in esperado.items() if getattr(r, campo) != valor}
    if cambios:
        Requerimiento.objects.filter(pk=r.pk).update(**cambios)
        return "restablecido", len(propios) - 1
    return "sin cambios", len(propios) - 1
