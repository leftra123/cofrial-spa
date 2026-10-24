"""Avisos de stock: el cliente pide que se le avise cuando haya al menos X unidades de un producto."""
from django.db.models import Count, F, Sum
from django.utils import timezone

from .models import AvisoStock, Producto


class ErrorAviso(Exception):
    pass


def pedir(cliente, producto_id, cantidad):
    """Crea o actualiza el aviso pendiente del cliente para ese producto."""
    try:
        producto = Producto.objects.get(pk=producto_id, activo=True)
    except Producto.DoesNotExist:
        raise ErrorAviso("El producto no existe o ya no está disponible.")
    if cantidad < 1:
        raise ErrorAviso("Indica cuántas unidades necesitas (al menos 1).")
    if producto.stock_disponible >= cantidad:
        raise ErrorAviso(f"Ya hay {producto.stock_disponible} unidades disponibles de {producto.nombre}; puedes agregarlas al carrito.")
    aviso, _ = AvisoStock.objects.update_or_create(cliente=cliente, producto=producto, atendido_en=None,
                                                   defaults={"cantidad_minima": cantidad})
    return aviso


def pendientes(cliente):
    return AvisoStock.objects.filter(cliente=cliente, atendido_en__isnull=True).select_related("producto").order_by("-creado_en")


def minimos_pendientes(cliente):
    """{producto_id: cantidad_minima} de los avisos pendientes del cliente (para marcar las tarjetas del catálogo)."""
    return dict(pendientes(cliente).values_list("producto_id", "cantidad_minima"))


def cuantos_disponibles(cliente):
    """Avisos pendientes cuyo stock ya alcanzó la cantidad pedida: lo que se muestra como novedad en la barra."""
    return AvisoStock.objects.filter(cliente=cliente, atendido_en__isnull=True,
                                     producto__stock_disponible__gte=F("cantidad_minima")).count()


def marcar_atendidos(cliente, producto_id):
    AvisoStock.objects.filter(cliente=cliente, producto_id=producto_id, atendido_en__isnull=True).update(atendido_en=timezone.now())


def demanda_en_espera():
    """Para el CRM: por producto, cuántos clientes esperan, cuántas unidades piden en total y si ya hay stock para atenderlos."""
    filas = (AvisoStock.objects.filter(atendido_en__isnull=True).values("producto_id", "producto__nombre", "producto__sku", "producto__stock_disponible")
             .annotate(n_clientes=Count("aviso_id"), pedido=Sum("cantidad_minima")))
    return sorted(filas, key=lambda f: -f["pedido"])
