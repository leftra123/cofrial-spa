"""Torre de control: una pantalla para gerencia y administración que junta el negocio, la flota y la rúbrica. Solo lee."""
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from crm.views import con_rol

from . import servicios

ROTULO = "Clientes ilustrativos: nombres públicos usados como ejemplo; ninguno es cliente confirmado de Cofrial"
VEN = ("admin", "gerencia")          # los vendedores verían clientes fuera de su cartera (RN-09)


@require_GET
@con_rol(*VEN)
def panel(request):
    return render(request, "torre/panel.html", {"rotulo": ROTULO})


@require_GET
@con_rol(*VEN)
def pulso(request):
    respuesta = JsonResponse(servicios.pulso(request.user, request.rol))
    respuesta["Cache-Control"] = "no-store"
    return respuesta
