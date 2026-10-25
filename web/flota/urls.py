from django.urls import path

from . import api, views

urlpatterns = [
    path("", views.panel, name="flota"),
    path("despachar/", views.despachar, name="despachar"),
    path("viajes/<int:despacho_id>/cerrar/", views.cerrar_despacho, name="cerrar_despacho"),
    path("despachar/ruta/", views.ruta_sugerida, name="ruta_sugerida"),
    path("despachar/ubicar/<int:direccion_id>/", views.ubicar_direccion, name="ubicar_direccion"),
]
api_urlpatterns = [
    path("flota/", api.FlotaAPI.as_view(), name="api_flota"),
    path("pedidos/", api.PedidosAPI.as_view(), name="api_pedidos"),
    path("pedidos/<int:orden_id>/seguimiento/", api.SeguimientoAPI.as_view(), name="api_seguimiento"),
    path("pedidos/<int:orden_id>/ruta/", api.RutaAPI.as_view(), name="api_ruta"),
]
