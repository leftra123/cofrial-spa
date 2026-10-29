"""Configuración de Cofrial. Todo lo sensible viene del entorno (.env), nunca del código."""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def entorno(nombre, defecto=None):
    return os.environ.get(nombre, defecto)


DEBUG = entorno("DJANGO_DEBUG", "0") == "1"
# Sin clave propia solo se arranca en desarrollo (DEBUG) o en las pruebas: una clave conocida permite falsificar sesiones.
SECRET_KEY = entorno("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not (DEBUG or "test" in sys.argv):
        raise RuntimeError("Define DJANGO_SECRET_KEY en .env (una clave larga y aleatoria).")
    SECRET_KEY = "clave-solo-para-desarrollo"
ALLOWED_HOSTS = [h for h in entorno("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in entorno("DJANGO_CSRF_ORIGINS", "").split(",") if o]
CSRF_FAILURE_VIEW = "cofrial.vistas.csrf_fallo"
# Ruta del panel de administración. En producción conviene una propia (DJANGO_ADMIN_URL=panel-9f3k/) para que /admin/ no exista.
ADMIN_URL = entorno("DJANGO_ADMIN_URL", "admin/").strip("/") + "/"
# Detrás de un balanceador (ALB/nginx) que agrega X-Forwarded-For: DJANGO_CONFIAR_PROXY=1 usa esa IP en los límites de intentos.
CONFIAR_PROXY = entorno("DJANGO_CONFIAR_PROXY", "0") == "1"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "catalogo",
    "clientes",
    "pedidos",
    "flota",
    "crm",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "cofrial.seguridad.ProteccionMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cofrial.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"builtins": ["catalogo.templatetags.formato"],
    "context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "cofrial.contexto.menu",
    ]},
}]
WSGI_APPLICATION = "cofrial.wsgi.application"

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": entorno("DB_NAME", "cofrial"),
    "USER": entorno("DB_USER", "cofrial"),
    "PASSWORD": entorno("DB_PASSWORD", ""),
    "HOST": entorno("DB_HOST", "localhost"),
    "PORT": entorno("DB_PORT", "5432"),
    "CONN_MAX_AGE": 60,
    "CONN_HEALTH_CHECKS": True,                  # comprueba que la conexión persistente siga viva antes de reutilizarla (RDS puede cerrarla)
    "OPTIONS": {"sslmode": entorno("DB_SSLMODE", "prefer")},     # contra RDS: DB_SSLMODE=require
}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Archivos con huella en el nombre (cofrial.3f9a1c.css) y caché larga: WhiteNoise los sirve como inmutables. Las pruebas
# y el modo de desarrollo usan nombres planos porque no hay collectstatic previo.
_CON_HUELLA = not DEBUG and "test" not in sys.argv
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if _CON_HUELLA
                    else "whitenoise.storage.CompressedStaticFilesStorage"},
}
# API JSON de solo lectura: misma sesión del sitio, sin navegador de la API y siempre con sesión iniciada.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
# Detrás de HTTPS (DJANGO_HTTPS=1): cookies solo por canal seguro, HSTS y redirección. Apagado por defecto porque la demo en EC2 puede ir por HTTP.
if entorno("DJANGO_HTTPS", "0") == "1":
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
LOGIN_URL = "/cuenta/entrar/"
LOGIN_REDIRECT_URL = "/"                        # lo decide cofrial.acceso.inicio_de(); «/» envía a cada cuenta a su inicio
LOGOUT_REDIRECT_URL = "/"

# Los mosaicos de OpenStreetMap exigen que el navegador envíe el Referer (su política de uso). Django envía por defecto «same-origin»,
# que lo quita en las peticiones a otro sitio y OSM responde «403 Access blocked». Con esta política se envía solo el origen (sin ruta ni datos).
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Asistente de IA de la tienda (ASISTENTE_ACTIVO=0 lo apaga sin tocar el resto).
ASISTENTE_ACTIVO = os.environ.get("ASISTENTE_ACTIVO", "1") == "1"

# Mosaicos del mapa. Por defecto, OpenStreetMap (uso liviano, con Referer y atribución). Para otro proveedor, definir las variables
# MAP_TILE_URL y MAP_TILE_ATTRIBUTION (y MAP_TILE_SUBDOMAINS / MAP_TILE_MAX_ZOOM si hace falta); las claves del proveedor, si las pide, van en la propia URL.
MAPA_TILES = {
    "url": os.environ.get("MAP_TILE_URL") or "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "attribution": os.environ.get("MAP_TILE_ATTRIBUTION") or "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
    "maxZoom": int(os.environ.get("MAP_TILE_MAX_ZOOM") or 19),
    "subdomains": os.environ.get("MAP_TILE_SUBDOMAINS") or "abc",
}

