"""Qué enlaces del menú puede usar la cuenta. Solo presentación: los permisos reales siguen en las vistas."""
from django.conf import settings

from catalogo import avisos
from .acceso import ETIQUETAS, INICIOS, tipo_de
from crm import servicios as crm
from flota import tiempo
from . import bi
from pedidos import servicios as pedidos


def _grafana(rol):
    """El tablero de Grafana ya no se publica: se abre por /bi/ y solo lo ven los roles que cofrial.bi deja pasar."""
    return "/bi/" if rol in bi.ROLES_BI else ""


def menu(request):
    u = request.user
    tiles = {"mapa_tiles": settings.MAPA_TILES, "asistente_activo": settings.ASISTENTE_ACTIVO}
    if not u.is_authenticated:
        return {"menu": {"cliente": False, "crm": False, "flota": False, "admin": False, "operacion": False, "demo": False, "torre": False, "tienda": True, "comercial": False}, "inicio_url": "/", "tipo_cuenta": "anonimo", "etiqueta_cuenta": "", "carrito_n": 0, "cliente_tienda": None, "avisos_n": 0, "solicitudes_n": 0, "grafana_url": "", "tiempo_x": 1, **tiles}
    rol = crm.rol(u)
    cliente = pedidos.cliente_de(u)
    n = 0
    if cliente is not None:
        n = pedidos.lineas_en_carrito(cliente)
    tipo = tipo_de(u)
    return {"menu": {"cliente": cliente is not None, "crm": rol is not None,
                     "flota": rol in ("admin", "gerencia", "despachador"), "admin": u.is_superuser, "operacion": u.is_superuser, "demo": u.is_superuser, "torre": rol in ("admin", "gerencia"),
                     "tienda": tipo in ("cliente", "admin"),                       # la tienda es de los clientes; el administrador la ve para revisarla
                     "comercial": rol in ("admin", "gerencia", "vendedor")},       # el despachador del CRM solo usa demanda y alertas de frío
            "inicio_url": INICIOS[tipo], "tipo_cuenta": tipo, "etiqueta_cuenta": ETIQUETAS.get(tipo, ""),
            "carrito_n": n, "cliente_tienda": cliente,
            "avisos_n": avisos.cuantos_disponibles(cliente) if cliente is not None else 0,
            "solicitudes_n": crm.solicitudes_empresa().count() if rol in ("admin", "gerencia", "vendedor") else 0,   # empresas por aprobar
            "grafana_url": _grafana(rol), "tiempo_x": tiempo.multiplicador(), **tiles}
