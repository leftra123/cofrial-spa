from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.contrib.auth import views as auth_views
from django.urls import include, path
from . import bi, legal, vistas
from .vistas import api_avisos_equipo
from catalogo import views as catalogo_views
from flota import demo as flota_demo
from salud import vistas as salud_vista

from flota.urls import api_urlpatterns as flota_api

admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser      # el equipo (vendedor, gerencia, despacho) trabaja en el CRM y la flota; el admin de Django es del administrador
admin.site.site_header = "Cofrial SpA: CRM y operación"
admin.site.site_title = "Cofrial"


def salud_bd(request):
    """Además de estar viva, la aplicación alcanza la base de datos (503 si no). Para ver la caída controlada sin abrir una pantalla.
    Es también el chequeo del balanceador (/health): una web que perdió la base sale de rotación. Si la base cae para las dos web a la vez
    (conmutación de RDS), el ALB no tiene a quién preferir y sigue repartiendo entre ambas, que responden el 503 propio hasta que vuelve."""
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
    path("operacion/", include("operacion.urls")),
    path("torre/", include("torre.urls")),
    path("bi/", bi.proxy, name="bi"),
    path("bi/<path:ruta>", bi.proxy),
    path("demo/", flota_demo.pagina, name="demo"),
    path("demo/pulso/", flota_demo.pulso, name="demo_pulso"),
    path("demo/apagar/", flota_demo.apagar, name="demo_apagar"),
    path("demo/limpiar/", flota_demo.limpiar, name="demo_limpiar"),
    path("demo/tiempo/", flota_demo.cambiar_tiempo, name="demo_tiempo"),
    path("demo/pedido-cercano/", flota_demo.pedido_cercano, name="demo_pedido_cercano"),
    path("demo/preparar/", flota_demo.preparar_demo, name="demo_preparar"),
    path("api/asistente/", catalogo_views.api_asistente, name="api_asistente"),
    path("api/avisos-equipo/", api_avisos_equipo, name="api_avisos_equipo"),
    path("api/productos/", catalogo_views.api_productos, name="api_productos"),
    path("api/productos/<str:sku>/", catalogo_views.api_productos, name="api_producto"),
    path("api/", include(flota_api)),
    path("", include("pedidos.urls")),
    path("cuenta/entrar/", vistas.Entrar.as_view(), name="entrar"),
    path("cuenta/registro/", vistas.registro, name="registro"),
    path("cuenta/registro/empresa/", vistas.registro_empresa, name="registro_empresa"),
    path("cuenta/recuperar/", vistas.Recuperar.as_view(), name="recuperar"),
    path("cuenta/recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(template_name="cuenta/recuperar_enviado.html"), name="recuperar_enviado"),
    path("cuenta/recuperar/<str:uidb64>/<str:token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="cuenta/recuperar_nueva.html", success_url="/cuenta/recuperar/listo/"), name="recuperar_nueva"),
    path("cuenta/recuperar/listo/", auth_views.PasswordResetCompleteView.as_view(template_name="cuenta/recuperar_listo.html"), name="recuperar_listo"),
    path("cuenta/clave/", auth_views.PasswordChangeView.as_view(
        template_name="cuenta/clave.html", success_url="/cuenta/clave/hecho/"), name="cambiar_clave"),
    path("cuenta/clave/hecho/", auth_views.PasswordChangeDoneView.as_view(template_name="cuenta/clave_hecha.html"), name="clave_hecha"),
    path("cuenta/salir/", auth_views.LogoutView.as_view(), name="salir"),
    path("cuenta/mis-datos/", legal.mis_datos, name="mis_datos"),
    path("cuenta/mis-datos/descargar/", legal.descargar_datos, name="mis_datos_descargar"),
    path("cuenta/mis-datos/eliminar/", legal.eliminar_cuenta, name="mis_datos_eliminar"),
    path("cuenta/mis-datos/solicitar/", legal.solicitar, name="mis_datos_solicitar"),
    path("legal/<slug:nombre>/", legal.pagina, name="legal"),
    path("salud/", salud_vista.pagina),
    path("salud/bd/", salud_bd),
    path("health", salud_bd),            # nombre convencional para el chequeo del ALB; sin barra final, tal como lo pide el balanceador
    path(settings.ADMIN_URL, admin.site.urls),
]
