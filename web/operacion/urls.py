from django.urls import path

from . import vistas

urlpatterns = [
    path("", vistas.indice, name="operacion"),
    path("stock/", vistas.stock, name="operacion_stock"),
    path("stock/<int:pk>/sumar/", vistas.stock_sumar, name="operacion_stock_sumar"),
    path("cuentas/", vistas.cuentas_lista, name="operacion_cuentas"),
    path("cuentas/nueva/", vistas.cuenta_nueva, name="operacion_cuenta_nueva"),
    path("cuentas/<int:pk>/clave/", vistas.cuenta_clave, name="operacion_cuenta_clave"),
]
