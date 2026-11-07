"""Sugerencia de despachos: qué pedidos esperan y qué camión libre conviene usar.

Los hechos (qué pedidos, qué camión, cuánto llevan esperando) los calcula el código con las mismas reglas de `despachar`:
un solo rango de frío por viaje, camión libre y activo, pedidos ubicados en el mapa. La IA solo redacta el aviso a partir de
esos hechos; si falla, no hay clave o inventa un camión, se usa el texto base. Este módulo nunca despacha: el botón lleva al
formulario de «Armar despacho» ya marcado y alguien confirma. El modo automático (`autodespacho.py`) parte del mismo cálculo.
Privacidad: a la IA solo le llegan números de orden, comuna, rango de frío y minutos de espera; ni nombres ni direcciones.
"""
import hashlib
import json
import re

from django.core.cache import cache
from django.utils import timezone

from crm import ia

from . import servicios
from .vigente import ultimas_vigentes

MAX_PARADAS = 6           # pedidos por viaje sugerido
CACHE_SEG = 300           # la misma situación no vuelve a consultar a la IA durante 5 minutos


def _nota(c, t, alerta, reciente):
    """Por qué un camión queda donde queda en la lista; es el texto que ve la persona."""
    if t is None:
        return f"{c.camion_id} no tiene lecturas de telemetría."
    temp = f"{t.temp_camara:.1f}".replace(".", ",")
    if alerta:
        return f"{c.camion_id} tiene ruptura de frío: la cámara marca {temp} °C."
    texto = f"{c.camion_id}: {t.combustible_pct} % de combustible, cámara a {temp} °C, sin alerta de frío."
    return texto if reciente else f"{texto[:-1]}, pero su última lectura no es reciente."


def opciones_camion():
    """Camiones libres del mejor al peor. El mejor tiene más combustible y lecturas al día; el código del camión desempata.
    `apto` es lo mínimo para proponerlo a una persona (sin ruptura de frío). `apto_auto` agrega lo que una persona ve y el
    modo automático no puede suponer: telemetría reciente y combustible suficiente."""
    ultimas, ahora, filas = ultimas_vigentes(), timezone.now(), []
    for c in servicios.camiones_libres():
        t = ultimas.get(c.camion_id)
        alerta = bool(t and t.alerta_ruptura_frio)
        bajo = bool(t and t.combustible_pct < servicios.COMBUSTIBLE_BAJO)
        reciente = bool(t and (ahora - t.registrado_en).total_seconds() <= servicios.SENAL_VIGENTE_SEG)
        filas.append({"id": c.camion_id, "patente": c.patente, "rango": c.rango_temperatura.nombre,
                      "combustible": t.combustible_pct if t else None, "alerta": alerta, "apto": not alerta,
                      "apto_auto": reciente and not alerta and not bajo, "nota": _nota(c, t, alerta, reciente)})
    filas.sort(key=lambda f: (f["combustible"] is None, f["combustible"] is not None and f["combustible"] < servicios.COMBUSTIBLE_BAJO,
                              -(f["combustible"] or 0), f["id"]))
    return filas


