from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("catalogo/", views.catalogo, name="catalogo"),
    path("cliente/", views.elegir_cliente, name="elegir_cliente"),
    path("carrito/", views.carrito, name="carrito"),
    path("carrito/agregar/", views.agregar, name="agregar"),
    path("carrito/quitar/", views.quitar, name="quitar"),
    path("carrito/confirmar/", views.confirmar, name="confirmar"),
    path("orden/<int:orden_id>/", views.orden, name="orden"),
]
