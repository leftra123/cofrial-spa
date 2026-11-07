"""Íconos del juego Lucide de react-icons, generados con herramientas/iconos/generar.mjs. La app no usa React: aquí solo se pintan los trazos."""
import json
from functools import lru_cache
from pathlib import Path

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@lru_cache(maxsize=1)
def _iconos():
    return json.loads((Path(__file__).resolve().parent.parent / "iconos.json").read_text(encoding="utf-8"))


@register.simple_tag
def icono(nombre, clase=""):
    """{% icono "camion" %}: SVG decorativo. Un nombre que no existe falla al pintar la pantalla, para notarlo en las pruebas."""
    trazos = mark_safe(_iconos()[nombre])
    return format_html('<svg class="{}" viewBox="0 0 24 24" aria-hidden="true">{}</svg>', f"ico {clase}".strip(), trazos)
