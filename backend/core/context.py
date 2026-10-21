from . import cuentas
from .models import CarritoItem


def sesion(request):
    """Cliente con sesión iniciada y cantidad de unidades en su carrito (para la cabecera)."""
    cliente = cuentas.cliente_de_sesion(request)
    en_carrito = 0
    if cliente:
        en_carrito = sum(CarritoItem.objects.filter(carrito__cliente=cliente, carrito__estado="abierto").values_list("cantidad", flat=True))
    return {"cliente_sesion": cliente, "en_carrito": en_carrito}
