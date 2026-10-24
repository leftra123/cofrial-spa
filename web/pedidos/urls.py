from django.urls import path

from catalogo import views as catalogo_views

from . import views

urlpatterns = [
    path("carrito/", views.ver_carrito, name="carrito"),
    path("carrito/agregar/", views.agregar, name="carrito_agregar"),
    path("carrito/actualizar/", views.actualizar, name="carrito_actualizar"),
    path("carrito/repetir/", views.repetir, name="carrito_repetir"),
    path("carrito/confirmar/", views.confirmar, name="carrito_confirmar"),
    path("avisos/", catalogo_views.mis_avisos, name="avisos"),
    path("avisos/pedir/", catalogo_views.pedir_aviso, name="aviso_pedir"),
    path("avisos/<int:aviso_id>/quitar/", catalogo_views.quitar_aviso, name="aviso_quitar"),
    path("seguimiento/", views.seguimiento, name="seguimiento"),
    path("pedidos/", views.mis_pedidos, name="pedidos"),
    path("soporte/", views.soporte, name="soporte"),
    path("pedidos/<int:orden_id>/", views.detalle, name="orden"),
    path("pedidos/<int:orden_id>/cancelar/", views.cancelar, name="orden_cancelar"),
]
