"""Panel de flota (solo lectura): estado de cada camión según su última lectura de telemetría y su viaje activo."""
from django.conf import settings
from django.http import JsonResponse
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from clientes import geo
from cofrial import entradas
from clientes.models import Direccion
from pedidos.servicios import ErrorDeNegocio

from crm.views import con_rol

from . import autodespacho, rutas, servicios, sugerencias, tiempo
from .servicios import estado_flota

DESPACHAN = ("admin", "despachador")          # gerencia ve la flota y la pantalla de despacho, pero no arma viajes ni toca direcciones


def _solo_lectura(request):
    return render(request, "403.html", {"detalle": "Gerencia consulta los despachos; los arman el despachador y el administrador."}, status=403)


def _ruta_para_mapa(viaje):
    """La ruta guardada del viaje (se calcula una vez si es de antes de guardarlas) con los minutos que tomaría a la velocidad media."""
    ruta = rutas.asegurar_ruta(viaje)
    if not ruta:
        return None
    return {**ruta, "minutos": round(tiempo.minutos_de_viaje(ruta["km"]))}


@con_rol("admin", "gerencia", "despachador")
def ruta_sugerida(request):
    """Vista previa al armar un despacho: la misma ruta por calles que quedará guardada al despachar (sale de la caché del servidor)."""
    ids = [entradas.entero(i) for i in request.GET.get("ordenes", "").split(",") if entradas.es_entero(i)]     # «²» pasa isdigit() y rompe int()
    ordenes = list(servicios.pedidos_por_despachar().filter(pk__in=ids))
    ruta = rutas.armar_ruta([(o.direccion_id, o.direccion.lat, o.direccion.long) for o in ordenes])
    if ruta is None:
        return JsonResponse({"ruta": None})
    por_direccion = {}
    for o in ordenes:
        por_direccion.setdefault(o.direccion_id, []).append(o.orden_id)
    for p in ruta["paradas"]:
        p["ordenes"] = por_direccion.get(p["direccion_id"], [])
    return JsonResponse({"ruta": {**ruta, "minutos": round(tiempo.minutos_de_viaje(ruta["km"]))}})


@con_rol("admin", "gerencia", "despachador")
def panel(request):
    tarjetas, resumen = estado_flota()
    viajes = [x for x in tarjetas if x["viaje"]]
    # Datos del mapa: la base, los camiones en operación, los guardados en la base (se muestran a pedido) y las paradas ubicadas de cada viaje.
    mapa = {"base": settings.BASE_LOGISTICA,
            "camiones": [{"id": x["camion"].camion_id, "patente": x["camion"].patente, "lat": x["lectura"].lat, "long": x["lectura"].long,
                          "alerta": x["alerta"]} for x in tarjetas if x["lectura"] and x["en_operacion"]],
            "en_base": [{"id": x["camion"].camion_id, "patente": x["camion"].patente} for x in tarjetas if not x["en_operacion"]],
            "viajes": [{"camion": x["camion"].camion_id, "patente": x["camion"].patente, "despacho": x["viaje"].despacho_id,
                        "situacion": x["situacion_texto"], "ruta": _ruta_para_mapa(x["viaje"]),
                        "paradas": [{"orden": o.orden_id, "direccion_id": o.direccion_id, "cliente": o.direccion.cliente.nombre,
                                     "direccion": str(o.direccion), "estado": o.estado_orden.nombre,
                                     "lat": o.direccion.lat, "long": o.direccion.long}
                                    for o in x["pedidos"] if o.direccion.lat is not None]} for x in viajes]}
    return render(request, "flota/panel.html", {"rol": request.rol, "tarjetas": tarjetas, "resumen": resumen,
                                                "viajes": viajes, "mapa": mapa, "puede_cerrar": request.rol in DESPACHAN,
                                                "auto": autodespacho.estado()})


@require_POST
@con_rol("admin", "despachador")
def cerrar_despacho(request, despacho_id):
    """Marcar entregado / cerrar despacho: solo administrador y despachador, y con confirmación explícita."""
    if request.POST.get("confirmar") != "1":
        messages.error(request, "Hay que confirmar para cerrar el despacho.")
        return redirect("flota")
    try:
        d, n = servicios.cerrar_despacho(despacho_id)
        messages.success(request, f"Despacho N.º {d.despacho_id} dado por llegado: {d.camion_id} vuelve a la base y {n} pedido{'s' if n != 1 else ''} pasó a «Entregada».")
    except ErrorDeNegocio as e:
        for m in e.mensajes:
            messages.error(request, m)
    return redirect("flota")


@con_rol("admin", "gerencia", "despachador")
def sugerencias_despacho(request):
    """JSON para el panel: viajes sugeridos y un aviso redactado por la IA (o el texto base). Solo propone; no despacha."""
    viajes, resto = sugerencias.calcular()
    texto, por_ia = sugerencias.redactar(viajes, resto)
    return JsonResponse({"texto": texto, "por_ia": por_ia, "viajes": sugerencias.con_enlaces(viajes), **resto},
                        json_dumps_params={"ensure_ascii": False})


