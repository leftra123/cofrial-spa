from django.urls import path

from . import api, views
from . import escenarios

urlpatterns = [
    path("", views.panel, name="flota"),
    path("sugerencias/", views.sugerencias_despacho, name="sugerencias_despacho"),
    path("por-despachar/", views.por_despachar, name="por_despachar"),
    path("despacho-auto/", views.despacho_auto, name="despacho_auto"),
    path("despacho-auto/correr/", views.correr_despacho_auto, name="correr_despacho_auto"),
    path("despachar/", views.despachar, name="despachar"),
    path("viajes/<int:despacho_id>/cerrar/", views.cerrar_despacho, name="cerrar_despacho"),
    path("despachar/ruta/", views.ruta_sugerida, name="ruta_sugerida"),
    path("despachar/ubicar/<int:direccion_id>/", views.ubicar_direccion, name="ubicar_direccion"),
    path("camion/<str:camion_id>/diagnostico/", views.diagnostico_camion, name="diagnostico_camion"),
    path("camion/<str:camion_id>/revision/", views.revision_camion, name="revision_camion"),
    path("escenarios/estado/", escenarios.estado, name="escenarios_estado"),
    path("escenarios/interpretar/", escenarios.interpretar, name="escenarios_interpretar"),
    path("escenarios/activar/", escenarios.activar, name="escenarios_activar"),
    path("escenarios/cancelar/", escenarios.cancelar, name="escenarios_cancelar"),
]
api_urlpatterns = [
    path("flota/", api.FlotaAPI.as_view(), name="api_flota"),
    path("pedidos/", api.PedidosAPI.as_view(), name="api_pedidos"),
    path("pedidos/<int:orden_id>/seguimiento/", api.SeguimientoAPI.as_view(), name="api_seguimiento"),
    path("pedidos/<int:orden_id>/ruta/", api.RutaAPI.as_view(), name="api_ruta"),
]
