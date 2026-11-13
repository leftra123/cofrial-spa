"""Torre de control: una pantalla para gerencia y administración que junta el negocio, la flota y la rúbrica. Solo lee."""
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from crm.views import con_rol

from . import antes, servicios

ROTULO = "Clientes ilustrativos: nombres públicos usados como ejemplo; ninguno es cliente confirmado de Cofrial"
VEN = ("admin",)          # solo el equipo de consultoría: gerencia no la ve, ni la rúbrica que lleva dentro


@require_GET
@con_rol(*VEN)
def panel(request):
    inicial = {**servicios.pulso(request.user, request.rol), "base": settings.BASE_LOGISTICA,
               "antes": {"registro": antes.REGISTRO, "supuestos": antes.SUPUESTOS}}
    return render(request, "torre/panel.html", {"rotulo": ROTULO, "inicial": inicial})


@require_GET
@con_rol(*VEN)
def pulso(request):
    respuesta = JsonResponse(servicios.pulso(request.user, request.rol))
    respuesta["Cache-Control"] = "no-store"
    return respuesta
