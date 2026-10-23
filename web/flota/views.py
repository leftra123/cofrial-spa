"""Panel de flota (solo lectura): estado de cada camión según su última lectura de telemetría y su viaje activo."""
from django.conf import settings
from django.shortcuts import render

from crm.views import con_rol

from .servicios import estado_flota


@con_rol("admin", "gerencia", "despachador")
def panel(request):
    tarjetas, resumen = estado_flota()
    viajes = [x for x in tarjetas if x["viaje"]]
    # Datos del mapa: la base, la posición de cada camión y las paradas ubicadas de cada viaje (la ruta sugerida se calcula en el navegador).
    mapa = {"base": settings.BASE_LOGISTICA,
            "camiones": [{"id": x["camion"].camion_id, "patente": x["camion"].patente, "lat": x["lectura"].lat, "long": x["lectura"].long,
                          "alerta": x["alerta"]} for x in tarjetas if x["lectura"]],
            "viajes": [{"camion": x["camion"].camion_id, "patente": x["camion"].patente, "despacho": x["viaje"].despacho_id,
                        "paradas": [{"orden": o.orden_id, "cliente": o.direccion.cliente.nombre, "direccion": str(o.direccion),
                                     "lat": o.direccion.lat, "long": o.direccion.long}
                                    for o in x["pedidos"] if o.direccion.lat is not None]} for x in viajes]}
    return render(request, "flota/panel.html", {"rol": request.rol, "tarjetas": tarjetas, "resumen": resumen,
                                                "viajes": viajes, "mapa": mapa})
