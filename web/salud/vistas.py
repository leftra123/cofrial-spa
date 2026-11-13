from datetime import datetime

from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from . import servicios

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


ETIQUETAS = {"ok": "Operativo", "degradado": "Degradado", "caido": "Caído", "sin": "Sin registros"}


def _fecha(d):
    return f"{d.day} {MESES[d.month - 1]}"


def _porcentaje(x):
    if x is None:
        return None
    texto = f"{x * 100:.2f}".rstrip("0").rstrip(".") if x < 1 else "100"
    return texto.replace(".", ",") + " %"


def _cubo(cubo):
    """Rótulo de una barra: «13 nov» si es un día, «13 nov 14:00 h» si es una hora."""
    if isinstance(cubo, datetime):
        local = timezone.localtime(cubo)
        return f"{_fecha(local)} {local:%H}:00 h"
    return _fecha(cubo)


def pagina(request):
    """/salud/: el navegador (Accept: text/html) ve la página; el balanceador, curl y las pruebas siguen recibiendo {"estado": "ok"}."""
    if "text/html" not in request.headers.get("Accept", "") or request.GET.get("formato") == "json":
        return JsonResponse({"estado": "ok"})
    try:
        d = servicios.panel(ventana=request.GET.get("ventana", servicios.VENTANA_INICIAL))      # una clave desconocida cae en el período inicial
    except DatabaseError:                              # sin base no hay historial que leer; la página lo dice en vez de dar un 500
        return render(request, "salud/pagina.html", {"sin_base": True}, status=503)
    hora_local = timezone.localtime
    for g in d["grupos"]:
        for obj in [g, *g["componentes"]]:
            obj["porcentaje"] = _porcentaje(obj["disponibilidad"])
            obj["etiqueta"] = ETIQUETAS[obj["estado"]]
            for b in obj["barras"]:
                b["titulo"] = f"{_cubo(b['cubo'])}: " + (f"{b['revisiones']} revisiones, {b['caidas']} con caída" if b["revisiones"] else "sin registros")
            for b in obj["horas"]:
                b["titulo"] = f"{hora_local(b['cubo']):%H}:00 h: " + (f"{b['revisiones']} revisiones, {b['caidas']} con caída" if b["revisiones"] else "sin registros")
    for i in d["incidentes"]:
        i["desde"], i["hasta"] = hora_local(i["inicio"]), hora_local(i["fin"])
        i["etiqueta"] = ETIQUETAS[i["estado"]]
    d["ultima_local"] = hora_local(d["ultima_revision"]) if d["ultima_revision"] else None
    d["nivel"] = "caido" if any(c["estado"] == "caido" for _, c in d["problemas"]) else "degradado"
    d["primer_dia"] = _cubo(d["dias"][0])
    d["por_hora"] = d["unidad"] == "hora"
    d["ventanas"] = [{"clave": k, "rotulo": v[0], "activa": k == d["ventana"]} for k, v in servicios.VENTANAS.items()]
    d["ahora_local"] = hora_local(d["ahora"])
    return render(request, "salud/pagina.html", d)