def calcular(automatico=False):
    """Sugerencias de despacho: (lista de viajes sugeridos, resto que no se pudo asignar).

    Con `automatico` solo usa camiones `apto_auto` y deja fuera las entregas no concretadas: volver a mandarlas sin saber qué pasó
    repetiría el viaje fallido, así que las decide una persona con lo que el cliente explicó."""
    ahora = timezone.now()
    por_rango, sin_ubicar, mixtos, reprogramar = {}, [], [], []
    for o in servicios.pedidos_por_despachar():
        rangos = servicios.rangos_de(o)
        if automatico and o.estado_orden.nombre == "Entrega no concretada":
            reprogramar.append(o.orden_id)
        elif len(rangos) != 1:
            mixtos.append(o.orden_id)
        elif o.direccion.lat is None:
            sin_ubicar.append(o.orden_id)
        else:
            por_rango.setdefault(rangos[0], []).append(
                {"orden": o.orden_id, "comuna": o.direccion.comuna.nombre, "espera_min": int((ahora - o.creada_en).total_seconds() // 60)})
    libres = {}
    for c in opciones_camion():
        if c["apto_auto" if automatico else "apto"]:
            libres.setdefault(c["rango"], []).append(c)
    viajes, sin_camion = [], []
    # el rango con el pedido más antiguo se atiende primero
    for rango, pedidos in sorted(por_rango.items(), key=lambda kv: -max(p["espera_min"] for p in kv[1])):
        # pedidos de una misma comuna juntos, partiendo por la que tiene el más antiguo: un viaje no cruza la región sin necesidad
        antigua = {}
        for p in pedidos:
            antigua[p["comuna"]] = max(antigua.get(p["comuna"], 0), p["espera_min"])
        pedidos = sorted(pedidos, key=lambda p: (-antigua[p["comuna"]], p["comuna"]))
        for i in range(0, len(pedidos), MAX_PARADAS):
            grupo = pedidos[i:i + MAX_PARADAS]
            if libres.get(rango):
                c = libres[rango].pop(0)
                viajes.append({"camion": c["id"], "patente": c["patente"], "rango": rango, "pedidos": grupo,
                               "espera_max_min": max(p["espera_min"] for p in grupo), "nota_camion": c["nota"]})
            else:
                sin_camion.append({"rango": rango, "pedidos": len(grupo)})
    return viajes, {"sin_camion": sin_camion, "sin_ubicar": sin_ubicar, "mixtos": mixtos, "reprogramar": reprogramar}


def _espera(minutos):
    return f"{minutos} min" if minutos < 120 else f"{minutos // 60} h"


def texto_base(viajes, resto):
    """Aviso sin IA, armado con plantillas: siempre disponible."""
    frases = []
    for v in viajes:
        n = len(v["pedidos"])
        frases.append(f"{n} pedido{'s' if n != 1 else ''} {v['rango'].lower()}{'s' if n != 1 else ''} esperan despacho (el más antiguo, hace {_espera(v['espera_max_min'])}). "
                      f"{v['camion']} está libre y su rango sirve.")
    for s in resto["sin_camion"]:
        frases.append(f"Hay {s['pedidos']} pedido(s) {s['rango'].lower()}(s) sin camión libre de ese rango.")
    if resto["sin_ubicar"]:
        frases.append(f"Las órdenes {', '.join(map(str, resto['sin_ubicar']))} no tienen ubicación en el mapa; ubícalas para poder despacharlas.")
    if resto["mixtos"]:
        frases.append(f"Las órdenes {', '.join(map(str, resto['mixtos']))} mezclan frío y congelado y no caben en un solo camión.")
    return " ".join(frases)


def _prompt(viajes, resto):
    hechos = json.dumps({"viajes_sugeridos": viajes, **resto}, ensure_ascii=False)
    return ("Eres el asistente de despacho de Cofrial SpA, distribuidora chilena de alimentos refrigerados y congelados. "
            "Con estos hechos, ya calculados por el sistema, escribe un aviso para el despachador: 2 o 3 frases en español, "
            "claras y sin saludos. Di cuántos pedidos esperan, cuánto lleva el más antiguo y qué camión conviene usar para cada viaje. "
            "Usa SOLO los camiones y números que aparecen en los hechos; no inventes nada y no menciones nombres de clientes.\n"
            f"Hechos: {hechos}")


def texto_valido(texto, viajes):
    """El texto de la IA solo vale si no inventa camiones y tiene un largo razonable."""
    permitidos = {v["camion"] for v in viajes}
    return 0 < len(texto) <= 600 and set(re.findall(r"CAM-\d+", texto)) <= permitidos


def redactar(viajes, resto):
    """(texto, por_ia): el aviso redactado por la IA, o el texto base si no hay IA utilizable."""
    base = texto_base(viajes, resto)
    if not viajes:
        return base, False
    prompt = _prompt(viajes, resto)
    clave = "sugerencia_despacho_" + hashlib.sha256(prompt.encode()).hexdigest()
    guardado = cache.get(clave)
    if guardado is not None:
        return guardado, True
    try:
        texto = ia.redactar(prompt).strip()
    except ia.ErrorIA:
        return base, False
    if not texto_valido(texto, viajes):
        return base, False
    cache.set(clave, texto, CACHE_SEG)
    return texto, True


def con_enlaces(viajes):
    """Cada viaje con el enlace que abre «Armar despacho» con el camión y los pedidos ya marcados."""
    return [{**v, "enlace": f"/flota/despachar/?camion={v['camion']}&ordenes={','.join(str(p['orden']) for p in v['pedidos'])}"} for v in viajes]
