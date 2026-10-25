"""Rutas por calles de los despachos: OSRM (perfil driving) desde el servidor, con caché y respaldo en línea recta.

El recorrido de un viaje es base -> paradas (la más cercana primero) -> base. Se calcula UNA vez al armar el despacho y se guarda en
`despacho.ruta_geojson`; el mapa del despachador, el del cliente y el simulador usan esa misma polilínea. La misma secuencia de puntos
siempre devuelve la misma ruta (tabla ruta_cache), así la demostración no depende del servicio público en cada vista. Si OSRM no
responde, la ruta son las rectas entre los puntos, marcada como aproximada: nunca un error.
"""
import hashlib
import json
import logging
import math
import urllib.error
import urllib.request

from django.conf import settings

from .models import RutaCache

log = logging.getLogger(__name__)


def km_entre(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def largo_km(puntos):
    return sum(km_entre(puntos[i], puntos[i + 1]) for i in range(len(puntos) - 1))


def ordenar_paradas(origen, paradas):
    """Vecino más cercano sobre [(direccion_id, lat, long)]: la sugerencia de orden de entrega."""
    pendientes, orden, actual = list(paradas), [], origen
    while pendientes:
        siguiente = min(pendientes, key=lambda p: km_entre(actual, (p[1], p[2])))
        pendientes.remove(siguiente)
        orden.append(siguiente)
        actual = (siguiente[1], siguiente[2])
    return orden


def _clave(puntos):
    texto = ";".join(f"{lat:.5f},{lon:.5f}" for lat, lon in puntos)
    return hashlib.sha256(texto.encode()).hexdigest()


def _pedir_osrm(puntos):
    """[[lat, long]...] por calles, o None si el servicio no responde (un reintento, tiempo de espera corto)."""
    if not settings.OSRM_URL:
        return None
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in puntos)
    url = f"{settings.OSRM_URL}/route/v1/driving/{coords}?overview=full&geometries=geojson"
    for intento in (1, 2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cofrial-spa/1.0"}), timeout=settings.OSRM_TIMEOUT_SEG) as r:
                datos = json.load(r)
            if datos.get("code") == "Ok" and datos.get("routes"):
                return [[lat, lon] for lon, lat in datos["routes"][0]["geometry"]["coordinates"]]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            log.warning("OSRM no respondió (intento %d): %s", intento, e)
    return None


def ruta_por_calles(puntos):
    """(polilínea [[lat, long]...], km, aproximada) pasando por los puntos en orden. Cacheada por secuencia de coordenadas."""
    puntos = [(float(a), float(b)) for a, b in puntos]
    clave = _clave(puntos)
    en_cache = RutaCache.objects.filter(pk=clave).first()
    if en_cache:
        return en_cache.ruta_geojson, en_cache.km, en_cache.aproximada
    linea = _pedir_osrm(puntos)
    if linea is None:
        recta = [list(p) for p in puntos]
        return recta, round(largo_km(recta), 2), True               # no se guarda: un intento posterior puede conseguir la ruta real
    km = round(largo_km(linea), 2)
    RutaCache.objects.get_or_create(clave=clave, defaults=dict(ruta_geojson=linea, km=km, aproximada=False))
    return linea, km, False


def _indice_cercano(puntos, destino, desde=0):
    return min(range(desde, len(puntos)), key=lambda i: km_entre(puntos[i], destino))


def armar_ruta(paradas):
    """Recorrido completo para las paradas [(direccion_id, lat, long)] (sin repetir direcciones): base -> paradas -> base.
    Devuelve {"puntos", "paradas": [{"direccion_id", "lat", "long", "indice"}], "km", "aproximada"} o None si no hay paradas ubicadas."""
    base = (settings.BASE_LOGISTICA["lat"], settings.BASE_LOGISTICA["long"])
    unicas = {}
    for did, lat, lon in paradas:
        if lat is not None and lon is not None:
            unicas.setdefault(did, (did, float(lat), float(lon)))
    if not unicas:
        return None
    orden = ordenar_paradas(base, list(unicas.values()))
    secuencia = [base] + [(p[1], p[2]) for p in orden] + [base]
    linea, km, aproximada = ruta_por_calles(secuencia)
    marcas, desde = [], 0
    for did, lat, lon in orden:
        if aproximada:                                                  # la recta pasa exactamente por cada punto
            i = next(k for k in range(desde, len(linea)) if (linea[k][0], linea[k][1]) == (lat, lon))
        else:
            i = _indice_cercano(linea, (lat, lon), desde)
        marcas.append({"direccion_id": did, "lat": lat, "long": lon, "indice": i})
        desde = i
    return {"puntos": linea, "paradas": marcas, "km": km, "aproximada": aproximada}


def asegurar_ruta(despacho):
    """La ruta guardada del despacho; si no tiene (viajes anteriores a este cambio), se calcula una vez y se guarda."""
    if despacho.ruta_geojson:
        return despacho.ruta_geojson
    from pedidos.models import Orden
    direcciones = [(o.direccion_id, o.direccion.lat, o.direccion.long)
                   for o in Orden.objects.filter(despacho=despacho).select_related("direccion")]
    ruta = armar_ruta(direcciones)
    if ruta is not None:
        despacho.ruta_geojson, despacho.ruta_aproximada = ruta, ruta["aproximada"]
        despacho.save(update_fields=["ruta_geojson", "ruta_aproximada"])
    return ruta


def km_hasta(ruta, posicion, indice_destino):
    """Km por la ruta desde la posición actual hasta el vértice `indice_destino` (0 si ya lo pasó)."""
    puntos = ruta["puntos"]
    mas_cercano = min(range(len(puntos)), key=lambda i: km_entre(puntos[i], posicion))
    if mas_cercano >= indice_destino:
        return km_entre(posicion, puntos[indice_destino])
    return km_entre(posicion, puntos[mas_cercano]) + largo_km(puntos[mas_cercano:indice_destino + 1])


def precalcular_demo():
    """Deja en caché el recorrido base -> dirección -> base de cada dirección ubicada de los clientes (las de la demostración y las que
    se registren): el primer despacho de una demostración no depende de que el servicio público de rutas esté disponible."""
    from clientes.models import Direccion
    for d in Direccion.objects.filter(lat__isnull=False, long__isnull=False):
        armar_ruta([(d.pk, d.lat, d.long)])
