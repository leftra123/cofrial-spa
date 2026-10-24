"""Panel de flota (solo lectura): estado de cada camión según su última lectura de telemetría y su viaje activo."""
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clientes import geo
from clientes.models import Direccion
from pedidos.servicios import ErrorDeNegocio

from crm.views import con_rol

from . import servicios, sugerencias
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


@con_rol("admin", "gerencia", "despachador")
def sugerencias_despacho(request):
    """JSON para el panel: viajes sugeridos y un aviso redactado por la IA (o el texto base). Solo propone; no despacha."""
    viajes, resto = sugerencias.calcular()
    texto, por_ia = sugerencias.redactar(viajes, resto)
    return JsonResponse({"texto": texto, "por_ia": por_ia, "viajes": sugerencias.con_enlaces(viajes), **resto},
                        json_dumps_params={"ensure_ascii": False})


@con_rol("admin", "gerencia", "despachador")
def despachar(request):
    """Armar un viaje: elegir camión y pedidos; la ruta sugerida se previsualiza en el mapa antes de salir."""
    if request.method == "POST":
        try:
            d = servicios.despachar(request.POST.get("camion", ""), [int(i) for i in request.POST.getlist("ordenes") if i.isdigit()])
            messages.success(request, f"Despacho N.º {d.despacho_id} en ruta con {d.camion_id}. Ya puedes ver la ruta sugerida.")
            return redirect("flota")
        except ErrorDeNegocio as e:
            for m in e.mensajes:
                messages.error(request, m)
        return redirect("despachar")
    pedidos = []
    for o in servicios.pedidos_por_despachar():
        rangos = servicios.rangos_de(o)
        pedidos.append({"o": o, "rangos": rangos, "mixto": len(rangos) > 1, "ubicada": o.direccion.lat is not None})
    mapa = {"base": settings.BASE_LOGISTICA,
            "pedidos": {p["o"].orden_id: {"lat": p["o"].direccion.lat, "long": p["o"].direccion.long, "cliente": p["o"].direccion.cliente.nombre,
                                          "direccion": str(p["o"].direccion)} for p in pedidos if p["ubicada"]}}
    marcados = {int(i) for i in request.GET.get("ordenes", "").split(",") if i.isdigit()}      # preselección que llega desde la sugerencia
    return render(request, "flota/despacho.html", {"pedidos": pedidos, "camiones": servicios.camiones_libres(), "mapa": mapa,
                                                   "camion_sugerido": request.GET.get("camion", ""), "marcados": marcados})


@require_POST
@con_rol("admin", "gerencia", "despachador")
def ubicar_direccion(request, direccion_id):
    """Reintenta ubicar una dirección en el mapa (OpenStreetMap) cuando el registro no la encontró."""
    direccion = get_object_or_404(Direccion.objects.select_related("comuna"), pk=direccion_id)
    if geo.ubicar(direccion):
        messages.success(request, f"Ubicamos «{direccion}» en el mapa.")
    else:
        messages.warning(request, f"No encontramos «{direccion}» en OpenStreetMap. Revisa que la calle y el número estén bien escritos.")
    return redirect("despachar")
