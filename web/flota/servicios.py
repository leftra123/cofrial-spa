"""Estado de la flota para el panel y la API: última lectura de cada camión y su viaje activo."""
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
