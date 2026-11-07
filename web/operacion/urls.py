from django.urls import path

from . import datos, vistas

urlpatterns = [
    path("", vistas.indice, name="operacion"),
    path("stock/", vistas.stock, name="operacion_stock"),
    path("stock/<int:pk>/sumar/", vistas.stock_sumar, name="operacion_stock_sumar"),
    path("cuentas/", vistas.cuentas_lista, name="operacion_cuentas"),
    path("cuentas/nueva/", vistas.cuenta_nueva, name="operacion_cuenta_nueva"),
    path("clientes/<int:pk>/cuenta/", vistas.cliente_cuenta, name="operacion_cliente_cuenta"),
    path("cuentas/<int:pk>/clave/", vistas.cuenta_clave, name="operacion_cuenta_clave"),
    path("cuentas/<int:pk>/activa/", vistas.cuenta_activa, name="operacion_cuenta_activa"),
    path("productos/", vistas.productos, name="operacion_productos"),
    path("productos/nuevo/", vistas.producto_nuevo, name="operacion_producto_nuevo"),
    path("productos/<int:pk>/", vistas.producto_editar, name="operacion_producto"),
    path("ordenes/", vistas.ordenes, name="operacion_ordenes"),
    path("ordenes/<int:pk>/avanzar/", vistas.orden_avanzar, name="operacion_orden_avanzar"),
    path("ordenes/<int:pk>/cancelar/", vistas.orden_cancelar, name="operacion_orden_cancelar"),
    path("sistema/", vistas.sistema, name="operacion_sistema"),
    path("sistema/ia/", vistas.sistema_ia, name="operacion_sistema_ia"),
    path("sistema/podar/", vistas.sistema_podar, name="operacion_sistema_podar"),
    path("datos/", datos.indice, name="operacion_datos"),
    path("datos/<slug:slug>/", datos.lista, name="operacion_tabla"),
    path("datos/<slug:slug>/nuevo/", datos.nuevo, name="operacion_tabla_nuevo"),
    path("datos/<slug:slug>/<str:pk>/", datos.fila, name="operacion_fila"),
    path("datos/<slug:slug>/<str:pk>/borrar/", datos.borrar, name="operacion_fila_borrar"),
]