@require_GET
@con_rol("admin", "gerencia", "despachador")
def por_despachar(request):
    """Contador junto a «Flota». Sin `detalle` es un solo COUNT, sin sugerencias ni IA. El menú recibe ese número con la consulta común de
    `/api/avisos-equipo/`; con `detalle=1` (al abrir el contador) agrega el aviso y a dónde ir, con el texto del código: abrirlo no gasta la cuota gratuita."""
    datos = {"total": servicios.pedidos_por_despachar().count()}
    if request.GET.get("detalle") == "1":
        viajes, resto = sugerencias.calcular()
        datos.update(texto=sugerencias.texto_base(viajes, resto), acciones=sugerencias.acciones_del_menu(viajes, request.rol in DESPACHAN))
    return JsonResponse(datos, json_dumps_params={"ensure_ascii": False})


@con_rol("admin", "gerencia", "despachador")
def despacho_auto(request):
    """El recuadro del despacho automático; el panel lo vuelve a pedir mientras el modo está encendido."""
    return render(request, "flota/_despacho_auto.html", {"auto": autodespacho.estado(), "puede_cerrar": request.rol in DESPACHAN})


@require_POST
@con_rol("admin", "despachador")
def correr_despacho_auto(request):
    """Una pasada pedida por una persona, con las mismas reglas: muestra el modo automático sin reiniciar servicios y sin esperar la agrupación."""
    if request.POST.get("confirmar") != "1":
        messages.error(request, "Hay que confirmar para correr el despacho automático.")
        return redirect("flota")
    r = autodespacho.ejecutar(forzar=True, max_viajes=autodespacho.MAX_VIAJES_A_MANO)
    n = len(r["despachos"])
    if n:
        messages.success(request, f"El despacho automático sacó {n} viaje{'s' if n != 1 else ''}. El motivo está en el recuadro.")
    elif not r["omitidos"]:
        messages.info(request, "El despacho automático no encontró ningún viaje que pueda salir ahora.")
    for o in r["omitidos"]:
        messages.warning(request, f"No salió el viaje con {o['camion']}: {' '.join(o['mensajes'])}")
    return redirect("flota")


@con_rol("admin", "gerencia", "despachador")
def despachar(request):
    """Armar un viaje: elegir camión y pedidos; la ruta sugerida se previsualiza en el mapa antes de salir."""
    if request.method == "POST":
        if request.rol not in DESPACHAN:
            return _solo_lectura(request)
        try:
            d = servicios.despachar(request.POST.get("camion", ""), [entradas.entero(i) for i in request.POST.getlist("ordenes") if entradas.es_entero(i)])
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
    opciones = sugerencias.opciones_camion()         # del mejor al peor: el navegador toma el primero compatible con lo que se marque
    camion_sugerido = request.GET.get("camion", "")
    mapa = {"base": settings.BASE_LOGISTICA, "camion_fijado": bool(camion_sugerido),
            "camiones": [{k: c[k] for k in ("id", "rango", "rangos", "apto", "nota")} for c in opciones],
            "rangos": {p["o"].orden_id: p["rangos"] for p in pedidos},
            "pedidos": {p["o"].orden_id: {"lat": p["o"].direccion.lat, "long": p["o"].direccion.long, "cliente": p["o"].direccion.cliente.nombre,
                                          "direccion": str(p["o"].direccion)} for p in pedidos if p["ubicada"]}}
    marcados = {entradas.entero(i) for i in request.GET.get("ordenes", "").split(",") if entradas.es_entero(i)}      # preselección que llega desde la sugerencia
    return render(request, "flota/despacho.html", {"pedidos": pedidos, "camiones": servicios.camiones_libres(), "mapa": mapa,
                                                   "camion_sugerido": camion_sugerido, "marcados": marcados,
                                                   "camiones_en_alerta": {c["id"] for c in opciones if c["alerta"]},
                                                   "puede_despachar": request.rol in DESPACHAN})


@require_POST
@con_rol("admin", "gerencia", "despachador")
def ubicar_direccion(request, direccion_id):
    """Reintenta ubicar una dirección en el mapa (OpenStreetMap) cuando el registro no la encontró."""
    if request.rol not in DESPACHAN:
        return _solo_lectura(request)
    direccion = get_object_or_404(Direccion.objects.select_related("comuna"), pk=direccion_id)
    if geo.ubicar(direccion):
        messages.success(request, f"Ubicamos «{direccion}» en el mapa.")
    else:
        messages.warning(request, f"No encontramos «{direccion}» en OpenStreetMap. Revisa que la calle y el número estén bien escritos.")
    return redirect("despachar")
