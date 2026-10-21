"""Panel de flota (solo lectura): estado de cada camión según su última lectura de telemetría y su viaje activo."""
from django.shortcuts import render

from crm.views import con_rol
from pedidos.models import Orden

from .models import Camion, Despacho, Telemetria


@con_rol("admin", "gerencia", "despachador")
def panel(request):
    camiones = list(Camion.objects.select_related("rango_temperatura").order_by("camion_id"))
    # DISTINCT ON de PostgreSQL: la última lectura de cada camión en una sola consulta.
    ultimas = {t.camion_id: t for t in Telemetria.objects.order_by("camion_id", "-registrado_en").distinct("camion_id")}
    viajes = {}
    for d in Despacho.objects.filter(salida_en__isnull=False, llegada_en__isnull=True).order_by("salida_en"):
        viajes[d.camion_id] = d
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
    return render(request, "flota/panel.html", {"rol": request.rol, "tarjetas": tarjetas, "resumen": resumen,
                                                "viajes": [x for x in tarjetas if x["viaje"]]})
