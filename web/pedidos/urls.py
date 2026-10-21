from django.urls import path

from . import views

urlpatterns = [
    path("carrito/", views.ver_carrito, name="carrito"),
    path("carrito/agregar/", views.agregar, name="carrito_agregar"),
    path("carrito/actualizar/", views.actualizar, name="carrito_actualizar"),
    path("carrito/repetir/", views.repetir, name="carrito_repetir"),
    path("carrito/confirmar/", views.confirmar, name="carrito_confirmar"),
    path("pedidos/", views.mis_pedidos, name="pedidos"),
    path("pedidos/<int:orden_id>/", views.detalle, name="orden"),
    path("pedidos/<int:orden_id>/cancelar/", views.cancelar, name="orden_cancelar"),
]
