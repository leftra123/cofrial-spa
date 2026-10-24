"""Modo demostración: forzar una ruptura de frío en un camión para mostrarla en vivo (campanita, alertas del CRM y Grafana).

Solo para administradores. No corre solo: exige confirmación, dura como máximo DURACION_MAX_S, y sus lecturas quedan marcadas
(`forzada`) para poder apagarlas y borrarlas sin tocar la telemetría real del simulador."""
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from crm.views import con_rol

from .models import Camion, Telemetria

DURACION_MAX_S = 180     # tope de una ruptura forzada
SEPARACION_S = 20        # si pasan más segundos sin pulsos, la siguiente ruptura cuenta como una nueva (y pide confirmación)


def _camion(request):
    return Camion.objects.filter(pk=request.POST.get("camion", ""), activo=True).select_related("rango_temperatura").first()


def _ultima_real(camion):
    return Telemetria.objects.filter(camion=camion).order_by("-registrado_en").first()


def _estado(request, camion):
    t = request.session.get("demo_" + camion.camion_id)
    ahora = timezone.now().timestamp()
    activa = bool(t) and ahora - t["ultimo"] <= SEPARACION_S and ahora - t["inicio"] <= DURACION_MAX_S
    return {"activa": activa, "restante_s": max(0, int(DURACION_MAX_S - (ahora - t["inicio"]))) if activa else 0,
            "forzadas": Telemetria.objects.filter(forzada=True).count()}


@con_rol("admin")
def pagina(request):
    camiones = Camion.objects.filter(activo=True).select_related("rango_temperatura").order_by("camion_id")
    return render(request, "flota/demo.html", {"rol": request.rol, "camiones": camiones, "duracion": DURACION_MAX_S,
                                               "forzadas": Telemetria.objects.filter(forzada=True).count()})


def _insertar(camion, temp, alerta):
    ref = _ultima_real(camion)
    base = settings.BASE_LOGISTICA
    return Telemetria.objects.create(
        camion=camion, temp_camara=round(temp, 1), alerta_ruptura_frio=alerta, forzada=True,
        lat=ref.lat if ref else base["lat"], long=ref.long if ref else base["long"], combustible_pct=ref.combustible_pct if ref else 70)


@require_POST
@con_rol("admin")
def pulso(request):
    """Inserta una lectura con la temperatura fuera de rango. El navegador lo llama cada pocos segundos mientras la ruptura está activa."""
    camion = _camion(request)
    if camion is None:
        return JsonResponse({"detail": "Camión no válido."}, status=400)
    clave, ahora = "demo_" + camion.camion_id, timezone.now().timestamp()
    t = request.session.get(clave)
    nueva = not t or ahora - t["ultimo"] > SEPARACION_S or ahora - t["inicio"] > DURACION_MAX_S
    if nueva:
        if request.POST.get("confirmar") != "1":
            return JsonResponse({"detail": "Hay que confirmar para iniciar una ruptura forzada."}, status=400)
        t = {"inicio": ahora, "ultimo": ahora}
    elif ahora - t["inicio"] > DURACION_MAX_S:
        return JsonResponse({**_estado(request, camion), "detail": "Se alcanzó el tiempo máximo."})
    t["ultimo"] = ahora
    request.session[clave] = t
    transcurrido = ahora - t["inicio"]
    tmax = float(camion.rango_temperatura.temp_max_c)
    lectura = _insertar(camion, tmax + 3 + min(5.0, transcurrido / 20), True)
    return JsonResponse({**_estado(request, camion), "temp": lectura.temp_camara})


@require_POST
@con_rol("admin")
def apagar(request):
    """Termina la ruptura: deja una lectura normal (para que, sin simulador, el camión vuelva a verse dentro del rango)."""
    camion = _camion(request)
    if camion is None:
        return JsonResponse({"detail": "Camión no válido."}, status=400)
    request.session.pop("demo_" + camion.camion_id, None)
    r = camion.rango_temperatura
    lectura = _insertar(camion, (float(r.temp_min_c) + float(r.temp_max_c)) / 2, False)
    return JsonResponse({**_estado(request, camion), "temp": lectura.temp_camara})


@require_POST
@con_rol("admin")
def limpiar(request):
    """Borra solo las lecturas forzadas; la telemetría real queda intacta."""
    if request.POST.get("confirmar") != "1":
        return JsonResponse({"detail": "Hay que confirmar para borrar."}, status=400)
    n, _ = Telemetria.objects.filter(forzada=True).delete()
    for k in [k for k in request.session.keys() if k.startswith("demo_")]:
        request.session.pop(k)
    return JsonResponse({"borradas": n, "forzadas": 0})
