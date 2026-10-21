"""Panel de flota (solo lectura): estado de cada camión según su última lectura de telemetría y su viaje activo."""
from django.shortcuts import render

from crm.views import con_rol

from .servicios import estado_flota


@con_rol("admin", "gerencia", "despachador")
def panel(request):
    tarjetas, resumen = estado_flota()
    return render(request, "flota/panel.html", {"rol": request.rol, "tarjetas": tarjetas, "resumen": resumen,
                                                "viajes": [x for x in tarjetas if x["viaje"]]})
