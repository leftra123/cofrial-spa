"""Tareas del administrador que no tenían pantalla: reponer stock, listar cuentas y asignar claves.
Sin HTTP: las vistas (vistas.py) piden y muestran; las reglas están aquí para poder probarlas solas."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q

from catalogo.models import AvisoStock, Producto
from clientes import cuentas
from cofrial.entradas import ENTERO_MAXIMO, entero

REPOSICION_MAXIMA = 100_000          # unidades por operación: un error de tipeo (un cero de más) no vacía ni infla el inventario
FILAS_MAXIMAS = 100                  # filas por pantalla; con más resultados se afina la búsqueda


class ErrorOperacion(ValueError):
    pass


# ───────────────────────────── stock ─────────────────────────────

def cantidad_valida(valor):
    """«25» → 25. Rechaza vacío, cero, negativos, decimales, letras y más de REPOSICION_MAXIMA."""
    try:
        n = entero(valor, maximo=REPOSICION_MAXIMA)
    except ValueError:
        raise ErrorOperacion(f"Indica una cantidad entera entre 1 y {REPOSICION_MAXIMA:,}.".replace(",", "."))
    if n < 1:
        raise ErrorOperacion(f"Indica una cantidad entera entre 1 y {REPOSICION_MAXIMA:,}.".replace(",", "."))
    return n


def productos(q=""):
    """Productos para reponer, los de menos stock primero. Busca por SKU o nombre."""
    qs = Producto.objects.select_related("categoria").order_by("stock_disponible", "nombre")
    for palabra in q.split():
        qs = qs.filter(Q(sku__icontains=palabra) | Q(nombre__icontains=palabra))
    return qs


@transaction.atomic
def reponer(producto_id, cantidad):
    """Suma `cantidad` al stock con un UPDATE ... SET stock = stock + n (F()): si una venta o cancelación ocurre al mismo tiempo,
    ninguna se pisa, que es lo que pasa al escribir un número entero desde el formulario de /admin/ (ver docs/decisiones.md).
    Devuelve (producto, avisos_que_ya_se_pueden_atender)."""
    cantidad = cantidad_valida(cantidad)
    if not Producto.objects.filter(pk=producto_id).exists():
        raise Producto.DoesNotExist
    afectadas = Producto.objects.filter(pk=producto_id, stock_disponible__lte=ENTERO_MAXIMO - cantidad).update(
        stock_disponible=F("stock_disponible") + cantidad)
    if not afectadas:
        raise ErrorOperacion("Con esa cantidad el stock superaría el máximo que acepta la base de datos.")
    producto = Producto.objects.get(pk=producto_id)
    listos = AvisoStock.objects.filter(producto=producto, atendido_en__isnull=True,
                                       cantidad_minima__gt=producto.stock_disponible - cantidad,
                                       cantidad_minima__lte=producto.stock_disponible).count()
    return producto, listos


# ───────────────────────────── cuentas ─────────────────────────────

def rol_de(u):
    """Rol visible de una cuenta con las consultas ya traídas por `cuentas_con_rol` (mismo orden que crm.servicios.rol:
    una prueba compara las dos para que no se separen)."""
    if u.is_superuser:
        return "admin"
    grupos = {g.name for g in u.groups.all()}
    if "gerencia" in grupos:
        return "gerencia"
    vendedor = getattr(u, "vendedor", None)
    if vendedor is not None and vendedor.activo:
        return "vendedor"
    if "despachadores" in grupos:
        return "despachador"
    cliente = getattr(u, "cliente", None)
    if cliente is not None:
        return "cliente-" + cliente.tipo_cliente.codigo.lower()
    return "personal" if u.is_staff else "sin rol"


def nombre_de(u):
    for rel in ("cliente", "vendedor"):
        o = getattr(u, rel, None)
        if o is not None:
            return o.nombre
    return u.first_name


def cuentas_con_rol(q=""):
    """Cuentas con su rol y nombre, ordenadas por usuario. Busca en usuario, correo, nombre, RUT y nombre de vendedor."""
    qs = (get_user_model().objects.select_related("vendedor", "cliente__tipo_cliente").prefetch_related("groups").order_by("username"))
    for palabra in q.split():
        qs = qs.filter(Q(username__icontains=palabra) | Q(email__icontains=palabra) | Q(first_name__icontains=palabra)
                       | Q(cliente__nombre__icontains=palabra) | Q(cliente__rut__icontains=palabra) | Q(vendedor__nombre__icontains=palabra))
    return qs


ROTULOS = dict(cuentas.ROLES) | {"personal": "Personal", "sin rol": "Sin rol"}
