"""Estado de la flota para el panel y la API: última lectura de cada camión y su viaje activo."""
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from pedidos import servicios as pedidos_servicios
from pedidos.models import EstadoOrden, Orden

from . import rutas
from .models import Camion, Despacho, Telemetria
from .vigente import ultimas_vigentes


SITUACIONES = {"en_base": "en base", "en_ruta": "en ruta", "en_la_puerta": "en la puerta del cliente", "volviendo": "volviendo a la base"}
COMBUSTIBLE_BAJO = 25         # bajo este porcentaje el panel lo marca y el despacho automático no lo usa
SENAL_VIGENTE_SEG = 120       # el simulador reporta cada 5 s: más de esto sin lecturas es que el camión no se está viendo


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

    tarjetas, ahora = [], timezone.now()
    for c in camiones:
        t = ultimas.get(c.camion_id)
        d = viajes.get(c.camion_id)
        pedidos = _pedidos_en_orden(ordenes.get(d.despacho_id, []) if d else [], d)
        tarjetas.append({"camion": c, "lectura": t, "viaje": d, "pedidos": pedidos,
                         "destino": _proxima_direccion(pedidos),
                         "situacion": situacion_de(d), "situacion_texto": SITUACIONES[situacion_de(d)],
                         "alerta": bool(t and t.alerta_ruptura_frio),
                         "combustible_bajo": bool(t and t.combustible_pct < COMBUSTIBLE_BAJO),
                         "sin_senal": bool(t and (ahora - t.registrado_en).total_seconds() > SENAL_VIGENTE_SEG)})
        tarjetas[-1]["en_operacion"] = tarjetas[-1]["situacion"] != "en_base" or tarjetas[-1]["alerta"]     # lo que el panel muestra por defecto
    resumen = {"total": len(camiones), "activos": sum(1 for c in camiones if c.activo),
               "en_ruta": sum(1 for x in tarjetas if x["situacion"] == "en_ruta"),
               "en_la_puerta": sum(1 for x in tarjetas if x["situacion"] == "en_la_puerta"),
               "volviendo": sum(1 for x in tarjetas if x["situacion"] == "volviendo"),
               "en_base": sum(1 for x in tarjetas if x["situacion"] == "en_base"),
               "guardados": sum(1 for x in tarjetas if not x["en_operacion"]),
               "con_viaje": len(viajes), "con_alerta": sum(1 for x in tarjetas if x["alerta"]),
               "sin_lectura": sum(1 for x in tarjetas if x["lectura"] is None),
               "sin_senal": sum(1 for x in tarjetas if x["sin_senal"])}
    return tarjetas, resumen


_YA_VISITADAS = {"Entregada", "Cancelada", "Entrega no concretada", "Rechazada en recepción"}


def _pedidos_en_orden(pedidos, viaje):
    """El mismo orden de `ruta_geojson.paradas` que ve el cliente. Cada pedido queda con `parada_n` (1 es la primera salida)."""
    indice = {p["direccion_id"]: i for i, p in enumerate(((viaje.ruta_geojson or {}) if viaje else {}).get("paradas") or [])}
    ordenados = sorted(pedidos, key=lambda o: (indice.get(o.direccion_id, 10_000), o.orden_id))
    for o in ordenados:
        o.parada_n = indice.get(o.direccion_id, len(indice)) + 1
    return ordenados


def _proxima_direccion(pedidos):
    """La próxima parada del recorrido, no la primera orden que haya devuelto la consulta."""
    for o in pedidos:
        if o.estado_orden.nombre not in _YA_VISITADAS:
            return o.direccion
    return pedidos[0].direccion if pedidos else None


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
def despachar(camion_id, orden_ids, decision=None):
    """Crea el despacho con salida ahora, le asigna las órdenes y las lleva hasta «Despachada».

    Reglas: el camión debe estar libre y activo, cada orden debe estar ubicada en el mapa (sin parada, el camión no llega nunca y la
    orden queda «Despachada» para siempre) y la cadena de frío no se mezcla (cada orden exige un solo rango de temperatura y debe ser
    el del camión). `decision` es el porqué del despacho automático; una persona no lo llena. Devuelve el despacho.

    Bloquea el camión y las órdenes hasta terminar: el despacho automático y una persona pueden pedir lo mismo a la vez, y el segundo
    debe recibir el error de siempre y no un camión con dos viajes. El camión se bloquea antes de mirar si está ocupado."""
    ErrorDeNegocio = pedidos_servicios.ErrorDeNegocio
    if not orden_ids:
        raise ErrorDeNegocio("Marca al menos un pedido para despachar.")
    camion = Camion.objects.select_for_update(of=("self",)).select_related("rango_temperatura").filter(camion_id=camion_id, activo=True).first()
    if camion is None or Despacho.objects.filter(camion=camion, salida_en__isnull=False, regreso_en__isnull=True).exists():
        raise ErrorDeNegocio("Ese camión no está disponible (inactivo o con un viaje en curso).")
    ordenes = list(pedidos_por_despachar().select_for_update(of=("self",)).filter(pk__in=orden_ids))
    if len(ordenes) != len(set(orden_ids)):
        raise ErrorDeNegocio("Algún pedido ya no está disponible para despachar; actualiza la pantalla.")
    problemas = []
    for o in ordenes:
        rangos = rangos_de(o)
        if o.direccion.lat is None or o.direccion.long is None:
            problemas.append(f"La orden N.º {o.orden_id} no está ubicada en el mapa: ubícala antes de despacharla.")
        if len(rangos) > 1:
            problemas.append(f"La orden N.º {o.orden_id} mezcla {' y '.join(r.lower() for r in rangos)}: no puede viajar en un solo camión.")
        elif rangos and rangos[0] != camion.rango_temperatura.nombre:
            problemas.append(f"La orden N.º {o.orden_id} es de productos {rangos[0].lower()}s y {camion.camion_id} es {camion.rango_temperatura.nombre.lower()}.")
    if problemas:
        raise ErrorDeNegocio(*problemas)
    ahora = timezone.now()
    ruta = rutas.armar_ruta([(o.direccion_id, o.direccion.lat, o.direccion.long) for o in ordenes])       # la misma ruta que vio el despachador
    despacho = Despacho.objects.create(camion=camion, programado_para=ahora, salida_en=ahora, ruta_geojson=ruta,
                                       ruta_aproximada=bool(ruta and ruta["aproximada"]), decision_auto=decision)
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


def lecturas_prescindibles(corte):
    """Lecturas normales anteriores al corte. Se conservan las alertas (RN-13 y el tablero), las forzadas de la demostración,
    las tomadas durante un viaje (se cruzan con los reclamos) y la última de cada camión (la usa la flota)."""
    durante_un_viaje = Despacho.objects.filter(camion_id=OuterRef("camion_id"), salida_en__lte=OuterRef("registrado_en")).filter(
        Q(llegada_en__isnull=True) | Q(llegada_en__gte=OuterRef("registrado_en")))
    ultimas = Telemetria.objects.order_by("camion_id", "-registrado_en").distinct("camion_id").values_list("pk", flat=True)
    return (Telemetria.objects.filter(registrado_en__lt=corte, alerta_ruptura_frio=False, forzada=False)
            .exclude(pk__in=list(ultimas)).filter(~Exists(durante_un_viaje)))
