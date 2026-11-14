"""Pedido de prueba cercano: crea, para la demostración, un pedido «En preparación» de un cliente de Temuco o Padre Las Casas, listo para armar su despacho.
Los clientes de Angol, Victoria o Pucón hacen viajes de horas; con estos el camión llega en minutos y la prueba se puede repetir a gusto.
Usa los mismos servicios que el carrito (stock, precios, estado inicial): no inventa nada. No toca el carrito de un cliente que ya tiene cosas en él."""
from catalogo.models import Producto
from clientes.models import Direccion
from pedidos import servicios as s

COMUNAS_CERCANAS = ("Temuco", "Padre Las Casas")
RANGOS = ("Refrigerado", "Congelado")
ETAPA_EN_PREPARACION = 3          # orden_flujo de «En preparación»


class ErrorPedidoDemo(Exception):
    """No se pudo armar el pedido; el mensaje es para mostrarlo."""


def crear(rango):
    if rango not in RANGOS:
        raise ErrorPedidoDemo("Elige refrigerado o congelado.")
    productos = list(Producto.objects.filter(activo=True, stock_disponible__gte=3, categoria__rango_temperatura__nombre=rango).order_by("stock_disponible", "nombre"))
    if not productos:
        raise ErrorPedidoDemo(f"No hay productos {rango.lower()}s con stock para armar el pedido.")
    direcciones = (Direccion.objects.filter(comuna__nombre__in=COMUNAS_CERCANAS, lat__isnull=False, long__isnull=False, cliente__usuario__is_active=True)
                   .select_related("cliente__tipo_cliente", "comuna").order_by("comuna__nombre", "cliente__nombre", "pk"))
    for d in direcciones:
        cliente = d.cliente
        if s.lineas_en_carrito(cliente):
            continue
        for p in productos:
            try:
                s.agregar(cliente, p.pk, 1)
                orden = s.generar_ordenes(cliente, d.pk)[0]
            except s.ErrorDeNegocio:
                s.fijar_cantidad(cliente, p.pk, 0)          # no deja a medias el carrito de nadie
                continue
            while orden.estado_orden.orden_flujo < ETAPA_EN_PREPARACION:
                orden = s.avanzar(orden)
            return {"orden": orden.pk, "cliente": cliente.nombre, "comuna": d.comuna.nombre, "rango": rango, "producto": p.nombre}
    raise ErrorPedidoDemo("Ningún cliente cercano está libre para un pedido de prueba (todos tienen algo en el carrito).")
