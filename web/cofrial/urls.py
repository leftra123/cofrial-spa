from django.contrib import admin
from django.http import JsonResponse
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

from flota.urls import api_urlpatterns as flota_api

admin.site.site_header = "Cofrial SpA: CRM y operación"
admin.site.site_title = "Cofrial"


def salud(request):
    """Responde 200 si la aplicación está viva; el balanceo y las pruebas la usan."""
    return JsonResponse({"estado": "ok"})


urlpatterns = [
    path("", TemplateView.as_view(template_name="inicio.html"), name="inicio"),
    path("catalogo/", include("catalogo.urls")),
    path("crm/", include("crm.urls")),
    path("flota/", include("flota.urls")),
    path("api/", include(flota_api)),
    path("", include("pedidos.urls")),
    path("cuenta/entrar/", auth_views.LoginView.as_view(template_name="cuenta/entrar.html"), name="entrar"),
    path("cuenta/salir/", auth_views.LogoutView.as_view(), name="salir"),
    path("salud/", salud),
    path("admin/", admin.site.urls),
]
