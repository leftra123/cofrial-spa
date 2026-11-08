from django.urls import path

from catalogo import views as catalogo_views

from . import views

urlpatterns = [
    path("carrito/", views.ver_carrito, name="carrito"),
    path("carrito/agregar/", views.agregar, name="carrito_agregar"),
    path("carrito/actualizar/", views.actualizar, name="carrito_actualizar"),
    path("carrito/repetir/", views.repetir, name="carrito_repetir"),
    path("carrito/confirmar/", views.confirmar, name="carrito_confirmar"),
    path("carrito/mp/pagar/", views.mp_pagar_brick, name="mp_pagar_brick"),
    path("carrito/mp/webhook/", views.mp_webhook, name="mp_webhook"),
    path("carrito/mp/vuelta/exito/", views.mp_vuelta_exito, name="mp_vuelta_exito"),
    path("carrito/mp/vuelta/fallo/", views.mp_vuelta_fallo, name="mp_vuelta_fallo"),
    path("carrito/mp/vuelta/pendiente/", views.mp_vuelta_pendiente, name="mp_vuelta_pendiente"),
    path("api/avisos/", views.api_avisos, name="api_avisos"),
    path("avisos/", catalogo_views.mis_avisos, name="avisos"),
    path("avisos/pedir/", catalogo_views.pedir_aviso, name="aviso_pedir"),
    path("avisos/<int:aviso_id>/quitar/", catalogo_views.quitar_aviso, name="aviso_quitar"),
    path("seguimiento/", views.seguimiento, name="seguimiento"),
    path("pedidos/", views.mis_pedidos, name="pedidos"),
    path("soporte/", views.soporte, name="soporte"),
    path("pedidos/<int:orden_id>/", views.detalle, name="orden"),
    path("pedidos/<int:orden_id>/documentos/<int:documento_id>/", views.comprobante, name="comprobante"),
    path("pedidos/<int:orden_id>/oc/", views.registrar_oc, name="orden_oc"),
    path("pedidos/<int:orden_id>/entrega/", views.entrega, name="orden_entrega"),
    path("pedidos/<int:orden_id>/cancelar/", views.cancelar, name="orden_cancelar"),
]
