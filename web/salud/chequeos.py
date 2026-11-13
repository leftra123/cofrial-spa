"""Las revisiones. Cada una devuelve (estado, ms, detalle), o None si el componente no está configurado (no se registra nada).
Nunca lanzan: una revisión que falla ES el dato. El detalle es siempre una frase fija; no se copia texto de respuestas ajenas.
Los chequeos de Gemini, Groq y Mercado Pago solo LISTAN (modelos o cuenta): no gastan cuota de tokens ni cobran nada."""
import os
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.db import connection
from django.utils import timezone

from flota.models import Telemetria

OK, DEGRADADO, CAIDO = "ok", "degradado", "caido"
LENTO_MS = 4000
BASE_LENTA_MS = 1500
IOT_OK_SEG, IOT_DEGRADADO_SEG = 180, 600          # el simulador inserta cada 5 s: 3 min sin lecturas ya es raro
PLAZO_SEG = 8


def _http(url, cabeceras=None):
    """(codigo|None, ms, texto_de_falla). codigo None = no hubo respuesta HTTP."""
    pedido = urllib.request.Request(url, headers={"User-Agent": "cofrial-vigilante/1.0", **(cabeceras or {})})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(pedido, timeout=PLAZO_SEG) as r:
            r.read(1024)
            return r.status, round((time.monotonic() - t0) * 1000), ""
    except urllib.error.HTTPError as e:
        return e.code, round((time.monotonic() - t0) * 1000), ""
    except TimeoutError:
        return None, round((time.monotonic() - t0) * 1000), "tiempo agotado"
    except (urllib.error.URLError, OSError, ValueError) as e:
        causa = getattr(e, "reason", e)
        return None, round((time.monotonic() - t0) * 1000), "tiempo agotado" if isinstance(causa, TimeoutError) else "sin conexión"


def _por_codigo(codigo, ms, falla, rechazo="HTTP "):
    if codigo is None:
        return CAIDO, ms, falla
    if 200 <= codigo < 300:
        return (DEGRADADO, ms, "respuesta lenta") if ms > LENTO_MS else (OK, ms, "")
    if codigo == 429:
        return DEGRADADO, ms, "límite de uso (HTTP 429)"
    if codigo in (401, 403):
        return CAIDO, ms, "credencial rechazada"
    return CAIDO, ms, f"{rechazo}{codigo}"


def web():
    url = os.environ.get("SALUD_URL_WEB") or "http://127.0.0.1:8000/salud/"
    host = next((h for h in settings.ALLOWED_HOSTS if h and not h.startswith(("*", "."))), None)
    return _por_codigo(*_http(url, {"Host": host} if host else None))


def publico():
    url = os.environ.get("SALUD_URL_PUBLICA")
    if not url:
        return None
    return _por_codigo(*_http(url.rstrip("/") + "/salud/"))


def base():
    t0 = time.monotonic()
    try:
        if not connection.in_atomic_block:
            connection.close()                               # conexión nueva: una persistente ya muerta no debe esconder la caída
        with connection.cursor() as c:
            c.execute("SELECT 1")
    except Exception:
        return CAIDO, round((time.monotonic() - t0) * 1000), "no responde"
    ms = round((time.monotonic() - t0) * 1000)
    return (DEGRADADO, ms, "respuesta lenta") if ms > BASE_LENTA_MS else (OK, ms, "")


def iot():
    t0 = time.monotonic()
    try:
        ultima = Telemetria.objects.order_by("-registrado_en").values_list("registrado_en", flat=True).first()
    except Exception:
        return CAIDO, None, "no se pudo leer la base"
    ms = round((time.monotonic() - t0) * 1000)
    if ultima is None:
        return CAIDO, ms, "sin lecturas"
    edad = (timezone.now() - ultima).total_seconds()
    if edad <= IOT_OK_SEG:
        return OK, ms, ""
    return (DEGRADADO if edad <= IOT_DEGRADADO_SEG else CAIDO), ms, f"última lectura hace {max(1, round(edad / 60))} min"


def grafana():
    return _por_codigo(*_http(settings.GRAFANA_INTERNA_URL.rstrip("/") + "/api/health"))


def gemini():
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        return None
    return _por_codigo(*_http("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1", {"x-goog-api-key": clave}))


def groq():
    clave = os.environ.get("GROQ_API_KEY")
    if not clave:
        return None
    return _por_codigo(*_http("https://api.groq.com/openai/v1/models", {"Authorization": f"Bearer {clave}"}))


def mercadopago():
    token = getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")
    if not token:
        return None
    return _por_codigo(*_http("https://api.mercadopago.com/users/me", {"Authorization": f"Bearer {token}"}))


REVISIONES = {"web": web, "publico": publico, "base": base, "iot": iot, "grafana": grafana,
              "gemini": gemini, "groq": groq, "mercadopago": mercadopago}
