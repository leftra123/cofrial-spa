"""Sugerencia de despachos: qué pedidos esperan y qué camión libre conviene usar.

Los hechos (qué pedidos, qué camión, cuánto llevan esperando) los calcula el código con las mismas reglas de `despachar`:
cada orden en una cámara de su rango, camión libre y activo, pedidos ubicados en el mapa. La IA solo redacta el aviso a partir de
esos hechos; si falla, no hay clave o inventa un camión, se usa el texto base. Este módulo nunca despacha: el botón lleva al
formulario de «Armar despacho» ya marcado y alguien confirma. El modo automático (`autodespacho.py`) parte del mismo cálculo.
Privacidad: a la IA solo le llegan números de orden, comuna, rango de frío y minutos de espera; ni nombres ni direcciones.
"""
import hashlib
import json
import re
from itertools import zip_longest

from django.core.cache import cache
from django.utils import timezone

from crm import ia

from . import servicios
from .vigente import ultimas_vigentes

MAX_PARADAS = 6           # pedidos por viaje sugerido
DESVIO_MAX_KM = 12        # un pedido va en el mismo viaje si queda «en el camino» de otro: ir a él por esa ruta alarga el recorrido a lo más esto (supuesto del prototipo)
CACHE_SEG = 300           # la misma situación no vuelve a consultar a la IA durante 5 minutos
MAX_VIAJES_EN_MENU = 3    # viajes con enlace propio en el contador del menú; el resto se arma desde «Armar despacho»


def _nota(c, t, alerta, reciente):
    """Por qué un camión queda donde queda en la lista; es el texto que ve la persona."""
    if t is None:
        return f"{c.camion_id} no tiene lecturas de telemetría."
    temp = f"{t.temp_camara:.1f}".replace(".", ",")
    if alerta:
        return f"{c.camion_id} tiene ruptura de frío: la cámara marca {temp} °C."
    temperaturas = " y ".join(f"{x.temp_camara:.1f}".replace(".", ",") + " °C" for x in getattr(t, "camaras", [t]))
    texto = f"{c.camion_id}: {t.combustible_pct} % de combustible, {'cámaras a' if c.dos_camaras else 'cámara a'} {temperaturas}, sin alerta de frío."
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
        filas.append({"id": c.camion_id, "patente": c.patente, "rango": c.rango_temperatura.nombre, "rangos": c.rangos,
                      "combustible": t.combustible_pct if t else None, "alerta": alerta, "apto": not alerta,
                      "apto_auto": reciente and not alerta and not bajo, "nota": _nota(c, t, alerta, reciente)})
    filas.sort(key=lambda f: (f["combustible"] is None, f["combustible"] is not None and f["combustible"] < servicios.COMBUSTIBLE_BAJO,
                              -(f["combustible"] or 0), f["id"]))
    return filas


def _tomar_de_dos_camaras(camiones, rango):
    c = next((x for x in camiones if rango in x["rangos"]), None)
    if c:
        camiones.remove(c)
    return c


def _viajes_de_una_salida(por_rango, camiones):
    """Las direcciones que esperan pedidos de dos rangos, en un camión de dos cámaras: una sola salida en vez de dos camiones al mismo lugar.
    Saca esos pedidos de `por_rango`. Las direcciones con más tiempo de espera van primero y un viaje no pasa de MAX_PARADAS pedidos;
    lo que sobra sigue su curso normal."""
    viajes = []
    while camiones and len(por_rango) > 1:
        c = camiones[0]
        rangos = c["rangos"]
        grupos = {}
        for rango in rangos:
            for p in por_rango.get(rango, []):
                grupos.setdefault(p["direccion"], {}).setdefault(rango, []).append(p)
        compartidas = [g for g in grupos.values() if len(g) == len(rangos)]
        if not compartidas:
            break
        compartidas.sort(key=lambda g: -max(p["espera_min"] for lista in g.values() for p in lista))
        grupo = []
        for g in compartidas:
            cupo = MAX_PARADAS - len(grupo)
            if cupo < len(rangos):                   # lo que no cabe queda para otro viaje, sin separar los dos rangos de una dirección
                break
            intercalados = [p for fila in zip_longest(*g.values()) for p in fila if p]
            grupo += intercalados[:cupo]
        elegidos = {p["orden"] for p in grupo}
        for rango in rangos:
            por_rango[rango] = [p for p in por_rango.get(rango, []) if p["orden"] not in elegidos]
            if not por_rango[rango]:
                del por_rango[rango]
        camiones.pop(0)
        viajes.append({"camion": c["id"], "patente": c["patente"], "rango": " y ".join(rangos), "pedidos": grupo,
                       "espera_max_min": max(p["espera_min"] for p in grupo), "nota_camion": c["nota"]})
    return viajes


