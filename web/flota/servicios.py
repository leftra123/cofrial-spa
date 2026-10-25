"""Estado de la flota para el panel y la API: última lectura de cada camión y su viaje activo."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from pedidos import servicios as pedidos_servicios
from pedidos.models import EstadoOrden, Orden

from . import rutas
from .models import Camion, Despacho, Telemetria
from .vigente import ultimas_vigentes


SITUACIONES = {"en_base": "en base", "en_ruta": "en ruta", "en_la_puerta": "en la puerta del cliente", "volviendo": "volviendo a la base"}


def situacion_de(viaje):
    """Dónde está un camión según su viaje: sin viaje queda guardado en la base; con viaje, la fase que informa el simulador."""
    return "en_base" if viaje is None else viaje.fase


def estado_flota():
    pedidos_servicios.confirmar_vencidas()
    camiones = list(Camion.objects.select_related("rango_temperatura").order_by("camion_id"))
    # DISTINCT ON de PostgreSQL: la última lectura de cada camión en una sola consulta.
    ultimas = ultimas_vigentes()
    viajes = {d.camion_id: d for d in Despacho.objects.filter(salida_en__isnull=False, regreso_en__isnull=True).order_by("salida_en")}
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
                         "situacion": situacion_de(d), "situacion_texto": SITUACIONES[situacion_de(d)],
                         "alerta": bool(t and t.alerta_ruptura_frio),
                         "combustible_bajo": bool(t and t.combustible_pct < 25)})
    resumen = {"total": len(camiones), "activos": sum(1 for c in camiones if c.activo),
               "en_ruta": sum(1 for x in tarjetas if x["situacion"] == "en_ruta"),
               "en_la_puerta": sum(1 for x in tarjetas if x["situacion"] == "en_la_puerta"),
               "volviendo": sum(1 for x in tarjetas if x["situacion"] == "volviendo"),
               "en_base": sum(1 for x in tarjetas if x["situacion"] == "en_base"),
               "con_viaje": len(viajes), "con_alerta": sum(1 for x in tarjetas if x["alerta"]),
               "sin_lectura": sum(1 for x in tarjetas if x["lectura"] is None)}
    return tarjetas, resumen


# ------------------------------------------------------------------------------------ armar despacho
ETAPA_DESPACHADA = 4          # orden_flujo de «Despachada» (Recibida, Confirmada, En preparación, Despachada, ...)


def pedidos_por_despachar():
    """Órdenes todavía sin camión y aún no despachadas, las más antiguas primero."""
    sin_camion = Q(despacho__isnull=True, estado_orden__es_final=False, estado_orden__orden_flujo__lt=ETAPA_DESPACHADA)
    return (Orden.objects.filter(sin_camion | Q(estado_orden__nombre="Entrega no concretada"))        # una entrega fallida se puede reprogramar
            .select_related("direccion__cliente", "direccion__comuna", "estado_orden")
            .prefetch_related("ordenitem_set__producto__categoria__rango_temperatura").order_by("creada_en"))


def rangos_de(orden):
    """Rangos de temperatura que exigen los productos de la orden (uno solo si es homogénea)."""
    return sorted({i.producto.categoria.rango_temperatura.nombre for i in orden.ordenitem_set.all()})


def camiones_libres():
    ocupados = Despacho.objects.filter(salida_en__isnull=False, regreso_en__isnull=True).values_list("camion_id", flat=True)
    return Camion.objects.filter(activo=True).exclude(camion_id__in=list(ocupados)).select_related("rango_temperatura").order_by("camion_id")


@transaction.atomic
def cerrar_despacho(despacho_id):
    """Corrección manual (administrador y despachador): da el viaje por llegado sin esperar al camión. Fija `llegada_en`, pasa a
    «Entregada» las órdenes que iban «Despachada» o con el camión en la puerta y manda al camión de vuelta a la base. El flujo normal
    no lo necesita: el simulador registra la llegada solo y el cliente confirma."""
    despacho = Despacho.objects.select_for_update().filter(pk=despacho_id, salida_en__isnull=False, llegada_en__isnull=True).first()
    if despacho is None:
        raise pedidos_servicios.ErrorDeNegocio("Ese viaje no existe o ya llegó.")
    despacho.llegada_en = timezone.now()
    despacho.fase = "volviendo"
    despacho.save(update_fields=["llegada_en", "fase"])
    entregadas = 0
    for o in Orden.objects.filter(despacho=despacho).select_related("estado_orden"):
        if o.estado_orden.nombre in ("Despachada", "Camión en la puerta"):
            pedidos_servicios.avanzar(o)
            entregadas += 1
    return despacho, entregadas


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
    ruta = rutas.armar_ruta([(o.direccion_id, o.direccion.lat, o.direccion.long) for o in ordenes])       # la misma ruta que vio el despachador
    despacho = Despacho.objects.create(camion=camion, programado_para=ahora, salida_en=ahora, ruta_geojson=ruta,
                                       ruta_aproximada=bool(ruta and ruta["aproximada"]))
    for o in ordenes:
        o.despacho = despacho
        if o.estado_orden.nombre == "Entrega no concretada":                 # reprogramada: vuelve a salir con otro viaje
            o.estado_orden = EstadoOrden.objects.get(nombre="Despachada")
            o.puerta_en = o.entrega_resuelta_en = None
            o.entrega_automatica = False
            o.save(update_fields=["despacho", "estado_orden", "puerta_en", "entrega_resuelta_en", "entrega_automatica"])
            continue
        o.save(update_fields=["despacho"])
        while o.estado_orden.orden_flujo < ETAPA_DESPACHADA:
            o = pedidos_servicios.avanzar(o)
    return despacho
