from django.contrib import admin
from django.http import JsonResponse
from django.contrib.auth import views as auth_views
from django.urls import include, path
from . import vistas
from catalogo import views as catalogo_views

from flota.urls import api_urlpatterns as flota_api

admin.site.site_header = "Cofrial SpA: CRM y operación"
admin.site.site_title = "Cofrial"


def salud(request):
    """Responde 200 si la aplicación está viva; el balanceo y las pruebas la usan."""
    return JsonResponse({"estado": "ok"})


urlpatterns = [
    path("", vistas.inicio, name="inicio"),
    path("catalogo/", include("catalogo.urls")),
    path("crm/", include("crm.urls")),
    path("flota/", include("flota.urls")),
    path("api/productos/", catalogo_views.api_productos, name="api_productos"),
    path("api/productos/<str:sku>/", catalogo_views.api_productos, name="api_producto"),
    path("api/", include(flota_api)),
    path("", include("pedidos.urls")),
    path("cuenta/entrar/", vistas.Entrar.as_view(), name="entrar"),
    path("cuenta/registro/", vistas.registro, name="registro"),
    path("cuenta/salir/", auth_views.LogoutView.as_view(), name="salir"),
    path("salud/", salud),
    path("admin/", admin.site.urls),
]
