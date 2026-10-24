"""Imágenes responsivas: ofrece las variantes AVIF que generó `herramientas/optimizar_fotos.py` y deja el archivo original como respaldo."""
from functools import lru_cache
from pathlib import PurePosixPath

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()
ANCHOS = (400, 800, 1672)


@lru_cache(maxsize=512)
def _variantes(ruta):
    """Lista «url ancho» de las variantes AVIF que existen; vacía si la foto no se optimizó (por ejemplo una .png subida a mano)."""
    p = PurePosixPath(ruta)
    return tuple(f"{static(str(p.with_name(f'{p.stem}-{a}.avif')))} {a}w" for a in ANCHOS
                 if finders.find(str(p.with_name(f"{p.stem}-{a}.avif"))))


@register.inclusion_tag("componentes/foto.html")
def foto(ruta, clase="foto", alt="", sizes="100vw", ancho=800, alto=800, prioridad=False):
    return {"src": static(ruta), "avif": ", ".join(_variantes(ruta)), "clase": clase, "alt": alt, "sizes": sizes,
            "ancho": ancho, "alto": alto, "prioridad": prioridad}

