from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("catalogo/", views.catalogo, name="catalogo"),
    path("entrar/", views.entrar, name="entrar"),
    path("salir/", views.salir, name="salir"),
    path("registro/", views.registro, name="registro"),
    path("pedidos/", views.pedidos, name="pedidos"),
    path("carrito/", views.carrito, name="carrito"),
    path("carrito/agregar/", views.agregar, name="agregar"),
    path("carrito/quitar/", views.quitar, name="quitar"),
    path("carrito/confirmar/", views.confirmar, name="confirmar"),
    path("orden/<int:orden_id>/", views.orden, name="orden"),
]
