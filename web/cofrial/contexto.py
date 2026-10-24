"""Qué enlaces del menú puede usar la cuenta. Solo presentación: los permisos reales siguen en las vistas."""
from catalogo import avisos
from crm import servicios as crm
from pedidos import servicios as pedidos
from pedidos.models import CarritoItem


def _grafana(request):
    """El tablero de Grafana corre en el mismo servidor (puerto 3000); GRAFANA_URL permite apuntarlo a otro lado."""
    import os
    return os.environ.get("GRAFANA_URL") or f"{request.scheme}://{request.get_host().split(':')[0]}:3000/"


def menu(request):
    u = request.user
    if not u.is_authenticated:
        return {"menu": {"cliente": False, "crm": False, "flota": False, "admin": False}, "carrito_n": 0, "cliente_tienda": None, "avisos_n": 0, "grafana_url": ""}
    rol = crm.rol(u)
    cliente = pedidos.cliente_de(u)
    n = 0
    if cliente is not None:
        n = sum(CarritoItem.objects.filter(carrito__cliente=cliente, carrito__estado="abierto").values_list("cantidad", flat=True))
    return {"menu": {"cliente": cliente is not None, "crm": rol is not None,
                     "flota": rol in ("admin", "gerencia", "despachador"), "admin": u.is_staff},
            "carrito_n": n, "cliente_tienda": cliente,
            "avisos_n": avisos.cuantos_disponibles(cliente) if cliente is not None else 0,
            "grafana_url": _grafana(request) if rol is not None or u.is_staff else ""}
