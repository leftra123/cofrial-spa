from .models import Carrito, CarritoItem, Cliente


def demo(request):
    """Datos del selector «Comprar como…» (sustituto temporal del login)."""
    cid = request.session.get("cliente_id")
    cliente = Cliente.objects.filter(pk=cid).first() if cid else None
    en_carrito = 0
    if cliente:
        en_carrito = sum(CarritoItem.objects.filter(carrito__cliente=cliente, carrito__estado="abierto").values_list("cantidad", flat=True))
    return {
        "clientes_demo": Cliente.objects.select_related("tipo_cliente").order_by("nombre"),
        "cliente_sesion": cliente,
        "en_carrito": en_carrito,
    }
