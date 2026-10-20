"""Reglas del carrito y de la generación de órdenes (informe/04c, RN-01 a RN-06)."""
from django.db import transaction
from django.db.models import F

from .models import Carrito, CarritoItem, Cliente, Direccion, EstadoOrden, Orden, OrdenItem, PrecioProducto, Producto


class ErrorCompra(Exception):
    """La orden no se puede generar; el mensaje se muestra al cliente. No se guarda nada."""

    def __init__(self, mensajes):
        self.mensajes = [mensajes] if isinstance(mensajes, str) else list(mensajes)
        super().__init__("; ".join(self.mensajes))


def precios_del_cliente(cliente):
    """RN-01: precios de la lista del tipo de cliente. {producto_id: precio_clp}."""
    return dict(
        PrecioProducto.objects.filter(lista_precio_id=cliente.tipo_cliente.lista_precio_id)
        .values_list("producto_id", "precio_clp")
    )


def carrito_abierto(cliente, crear=False):
    """RN-03: un solo carrito abierto por cliente. El bloqueo de la fila del cliente evita crear dos a la vez."""
    with transaction.atomic():
        Cliente.objects.select_for_update().get(pk=cliente.pk)
        carrito = Carrito.objects.filter(cliente=cliente, estado="abierto").first()
        if carrito is None and crear:
            carrito = Carrito.objects.create(cliente=cliente, estado="abierto")
        return carrito


def agregar(cliente, producto_id, cantidad):
    if cantidad < 1:
        raise ErrorCompra("La cantidad debe ser al menos 1.")
    producto = Producto.objects.filter(pk=producto_id, activo=True).first()
    if producto is None:
        raise ErrorCompra("El producto no existe o no está disponible.")
    if producto.producto_id not in precios_del_cliente(cliente):
        raise ErrorCompra("El producto no tiene precio en tu lista.")
    with transaction.atomic():
        carrito = carrito_abierto(cliente, crear=True)
        actualizadas = CarritoItem.objects.filter(carrito=carrito, producto=producto).update(cantidad=F("cantidad") + cantidad)
        if not actualizadas:
            CarritoItem.objects.create(carrito=carrito, producto=producto, cantidad=cantidad)


def quitar(cliente, producto_id):
    carrito = carrito_abierto(cliente)
    if carrito:
        CarritoItem.objects.filter(carrito=carrito, producto_id=producto_id).delete()


def detalle(cliente):
    """Líneas del carrito con precio y subtotal, y el total."""
    carrito = carrito_abierto(cliente)
    if carrito is None:
        return [], 0
    precios = precios_del_cliente(cliente)
    lineas = []
    for it in CarritoItem.objects.filter(carrito=carrito).select_related("producto").order_by("producto__nombre"):
        precio = precios.get(it.producto_id, 0)
        lineas.append({"producto": it.producto, "cantidad": it.cantidad, "precio": precio, "subtotal": precio * it.cantidad,
                       "sin_stock": it.cantidad > it.producto.stock_disponible})
    return lineas, sum(l["subtotal"] for l in lineas)


def confirmar(cliente, direccion_id, numero_oc=""):
    """Genera la orden desde el carrito abierto.

    RN-02: validación y descuento de stock en una misma transacción; los productos se bloquean
    (SELECT ... FOR UPDATE, siempre en orden de id para evitar bloqueos cruzados) para que dos
    compras simultáneas no vendan la misma unidad. Si algo falla, no se guarda nada.
    """
    numero_oc = (numero_oc or "").strip()
    with transaction.atomic():
        carrito = carrito_abierto(cliente)
        items = list(CarritoItem.objects.filter(carrito=carrito)) if carrito else []
        if not items:
            raise ErrorCompra("Tu carrito está vacío.")
        direccion = Direccion.objects.filter(pk=direccion_id, cliente=cliente).first()  # RN-04
        if direccion is None:
            raise ErrorCompra("Elige una dirección de entrega tuya.")
        if cliente.tipo_cliente.codigo == "B2B" and not numero_oc:  # RN-05
            raise ErrorCompra("Los clientes institucionales deben indicar su número de orden de compra.")

        ids = sorted(i.producto_id for i in items)
        bloqueados = {p.producto_id: p for p in Producto.objects.select_for_update().filter(pk__in=ids).order_by("producto_id")}
        precios = precios_del_cliente(cliente)

        errores = []
        for it in items:
            p = bloqueados[it.producto_id]
            if not p.activo:
                errores.append(f"«{p.nombre}» ya no está disponible.")
            elif it.producto_id not in precios:
                errores.append(f"«{p.nombre}» no tiene precio en tu lista.")
            elif p.stock_disponible < it.cantidad:
                errores.append(f"«{p.nombre}»: pediste {it.cantidad} y quedan {p.stock_disponible}.")
        if errores:  # RN-02: sin stock suficiente en alguna línea no se genera la orden
            raise ErrorCompra(errores)

        orden = Orden.objects.create(
            direccion=direccion,
            estado_orden=EstadoOrden.objects.get(nombre="Recibida"),
            numero_oc=numero_oc or None,
        )
        for it in items:
            OrdenItem.objects.create(orden=orden, producto_id=it.producto_id, cantidad=it.cantidad,
                                     precio_unitario_clp=precios[it.producto_id])  # RN-06: precio congelado
            Producto.objects.filter(pk=it.producto_id).update(stock_disponible=F("stock_disponible") - it.cantidad)
        Carrito.objects.filter(pk=carrito.pk).update(estado="convertido")  # RN-03
        return orden
