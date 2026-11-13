"""Dónde empieza cada cuenta y qué ve en el menú. Un solo lugar: el login, el logo, «/», el 403 y el 404 usan `inicio_de`.
Solo es presentación: los permisos reales siguen en cada vista (ver docs/rutas-y-roles.md)."""
from crm import servicios as crm
from pedidos import servicios as pedidos

PORTADA = "/"
INICIOS = {"anonimo": "/", "cliente": "/catalogo/", "vendedor": "/crm/", "gerencia": "/crm/", "despachador": "/flota/", "admin": "/crm/", "personal": "/catalogo/"}
ETIQUETAS = {"cliente": "Cliente", "vendedor": "Vendedor", "gerencia": "Gerencia", "despachador": "Despachador", "admin": "Administrador", "personal": "Personal"}


def tipo_de(usuario):
    """anonimo, cliente, vendedor, gerencia, despachador, admin, o personal (cuenta de staff sin rol del CRM)."""
    if not usuario.is_authenticated:
        return "anonimo"
    rol = crm.rol(usuario)
    if rol:
        return rol
    if pedidos.cliente_de(usuario) is not None:
        return "cliente"
    return "personal" if usuario.is_staff else "anonimo"


def inicio_de(usuario):
    return INICIOS[tipo_de(usuario)]
