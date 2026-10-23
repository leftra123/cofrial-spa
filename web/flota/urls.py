from django.urls import path

from . import api, views

urlpatterns = [path("", views.panel, name="flota")]
api_urlpatterns = [
    path("flota/", api.FlotaAPI.as_view(), name="api_flota"),
    path("pedidos/", api.PedidosAPI.as_view(), name="api_pedidos"),
    path("pedidos/<int:orden_id>/seguimiento/", api.SeguimientoAPI.as_view(), name="api_seguimiento"),
]
