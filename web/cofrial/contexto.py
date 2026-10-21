"""Qué enlaces del menú puede usar la cuenta. Solo presentación: los permisos reales siguen en las vistas."""
from crm import servicios as crm
from pedidos import servicios as pedidos


def menu(request):
    u = request.user
    if not u.is_authenticated:
        return {"menu": {"cliente": False, "crm": False, "flota": False, "admin": False}}
    rol = crm.rol(u)
    return {"menu": {"cliente": pedidos.cliente_de(u) is not None, "crm": rol is not None,
                     "flota": rol in ("admin", "gerencia", "despachador"), "admin": u.is_staff}}
