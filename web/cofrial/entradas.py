"""Lectura segura de lo que llega por formularios y URL: números acotados. Los destinos de redirección se validan con
`url_has_allowed_host_and_scheme` de Django en cada vista."""
import re
from urllib.parse import urlencode, urlsplit

from django.utils.http import url_has_allowed_host_and_scheme

ENTERO_MAXIMO = 2_147_483_647            # tope de un IntegerField de PostgreSQL
_ENTERO = re.compile(r"[0-9]{1,10}")      # solo 0-9: str.isdigit() acepta «²» o «٣», que int() no convierte


def entero(valor, maximo=ENTERO_MAXIMO):
    """Convierte «12» o « 12 » en 12. Todo lo demás (signos, decimales, «²», vacío, enormes) lanza ValueError."""
    texto = str(valor).strip()
    if not _ENTERO.fullmatch(texto) or int(texto) > maximo:
        raise ValueError("número no válido")
    return int(texto)


def es_entero(valor):
    try:
        entero(valor)
        return True
    except ValueError:
        return False



def url_de_ingreso(request, defecto="/"):
    """Login con vuelta a donde estaba. Un formulario enviado con la sesión vencida no se puede repetir: su ruta solo acepta POST y
    volver ahí tras ingresar daba una página en blanco (405). Por eso un POST vuelve a la página desde la que se envió."""
    destino = request.path
    if request.method != "GET":
        atras = request.META.get("HTTP_REFERER", "")
        seguro = url_has_allowed_host_and_scheme(atras, allowed_hosts={request.get_host()}, require_https=request.is_secure())
        partes = urlsplit(atras)
        destino = (partes.path + (f"?{partes.query}" if partes.query else "")) if atras and seguro else defecto
    return "/cuenta/entrar/?" + urlencode({"next": destino})
