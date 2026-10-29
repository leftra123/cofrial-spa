from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.contrib.auth import views as auth_views
from django.urls import include, path
from . import bi, vistas
from catalogo import views as catalogo_views
from flota import demo as flota_demo

from flota.urls import api_urlpatterns as flota_api

admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser      # el equipo (vendedor, gerencia, despacho) trabaja en el CRM y la flota; el admin de Django es del administrador
admin.site.site_header = "Cofrial SpA: CRM y operación"
admin.site.site_title = "Cofrial"


def salud(request):
    """Responde 200 si la aplicación está viva; el balanceo y las pruebas la usan."""
    return JsonResponse({"estado": "ok"})


def salud_bd(request):
    """Además de estar viva, la aplicación alcanza la base de datos (503 si no). Para ver la caída controlada sin abrir una pantalla."""
    from django.db import DatabaseError
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"estado": "sin_base"}, status=503)
    return JsonResponse({"estado": "ok"})


handler400 = "cofrial.seguridad.error_400"
handler500 = "cofrial.seguridad.error_500"

urlpatterns = [
    path("", vistas.inicio, name="inicio"),
    path("portada/", lambda request: vistas.inicio(request, portada=True), name="portada"),
    path("catalogo/", include("catalogo.urls")),
    path("crm/", include("crm.urls")),
    path("flota/", include("flota.urls")),
    path("bi/", bi.proxy, name="bi"),
    path("bi/<path:ruta>", bi.proxy),
    path("demo/", flota_demo.pagina, name="demo"),
    path("demo/pulso/", flota_demo.pulso, name="demo_pulso"),
    path("demo/apagar/", flota_demo.apagar, name="demo_apagar"),
    path("demo/limpiar/", flota_demo.limpiar, name="demo_limpiar"),
    path("api/asistente/", catalogo_views.api_asistente, name="api_asistente"),
    path("api/productos/", catalogo_views.api_productos, name="api_productos"),
    path("api/productos/<str:sku>/", catalogo_views.api_productos, name="api_producto"),
    path("api/", include(flota_api)),
    path("", include("pedidos.urls")),
    path("cuenta/entrar/", vistas.Entrar.as_view(), name="entrar"),
    path("cuenta/registro/", vistas.registro, name="registro"),
    path("cuenta/clave/", auth_views.PasswordChangeView.as_view(
        template_name="cuenta/clave.html", success_url="/cuenta/clave/hecho/"), name="cambiar_clave"),
    path("cuenta/clave/hecho/", auth_views.PasswordChangeDoneView.as_view(template_name="cuenta/clave_hecha.html"), name="clave_hecha"),
    path("cuenta/salir/", auth_views.LogoutView.as_view(), name="salir"),
    path("salud/", salud),
    path("salud/bd/", salud_bd),
    path(settings.ADMIN_URL, admin.site.urls),
]