# Mapa y rutas (OpenStreetMap, sin clave). La base es el punto de salida de los camiones, el mismo donde parte el simulador IoT.
BASE_LOGISTICA = {"nombre": "Frigorífico central, Temuco", "lat": -38.7330, "long": -72.6040}   # referencia: INACAP Temuco
GEOCODIFICAR = os.environ.get("GEOCODIFICAR", "1") == "1" and "test" not in sys.argv


# Registro de errores: con DEBUG apagado Django no imprime los 500 en la consola (solo los manda por correo, que no está configurado),
# así que `docker logs` no mostraba ningún traceback. Todo va a la salida estándar, que es lo que lee Docker.
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"consola": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "loggers": {
        "django.request": {"handlers": ["consola"], "level": "WARNING", "propagate": False},
        "django.db.backends": {"handlers": ["consola"], "level": "ERROR", "propagate": False},
        "cofrial": {"handlers": ["consola"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["consola"], "level": "WARNING"},
}

# Velocidad media de reparto y factor de calles: los usan la hora de llegada de la tienda y el simulador IoT (mismas variables).
VELOCIDAD_MEDIA_KMH = float(os.environ.get("VELOCIDAD_MEDIA_KMH") or 50)
FACTOR_CALLES = float(os.environ.get("FACTOR_CALLES") or 1.3)

# Rutas por calles: el servidor las calcula con OSRM (perfil driving) al armar un despacho y las guarda; vacío = sin OSRM (rectas marcadas como aproximadas).
OSRM_URL = "" if "test" in sys.argv else os.environ.get("OSRM_URL", "https://router.project-osrm.org")
OSRM_TIMEOUT_SEG = float(os.environ.get("OSRM_TIMEOUT_SEG") or 4)
# Tiempo que el cliente tiene para confirmar la entrega cuando el camión llega a su puerta; vencido, el pedido se da por entregado solo.
# 120 s sirve para la demostración; en una operación real serían horas.
CONFIRMACION_AUTO_SEG = int(os.environ.get("CONFIRMACION_AUTO_SEG") or 120)

# ---- Defensas de la aplicación (ver cofrial/seguridad.py). Main ya fija arriba cookies, HTTPS, Referer y la vista de CSRF.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 500                    # un formulario legítimo (pedido con cantidades por producto) usa menos de 100
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "cofrial"}}
# Límite de intentos. En la defensa toda la sala sale por una sola IP pública: por eso se cuenta por cuenta y no por IP (0 = sin límite por IP).
ACCESO_MAX_FALLOS_USUARIO = int(entorno("ACCESO_MAX_FALLOS_CUENTA") or 10)   # claves malas seguidas para una misma cuenta
ACCESO_MAX_FALLOS_IP = int(entorno("ACCESO_MAX_FALLOS_IP") or 0)              # claves malas desde una misma IP (cuentas distintas); 0 = no se cuenta
ACCESO_VENTANA_SEG = int(entorno("ACCESO_VENTANA_SEG") or 15 * 60)            # el bloqueo dura lo mismo que la ventana de conteo
# Barrido de rutas: «no encontrado» tolerados por IP en la ventana antes de responder 429 (un recorrido de 30 páginas en 10 minutos pasa con holgura).
ESCANEO_MAX_404 = int(entorno("ESCANEO_MAX_404") or 60)
ESCANEO_VENTANA_SEG = int(entorno("ESCANEO_VENTANA_SEG") or 10 * 60)
LIMITE_POST_POR_HORA = {"/cuenta/registro/": int(entorno("LIMITE_REGISTRO_HORA") or 10),     # envíos por IP: crean cuentas
                        "/cuenta/registro/empresa/": int(entorno("LIMITE_REGISTRO_HORA") or 10),
                        "/cuenta/recuperar/": int(entorno("LIMITE_RECUPERAR_HORA") or 10),  # mandan correos
                        "/soporte/": int(entorno("LIMITE_SOPORTE_HORA") or 20)}             # y gastan la cuota gratuita de la IA

# ---- Correo, para recuperar la clave. Con EMAIL_HOST se envía por SMTP (p. ej. Gmail con clave de aplicación, ver
# docs/credenciales-y-cuentas.md); sin él, el correo se escribe en el registro del contenedor (docker compose logs web), útil en local.
EMAIL_HOST = entorno("EMAIL_HOST", "")
EMAIL_HOST_USER = entorno("EMAIL_HOST_USER", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(entorno("EMAIL_PORT") or 587)
    EMAIL_HOST_PASSWORD = entorno("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = entorno("EMAIL_USE_TLS", "1") == "1"
    EMAIL_TIMEOUT = 10                             # un servidor de correo caído no deja colgada la página
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = entorno("EMAIL_REMITENTE") or (f"Cofrial SpA <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "Cofrial SpA <no-responder@cofrial.cl>")
PASSWORD_RESET_TIMEOUT = 60 * 60                   # el enlace para recuperar la clave dura una hora y sirve una sola vez
CANTIDAD_MAXIMA_POR_LINEA = 10000      # unidades de un producto en una línea del carrito
