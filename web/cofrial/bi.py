"""Panel de BI (Grafana) detrás de la aplicación: solo entra quien tiene sesión y un rol permitido.

Grafana ya no se publica hacia internet. Corre en la red interna de Docker y esta vista es su única puerta: comprueba la
sesión de Django y el rol, y reenvía la petición a Grafana con la identidad en la cabecera X-WEBAUTH-USER (modo «auth proxy»
de Grafana). Grafana confía en esa cabecera, por eso:

- el puerto de Grafana no debe publicarse jamás fuera de la red de Docker (ni en el compose ni en el Security Group);
- las cabeceras X-WEBAUTH-* que traiga el navegador se descartan antes de reenviar;
- la cookie de sesión y el token CSRF de Django no se reenvían a Grafana.

Roles: administrador (edita) y gerencia (solo mira). Grafana Live (websockets) está apagado: WSGI no los soporta y el tablero
se actualiza por consultas cada 5 s."""
import http.client
import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from crm import servicios as crm

log = logging.getLogger("cofrial.bi")

ROLES_BI = {"admin": "Admin", "gerencia": "Viewer"}          # rol de Django -> rol dentro de Grafana
PREFIJO_USUARIO = "django-"                                     # evita chocar con las cuentas propias de Grafana (admin)
CABECERAS_SALTO = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
                   "transfer-encoding", "upgrade", "host", "cookie", "set-cookie"}
LECTURA = 64 * 1024
METODOS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}


def _cookies_para_grafana(crudas):
    """Las cookies de Grafana pasan; las de Django (sesión y CSRF) se quedan aquí."""
    propias = (settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME)
    piezas = [p.strip() for p in crudas.split(";") if p.strip()]
    return "; ".join(p for p in piezas if p.split("=", 1)[0].strip() not in propias)


def _origen_valido(request):
    """En métodos que escriben, un Origin presente debe ser el de este mismo sitio (Grafana revisa lo mismo con la cabecera Host)."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    origen = request.META.get("HTTP_ORIGIN")
    return origen is None or urlsplit(origen).netloc == request.get_host()


def _cabeceras_de_ida(request, rol):
    cabeceras = {}
    for clave, valor in request.headers.items():
        bajo = clave.lower()
        if bajo in CABECERAS_SALTO or bajo in ("content-length", "forwarded", "authorization") or bajo.startswith(("x-webauth", "x-forwarded")):
            continue
        cabeceras[clave] = valor
    cookies = _cookies_para_grafana(request.META.get("HTTP_COOKIE", ""))
    if cookies:
        cabeceras["Cookie"] = cookies
    cabeceras["Host"] = request.get_host()                                   # Grafana compara Origin con Host al validar escrituras
    cabeceras["X-WEBAUTH-USER"] = PREFIJO_USUARIO + request.user.get_username()
    cabeceras["X-WEBAUTH-ROLE"] = ROLES_BI[rol]
    cabeceras["X-Forwarded-Proto"] = request.scheme
    return cabeceras


def _cuerpo(respuesta, conexion):
    try:
        while True:
            trozo = respuesta.read(LECTURA)
            if not trozo:
                break
            yield trozo
    finally:
        conexion.close()


@csrf_exempt                       # la defensa contra CSRF es _origen_valido, SameSite=Lax en la cookie de sesión y la revisión propia de Grafana
def proxy(request, ruta=""):
    if not request.user.is_authenticated:
        return redirect(f"/cuenta/entrar/?next={request.path}")
    rol = crm.rol(request.user)
    if rol not in ROLES_BI:
        return render(request, "403.html", {"detalle": "El panel de BI es para administración y gerencia."}, status=403)
    if request.method not in METODOS or not _origen_valido(request):
        return HttpResponse("Petición no permitida.", status=403, content_type="text/plain")

    destino = urlsplit(settings.GRAFANA_INTERNA_URL)
    conexion = http.client.HTTPConnection(destino.hostname, destino.port or 80, timeout=settings.GRAFANA_TIMEOUT_SEG)
    camino = request.path + (f"?{request.META['QUERY_STRING']}" if request.META.get("QUERY_STRING") else "")
    cuerpo = request.body if request.method in ("POST", "PUT", "PATCH", "DELETE") else None
    try:
        conexion.request(request.method, camino, body=cuerpo, headers=_cabeceras_de_ida(request, rol))
        respuesta = conexion.getresponse()
    except (OSError, http.client.HTTPException) as e:
        conexion.close()
        log.error("Grafana no responde (%s): %s", settings.GRAFANA_INTERNA_URL, e)
        return render(request, "errores/simple.html", {"codigo": 502, "titulo": "El tablero no está disponible",
                      "mensaje": "No pudimos conectar con el tablero de BI. Inténtalo de nuevo en un minuto."}, status=502)

    if request.method == "HEAD":
        conexion.close()
        salida = StreamingHttpResponse(iter(()), status=respuesta.status)
    else:
        salida = StreamingHttpResponse(_cuerpo(respuesta, conexion), status=respuesta.status)
    for clave, valor in respuesta.getheaders():
        if clave.lower() not in CABECERAS_SALTO:
            salida[clave] = valor
    for valor in respuesta.msg.get_all("Set-Cookie") or []:                  # una respuesta puede traer varias cookies
        salida.cookies.load(valor)
    if request.path.startswith("/bi/api/"):
        salida["Cache-Control"] = "private, no-store"
    return salida
