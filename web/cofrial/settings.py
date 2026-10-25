"""Configuración de Cofrial. Todo lo sensible viene del entorno (.env), nunca del código."""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def entorno(nombre, defecto=None):
    return os.environ.get(nombre, defecto)


SECRET_KEY = entorno("DJANGO_SECRET_KEY", "clave-solo-para-desarrollo")
DEBUG = entorno("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in entorno("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in entorno("DJANGO_CSRF_ORIGINS", "").split(",") if o]
CSRF_FAILURE_VIEW = "cofrial.vistas.csrf_fallo"

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
LOGIN_URL = "/cuenta/entrar/"
LOGIN_REDIRECT_URL = "/catalogo/"
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
