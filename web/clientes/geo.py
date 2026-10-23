"""Ubicación de una dirección con Nominatim (OpenStreetMap): gratuito y sin cuenta ni clave.

Mejor esfuerzo: si no hay red o no encuentra la dirección, devuelve None y la dirección queda sin ubicar (no se traza ruta).
La política de uso pide un identificador propio y como máximo una consulta por segundo."""
import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

log = logging.getLogger("cofrial.geo")
URL = "https://nominatim.openstreetmap.org/search"


def geocodificar(calle_numero, comuna):
    if not getattr(settings, "GEOCODIFICAR", True):
        return None
    consulta = urllib.parse.urlencode({"format": "json", "limit": 1, "countrycodes": "cl", "q": f"{calle_numero}, {comuna}, Chile"})
    pedido = urllib.request.Request(f"{URL}?{consulta}", headers={"User-Agent": "cofrial-spa-academico/1.0"})
    try:
        datos = json.loads(urllib.request.urlopen(pedido, timeout=4).read())
        return (float(datos[0]["lat"]), float(datos[0]["lon"])) if datos else None
    except Exception as e:                                  # red caída, límite de uso, respuesta rara: no debe romper el registro
        log.warning("No se pudo ubicar «%s»: %s", calle_numero, e)
        return None


def ubicar(direccion):
    """Completa lat y long de una Direccion si faltan. Devuelve True si quedó ubicada."""
    if direccion.lat is None:
        punto = geocodificar(direccion.calle_numero, direccion.comuna.nombre)
        if punto:
            direccion.lat, direccion.long = punto
            direccion.save(update_fields=["lat", "long"])
    return direccion.lat is not None
