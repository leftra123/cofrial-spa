"""Configuración de Cofrial. Todo lo sensible viene del entorno (.env), nunca del código."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def entorno(nombre, defecto=None):
    return os.environ.get(nombre, defecto)


SECRET_KEY = entorno("DJANGO_SECRET_KEY", "clave-solo-para-desarrollo")
DEBUG = entorno("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in entorno("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in entorno("DJANGO_CSRF_ORIGINS", "").split(",") if o]

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
    "OPTIONS": {"context_processors": [
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
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
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