def _agrupar_por_camino(pedidos):
    """Junta pedidos que coinciden en la ruta para no mandar un camión por cada uno. Parte por el más lejano de la base (el «ancla») y le suma los que
    quedan en su camino: los que, pasando por ellos de ida, alargan el recorrido a la base ≤ DESVIO_MAX_KM (misma comuna incluida). Un grupo no pasa de MAX_PARADAS."""
    from django.conf import settings
    from . import rutas
    base = (settings.BASE_LOGISTICA["lat"], settings.BASE_LOGISTICA["long"])
    km = rutas.km_entre
    pendientes = sorted(pedidos, key=lambda p: (-km(base, p["pos"]), p["orden"]))
    grupos = []
    while pendientes:
        ancla = pendientes.pop(0)
        grupo = [ancla]
        for p in list(pendientes):
            if len(grupo) >= MAX_PARADAS:
                break
            if km(base, p["pos"]) + km(p["pos"], ancla["pos"]) - km(base, ancla["pos"]) <= DESVIO_MAX_KM:
                grupo.append(p)
                pendientes.remove(p)
        grupos.append(grupo)
    return grupos


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
                {"orden": o.orden_id, "comuna": o.direccion.comuna.nombre, "direccion": o.direccion_id, "espera_min": int((ahora - o.creada_en).total_seconds() // 60),
                 "pos": (o.direccion.lat, o.direccion.long)})
    libres, dos_camaras = {}, []
    for c in opciones_camion():
        if c["apto_auto" if automatico else "apto"]:
            if len(c["rangos"]) > 1:
                dos_camaras.append(c)
            else:
                libres.setdefault(c["rango"], []).append(c)
    viajes, sin_camion = _viajes_de_una_salida(por_rango, dos_camaras), []
    # el rango con el pedido más antiguo se atiende primero
    for rango, pedidos in sorted(por_rango.items(), key=lambda kv: -max(p["espera_min"] for p in kv[1])):
        # los pedidos que quedan en el mismo camino van juntos en un solo camión; los grupos con el pedido más antiguo salen primero
        for grupo in sorted(_agrupar_por_camino(pedidos), key=lambda g: -max(p["espera_min"] for p in g)):
            c = libres[rango].pop(0) if libres.get(rango) else _tomar_de_dos_camaras(dos_camaras, rango)     # los de dos cámaras son pocos: se usan al final
            if c:
                viajes.append({"camion": c["id"], "patente": c["patente"], "rango": rango, "pedidos": grupo,
                               "espera_max_min": max(p["espera_min"] for p in grupo), "nota_camion": c["nota"]})
            else:
                sin_camion.append({"rango": rango, "pedidos": len(grupo)})
    for v in viajes:                           # las coordenadas sirven para agrupar y no salen de aquí: ni a la pantalla ni a la IA
        v["pedidos"] = [{k: x for k, x in p.items() if k != "pos"} for p in v["pedidos"]]
        v["comunas"] = sorted({p["comuna"] for p in v["pedidos"]})
    return viajes, {"sin_camion": sin_camion, "sin_ubicar": sin_ubicar, "mixtos": mixtos, "reprogramar": reprogramar}


def _espera(minutos):
    return f"{minutos} min" if minutos < 120 else f"{minutos // 60} h"


