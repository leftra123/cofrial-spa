"""Lectura segura de lo que llega por formularios y URL: números acotados. Los destinos de redirección se validan con
`url_has_allowed_host_and_scheme` de Django en cada vista."""
import re

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

