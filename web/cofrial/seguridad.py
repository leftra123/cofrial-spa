"""Defensas de la aplicación contra quien sondea o ataca, y páginas de error controladas.

- Límite de intentos: tras 10 claves malas para una misma cuenta el acceso a esa cuenta se bloquea 15 minutos. El límite por IP
  viene apagado (en la defensa toda la sala sale por una sola IP pública). Ambos se ajustan por entorno (ver settings.py).
  Vale para el ingreso de la tienda y para el del panel de administración.
- Barrido de rutas: quien acumula muchos «no encontrado» (buscando /wp-admin, /.env, /phpmyadmin…) queda con 429 hasta que vence la ventana.
- Registro y soporte: tope por hora, porque crean cuentas y gastan la cuota gratuita de la IA.
- Entradas absurdas: bytes NUL, números fuera de rango o textos más largos que la columna dan 400 y no 500.
- Base de datos caída: 503 con aviso de reintentar, sin traza y sin depender de la base para dibujar la página.

Los contadores viven en la caché de Django (en memoria de cada proceso); para varias instancias detrás de un balanceador
conviene una caché compartida (ver docs/decisiones.md)."""
import logging
import sys

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.core.cache import cache
from django.db import DataError, InterfaceError, OperationalError
from django.dispatch import receiver
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse

log = logging.getLogger("cofrial.seguridad")


# ---------------------------------------------------------------- páginas de error (no dependen de la base ni del menú)
# 400 y 500 usan las páginas propias de main (templates/400.html y 500.html, sin base); 429 y 503 usan errores/simple.html.
# El 403 por CSRF sigue en cofrial.vistas.csrf_fallo.
def pagina(codigo, titulo, mensaje, extra=None):
    html = render_to_string("errores/simple.html", {"codigo": codigo, "titulo": titulo, "mensaje": mensaje})
    respuesta = HttpResponse(html, status=codigo)
    for k, v in (extra or {}).items():
        respuesta[k] = v
    return respuesta


def error_400(request, exception=None):
    return HttpResponse(render_to_string("400.html"), status=400)


def error_500(request):
    """Error inesperado. Si la causa es la base de datos, se responde 503 («reintenta») en vez de un 500 genérico."""
    causa = sys.exc_info()[1]
    if isinstance(causa, (OperationalError, InterfaceError)):
        return sin_base()
    return HttpResponse(render_to_string("500.html"), status=500)


def sin_base():
    log.error("Base de datos no disponible")
    return pagina(503, "Servicio no disponible", "No podemos consultar los datos en este momento. Inténtalo de nuevo en un minuto.",
                  {"Retry-After": "30"})


def demasiadas(motivo, segundos):
    return pagina(429, "Demasiados intentos", f"{motivo} Espera {max(1, round(segundos / 60))} minutos antes de volver a intentarlo.",
                  {"Retry-After": str(segundos)})


# ---------------------------------------------------------------- contadores
def ip_de(request):
    """IP del visitante. Detrás de un balanceador (CONFIAR_PROXY=1) se toma el último salto de X-Forwarded-For, que agregó él."""
    if settings.CONFIAR_PROXY:
        salto = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
        if salto:
            return salto
    return request.META.get("REMOTE_ADDR", "?")


def _contar(clave, ventana):
    cache.add(clave, 0, ventana)
    try:
        return cache.incr(clave)
    except ValueError:                                       # venció entre add e incr
        cache.set(clave, 1, ventana)
        return 1


def _cuenta(clave):
    return cache.get(clave, 0)


def _usuario(request):
    return str(request.POST.get("username", "")).strip().lower()[:150]


@receiver(user_login_failed)
def registrar_fallo(sender, credentials, request=None, **kwargs):
    usuario = str(credentials.get("username", "")).strip().lower()[:150]
    ventana = settings.ACCESO_VENTANA_SEG
    n_usuario = _contar(f"fallos:usuario:{usuario}", ventana)
    n_ip = _contar(f"fallos:ip:{ip_de(request)}", ventana) if request is not None and settings.ACCESO_MAX_FALLOS_IP else 0
    log.warning("Ingreso fallido de %r desde %s (cuenta: %s, IP: %s)", usuario, ip_de(request) if request is not None else "?", n_usuario, n_ip)


@receiver(user_logged_in)
def limpiar_fallos(sender, request, user, **kwargs):
    cache.delete(f"fallos:usuario:{user.get_username().lower()}")


# ---------------------------------------------------------------- middleware
class ProteccionMiddleware:
    """Va antes que sesiones y autenticación: corta rápido a quien ya excedió un límite."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = ip_de(request)
        bloqueo = self._bloqueo(request, ip)
        if bloqueo is not None:
            return bloqueo
        respuesta = self.get_response(request)
        if respuesta.status_code == 404:
            n = _contar(f"escaneo:{ip}", settings.ESCANEO_VENTANA_SEG)
            if n == settings.ESCANEO_MAX_404 + 1:
                log.warning("Barrido de rutas desde %s: %s «no encontrado» en %s s (último: %s)", ip, n - 1, settings.ESCANEO_VENTANA_SEG, request.path[:80])
        return respuesta

    def _bloqueo(self, request, ip):
        if _cuenta(f"escaneo:{ip}") > settings.ESCANEO_MAX_404:
            return demasiadas("Detectamos demasiadas búsquedas de páginas que no existen desde tu conexión.", settings.ESCANEO_VENTANA_SEG)
        if "\x00" in request.path or any("\x00" in k or "\x00" in v for k, v in request.GET.items()):
            return error_400(request)
        if request.method != "POST":
            return None
        if request.content_type == "multipart/form-data":
            request.body            # se lee y queda en memoria antes de request.POST: así la vista aún puede leer el cuerpo (p. ej. /api/asistente/)
        if any("\x00" in k or "\x00" in v for k, v in request.POST.items()):
            return error_400(request)
        if request.path in (reverse("entrar"), reverse("admin:login")):
            if _cuenta(f"fallos:usuario:{_usuario(request)}") >= settings.ACCESO_MAX_FALLOS_USUARIO \
                    or (settings.ACCESO_MAX_FALLOS_IP and _cuenta(f"fallos:ip:{ip}") >= settings.ACCESO_MAX_FALLOS_IP):
                log.warning("Ingreso bloqueado para %r desde %s", _usuario(request), ip)
                return demasiadas("Hubo demasiados ingresos fallidos.", settings.ACCESO_VENTANA_SEG)
        tope = settings.LIMITE_POST_POR_HORA.get(request.path)
        if tope is not None and _contar(f"post:{request.path}:{ip}", 3600) > tope:
            log.warning("Límite por hora superado en %s desde %s", request.path, ip)
            return demasiadas("Superaste el máximo de envíos por hora para este formulario.", 3600)
        return None

    def process_exception(self, request, exception):
        if isinstance(exception, (DataError, OverflowError)):          # un valor que no cabe en la columna: dato inválido, no falla nuestra
            log.warning("Dato no válido en %s: %s", request.path, exception)
            return error_400(request)
        if isinstance(exception, (OperationalError, InterfaceError)):
            return sin_base()
        return None
