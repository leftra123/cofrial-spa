"""Qué enlaces del menú puede usar la cuenta. Solo presentación: los permisos reales siguen en las vistas."""
from django.conf import settings

from catalogo import avisos
from .acceso import ETIQUETAS, INICIOS, tipo_de
from crm import servicios as crm
from pedidos import servicios as pedidos
from pedidos.models import CarritoItem


def _grafana(request):
    """El tablero de Grafana corre en el mismo servidor (puerto 3000); GRAFANA_URL permite apuntarlo a otro lado."""
    import os
    return os.environ.get("GRAFANA_URL") or f"{request.scheme}://{request.get_host().split(':')[0]}:3000/"


def menu(request):
    u = request.user
    tiles = {"mapa_tiles": settings.MAPA_TILES, "asistente_activo": settings.ASISTENTE_ACTIVO}
    if not u.is_authenticated:
        return {"menu": {"cliente": False, "crm": False, "flota": False, "admin": False, "demo": False, "tienda": True, "comercial": False}, "inicio_url": "/", "tipo_cuenta": "anonimo", "etiqueta_cuenta": "", "carrito_n": 0, "cliente_tienda": None, "avisos_n": 0, "grafana_url": "", **tiles}
    rol = crm.rol(u)
    cliente = pedidos.cliente_de(u)
    n = 0
    if cliente is not None:
        n = sum(CarritoItem.objects.filter(carrito__cliente=cliente, carrito__estado="abierto").values_list("cantidad", flat=True))
    tipo = tipo_de(u)
    return {"menu": {"cliente": cliente is not None, "crm": rol is not None,
                     "flota": rol in ("admin", "gerencia", "despachador"), "admin": u.is_superuser, "demo": u.is_superuser,
                     "tienda": tipo in ("cliente", "admin"),                       # la tienda es de los clientes; el administrador la ve para revisarla
                     "comercial": rol in ("admin", "gerencia", "vendedor")},       # el despachador del CRM solo usa demanda y alertas de frío
            "inicio_url": INICIOS[tipo], "tipo_cuenta": tipo, "etiqueta_cuenta": ETIQUETAS.get(tipo, ""),
            "carrito_n": n, "cliente_tienda": cliente,
            "avisos_n": avisos.cuantos_disponibles(cliente) if cliente is not None else 0,
            "grafana_url": _grafana(request) if rol is not None or u.is_staff else "", **tiles}
