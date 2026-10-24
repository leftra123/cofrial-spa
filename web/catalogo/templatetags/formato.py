"""Formato chileno: separador de miles con punto, sin decimales y sin sufijo «CLP» ($34.990)."""
from django import template

register = template.Library()


def _miles(valor):
    try:
        return f"{round(float(valor)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


@register.filter
def clp(valor):
    return f"${_miles(valor)}" if _miles(valor) != "" else ""


@register.filter
def miles(valor):
    return _miles(valor)


@register.filter
def iva(valor):
    """IVA de 19 % sobre un monto neto (los precios institucionales se informan netos)."""
    return clp(round(float(valor or 0) * 0.19))


@register.filter
def con_iva(valor):
    return clp(round(float(valor or 0) * 1.19))


@register.filter
def get_item(diccionario, clave):
    """Valor de un diccionario por clave dentro de una plantilla ({{ d|get_item:k }})."""
    return (diccionario or {}).get(clave)


@register.simple_tag
def imagen_producto(producto):
    """Imagen de un producto con la misma prioridad que el catálogo: propia, foto de Commons, ilustración de IA; solo si no hay nada, la de su categoría."""
    from catalogo.views import _fila
    return _fila(producto, {})
