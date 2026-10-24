"""Estado de la flota para el panel y la API: última lectura de cada camión y su viaje activo."""
from django.db import transaction
from django.utils import timezone

from pedidos import servicios as pedidos_servicios
from pedidos.models import Orden

from .models import Camion, Despacho, Telemetria


def estado_flota():
    camiones = list(Camion.objects.select_related("rango_temperatura").order_by("camion_id"))
    # DISTINCT ON de PostgreSQL: la última lectura de cada camión en una sola consulta.
    ultimas = {t.camion_id: t for t in Telemetria.objects.order_by("camion_id", "-registrado_en").distinct("camion_id")}
    viajes = {d.camion_id: d for d in Despacho.objects.filter(salida_en__isnull=False, llegada_en__isnull=True).order_by("salida_en")}
    ordenes = {}
    for o in (Orden.objects.filter(despacho__in=viajes.values())
              .select_related("direccion__cliente", "direccion__comuna", "estado_orden")):
        ordenes.setdefault(o.despacho_id, []).append(o)

    tarjetas = []
    for c in camiones:
        t = ultimas.get(c.camion_id)
        d = viajes.get(c.camion_id)
        pedidos = ordenes.get(d.despacho_id, []) if d else []
        tarjetas.append({"camion": c, "lectura": t, "viaje": d, "pedidos": pedidos,
                         "destino": pedidos[0].direccion if pedidos else None,
                         "alerta": bool(t and t.alerta_ruptura_frio),
                         "combustible_bajo": bool(t and t.combustible_pct < 25)})
    resumen = {"total": len(camiones), "activos": sum(1 for c in camiones if c.activo),
               "en_ruta": len(viajes), "con_alerta": sum(1 for x in tarjetas if x["alerta"]),
               "sin_lectura": sum(1 for x in tarjetas if x["lectura"] is None)}
    return tarjetas, resumen


# ------------------------------------------------------------------------------------ armar despacho
ETAPA_DESPACHADA = 4          # orden_flujo de «Despachada» (Recibida, Confirmada, En preparación, Despachada, ...)


def pedidos_por_despachar():
    """Órdenes todavía sin camión y aún no despachadas, las más antiguas primero."""
    return (Orden.objects.filter(despacho__isnull=True, estado_orden__es_final=False, estado_orden__orden_flujo__lt=ETAPA_DESPACHADA)
            .select_related("direccion__cliente", "direccion__comuna", "estado_orden")
            .prefetch_related("ordenitem_set__producto__categoria__rango_temperatura").order_by("creada_en"))


def rangos_de(orden):
    """Rangos de temperatura que exigen los productos de la orden (uno solo si es homogénea)."""
    return sorted({i.producto.categoria.rango_temperatura.nombre for i in orden.ordenitem_set.all()})


def camiones_libres():
    ocupados = Despacho.objects.filter(salida_en__isnull=False, llegada_en__isnull=True).values_list("camion_id", flat=True)
    return Camion.objects.filter(activo=True).exclude(camion_id__in=list(ocupados)).select_related("rango_temperatura").order_by("camion_id")


@transaction.atomic
def despachar(camion_id, orden_ids):
    """Crea el despacho con salida ahora, le asigna las órdenes y las lleva hasta «Despachada».

    Reglas: el camión debe estar libre y activo, y la cadena de frío no se mezcla (cada orden exige un solo rango de temperatura
    y debe ser el del camión). Devuelve el despacho."""
    ErrorDeNegocio = pedidos_servicios.ErrorDeNegocio
    if not orden_ids:
        raise ErrorDeNegocio("Marca al menos un pedido para despachar.")
    camion = camiones_libres().filter(camion_id=camion_id).first()
    if camion is None:
        raise ErrorDeNegocio("Ese camión no está disponible (inactivo o con un viaje en curso).")
    ordenes = list(pedidos_por_despachar().filter(pk__in=orden_ids))
    if len(ordenes) != len(set(orden_ids)):
        raise ErrorDeNegocio("Algún pedido ya no está disponible para despachar; actualiza la pantalla.")
    problemas = []
    for o in ordenes:
        rangos = rangos_de(o)
        if len(rangos) > 1:
            problemas.append(f"La orden N.º {o.orden_id} mezcla {' y '.join(r.lower() for r in rangos)}: no puede viajar en un solo camión.")
        elif rangos and rangos[0] != camion.rango_temperatura.nombre:
            problemas.append(f"La orden N.º {o.orden_id} es de productos {rangos[0].lower()}s y {camion.camion_id} es {camion.rango_temperatura.nombre.lower()}.")
    if problemas:
        raise ErrorDeNegocio(*problemas)
    ahora = timezone.now()
    despacho = Despacho.objects.create(camion=camion, programado_para=ahora, salida_en=ahora)
    for o in ordenes:
        o.despacho = despacho
        o.save(update_fields=["despacho"])
        while o.estado_orden.orden_flujo < ETAPA_DESPACHADA:
            o = pedidos_servicios.avanzar(o)
    return despacho