def _de_rango(rango, n):
    """«refrigerados», o «de refrigerado y congelado» cuando el viaje lleva los dos."""
    return f"de {rango.lower()}" if " y " in rango else rango.lower() + ("s" if n != 1 else "")


def _lista(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def texto_base(viajes, resto):
    """Aviso sin IA, armado con plantillas: siempre disponible."""
    frases = []
    for v in viajes:
        n = len(v["pedidos"])
        frases.append(f"{n} pedido{'s' if n != 1 else ''} {_de_rango(v['rango'], n)} espera{'n' if n != 1 else ''} despacho (el más antiguo, hace {_espera(v['espera_max_min'])}). "
                      f"{v['camion']} está libre y su rango sirve."
                      + (f" Van juntos {_lista(v['comunas'])} porque quedan en el mismo camino: un solo camión en vez de {len(v['comunas'])}." if len(v.get("comunas", [])) > 1 else ""))
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
            "claras y sin saludos. Di cuántos pedidos esperan, cuánto lleva el más antiguo y qué camión conviene usar para cada viaje; si un viaje reúne varias comunas, di que van juntas porque quedan en el mismo camino. "
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


def acciones_del_menu(viajes, puede_armar):
    """A dónde lleva el contador del menú. Gerencia consulta y no arma viajes: solo recibe el enlace a Flota."""
    acciones = []
    if puede_armar:
        for v in con_enlaces(viajes[:MAX_VIAJES_EN_MENU]):
            n = len(v["pedidos"])
            acciones.append({"texto": f"Armar despacho con {v['camion']} ({n} pedido{'s' if n != 1 else ''})", "url": v["enlace"]})
        acciones.append({"texto": "Armar despacho", "url": "/flota/despachar/"})
    return acciones + [{"texto": "Ver la sugerencia en Flota", "url": "/flota/"}]


# ---------------------------------------------------------------------------------------------------------- qué camión usar para estas solicitudes
VIAJE_LARGO_KM = 150          # ida y vuelta; desde aquí el camión necesita combustible de sobra (supuesto del prototipo, no un dato de Cofrial)
COMBUSTIBLE_VIAJE_LARGO = 50  # % mínimo para un viaje largo; en uno corto basta lo que ya exige el sistema (COMBUSTIBLE_BAJO)


def _km_de_ida_y_vuelta(ordenes):
    """Estimación sin pedir rutas: línea recta base → paradas (vecino más cercano) → base, por el factor de calles. La ruta real por calles se calcula al despachar."""
    from django.conf import settings
    from . import rutas
    paradas = [(o.direccion_id, o.direccion.lat, o.direccion.long) for o in ordenes if o.direccion.lat is not None]
    if not paradas:
        return None
    base = (settings.BASE_LOGISTICA["lat"], settings.BASE_LOGISTICA["long"])
    orden = rutas.ordenar_paradas(base, paradas)
    puntos = [base] + [(p[1], p[2]) for p in orden] + [base]
    return round(rutas.largo_km(puntos) * settings.FACTOR_CALLES)


def sugerir_para(orden_ids):
    """Qué camión conviene para estos pedidos. Decide el código, con reglas a la vista: el rango de frío que exigen los productos, un camión libre y sano
    (sin ruptura, sin revisión técnica, con lecturas recientes), y combustible suficiente para el largo del viaje. Entre los que sirven gana el que tiene más
    combustible, y para un solo rango se prefiere un camión simple (los de dos cámaras son pocos). Devuelve None si no hay pedidos válidos."""
    from . import tiempo
    ordenes = list(servicios.pedidos_por_despachar().filter(pk__in=orden_ids))
    if not ordenes:
        return None
    rangos = sorted({r for o in ordenes for r in servicios.rangos_de(o)})
    km = _km_de_ida_y_vuelta(ordenes)
    largo = bool(km and km >= VIAJE_LARGO_KM)
    minimo = COMBUSTIBLE_VIAJE_LARGO if largo else servicios.COMBUSTIBLE_BAJO
    candidatos, descartados = [], []
    for c in opciones_camion():
        if not all(r in c["rangos"] for r in rangos):
            continue                                            # no es de ese frío: no merece ni mencionarse
        motivo = None
        if not c["apto"]:
            motivo = "tiene ruptura de frío"
        elif not c["apto_auto"]:
            motivo = "no tiene lecturas recientes o le queda poco combustible"
        elif c["combustible"] is not None and c["combustible"] < minimo:
            motivo = f"tiene {c['combustible']} % de combustible y este viaje pide al menos {minimo} %"
        (descartados if motivo else candidatos).append({**c, "motivo": motivo})
    candidatos.sort(key=lambda c: (len(c["rangos"]) != len(rangos), -(c["combustible"] or 0), c["id"]))
    elegido = candidatos[0] if candidatos else None
    return {"ordenes": [o.orden_id for o in ordenes], "rangos": rangos, "destinos": sorted({o.direccion.comuna.nombre for o in ordenes}),
            "km": km, "minutos": round(tiempo.minutos_de_viaje(km)) if km else None, "viaje_largo": largo, "minimo_combustible": minimo,
            "camion": None if elegido is None else {k: elegido[k] for k in ("id", "patente", "combustible", "rangos")},
            "alternativas": [{k: c[k] for k in ("id", "combustible")} for c in candidatos[1:3]],
            "descartados": [{"id": c["id"], "motivo": c["motivo"]} for c in descartados[:3]]}


def _hm(minutos):
    h, m = divmod(int(minutos), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def texto_para(s):
    """Explicación sin IA, de plantilla: siempre disponible."""
    lugar = " y ".join(s["destinos"]) if len(s["destinos"]) <= 2 else f"{len(s['destinos'])} comunas"
    viaje = f" Son unos {s['km']} km entre ida y vuelta (≈ {_hm(s['minutos'])} sin contar paradas)." if s["km"] else ""
    if s["camion"] is None:
        porque = "; ".join(f"{d['id']} {d['motivo']}" for d in s["descartados"])
        return (f"Para {lugar} ({' y '.join(r.lower() for r in s['rangos'])}) no hay un camión libre que sirva ahora." + viaje +
                (f" Descartados: {porque}." if porque else " Espera a que uno vuelva a la base."))
    c = s["camion"]
    alt = f" Alternativas: {', '.join(a['id'] for a in s['alternativas'])}." if s["alternativas"] else ""
    return (f"Para {lugar} conviene {c['id']}: es {' y '.join(r.lower() for r in c['rangos'])}, está libre, sin alertas y con {c['combustible']} % de combustible."
            + viaje + (f" Como el viaje es largo, se exige al menos {s['minimo_combustible']} % de combustible." if s["viaje_largo"] else "") + alt)


def redactar_para(s):
    """(texto, por_ia): la misma explicación escrita por la IA, o el texto base. La IA solo recibe comunas, kilómetros, rangos y camiones; ningún cliente."""
    base = texto_para(s)
    prompt = ("Eres el asistente de despacho de Cofrial SpA. Con estos hechos, ya calculados por el sistema, explica en 2 frases en español, sin saludos, qué camión "
              "conviene usar y por qué. Usa SOLO los camiones y números de los hechos; no inventes nada ni menciones clientes.\n"
              f"Hechos: {json.dumps({k: v for k, v in s.items() if k != 'ordenes'}, ensure_ascii=False)}")
    clave = "sugerencia_camion_" + hashlib.sha256(prompt.encode()).hexdigest()
    guardado = cache.get(clave)
    if guardado is not None:
        return guardado, True
    permitidos = {s["camion"]["id"]} if s["camion"] else set()
    permitidos |= {a["id"] for a in s["alternativas"]} | {d["id"] for d in s["descartados"]}
    try:
        texto = ia.redactar(prompt).strip()
    except ia.ErrorIA:
        return base, False
    if not 0 < len(texto) <= 500 or not set(re.findall(r"CAM-\d+", texto)) <= permitidos:
        return base, False
    cache.set(clave, texto, CACHE_SEG)
    return texto, True
