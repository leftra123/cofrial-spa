"""Tareas del administrador que no tenían pantalla: reponer stock, listar usuarios por tipo y asignar claves.
Sin HTTP: las vistas (vistas.py) piden y muestran; las reglas están aquí para poder probarlas solas."""
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from catalogo.models import AvisoStock, PrecioProducto, Producto
from clientes import cuentas
from cofrial.entradas import ENTERO_MAXIMO, entero
from crm import ia
from crm.models import CategoriaRequerimiento
from flota.models import Telemetria
from flota.servicios import lecturas_prescindibles
from pedidos.models import Orden

REPOSICION_MAXIMA = 100_000          # unidades por operación: un error de tipeo (un cero de más) no vacía ni infla el inventario
PODA_TOPE = 50_000                   # lecturas por clic: la web corta a los 60 s; el resto queda para otro clic o para el podador diario
PODA_LOTE = 5_000
RETENCION_POR_DEFECTO = 7
TEXTO_PRUEBA_IA = "El camión llegó con la carga tibia y rechazamos dos cajas."
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


def productos(q="", orden=("stock_disponible", "nombre")):
    """Productos, por defecto los de menos stock primero (para reponer). Busca por SKU o nombre."""
    qs = Producto.objects.select_related("categoria").order_by(*orden)
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


@transaction.atomic
def guardar_producto(form):
    """Guarda el producto y sus precios juntos. Al editar no escribe stock_disponible: una venta simultánea no se pisa."""
    producto = form.save(commit=False)
    if producto._state.adding:
        producto.stock_disponible = form.cleaned_data["stock_inicial"]
        producto.save()
    else:
        producto.save(update_fields=[c for c in form.Meta.fields if c != "sku"])
    for lista, precio in form.campos_de_precio():
        if precio is None:
            PrecioProducto.objects.filter(lista_precio=lista, producto=producto).delete()
        else:
            PrecioProducto.objects.update_or_create(lista_precio=lista, producto=producto, defaults={"precio_clp": precio})
    return producto


# ───────────────────────────── órdenes ─────────────────────────────

def ordenes(q="", estado=""):
    """Órdenes, las más nuevas primero. Busca por número, orden de compra o cliente."""
    qs = Orden.objects.select_related("estado_orden", "direccion__cliente", "despacho").order_by("-creada_en")
    if estado:
        qs = qs.filter(estado_orden__nombre=estado)
    for palabra in q.split():
        filtro = Q(numero_oc__icontains=palabra) | Q(direccion__cliente__nombre__icontains=palabra)
        if palabra.isascii() and palabra.isdigit() and len(palabra) < 10:
            filtro |= Q(orden_id=int(palabra))
        qs = qs.filter(filtro)
    return qs


def puede_avanzar(orden):
    """Solo antes de que salga el camión. En viaje la orden la mueven el simulador y el cliente: avanzarla a mano saltaría su confirmación
    y el camión perdería esa parada. «En preparación» pasa a «Despachada» únicamente si ya tiene despacho."""
    nombre = orden.estado_orden.nombre
    return nombre in ("Recibida", "Confirmada") or (nombre == "En preparación" and orden.despacho_id is not None)


def puede_cancelar(orden):
    """La misma regla de pedidos.servicios.cancelar con como="vendedor": aquí solo decide si se muestra el botón."""
    e = orden.estado_orden
    return (not e.es_final and e.orden_flujo <= 3) or e.nombre == "Entrega no concretada"


# ───────────────────────────── sistema ─────────────────────────────

def probar_ia():
    """Clasifica un mensaje de ejemplo con la IA real, como `manage.py probar_ia`. Nunca lanza: devuelve qué pasó para mostrarlo."""
    categorias = list(CategoriaRequerimiento.objects.values_list("nombre", flat=True))
    try:
        categoria, confianza = ia.clasificar("Prueba", TEXTO_PRUEBA_IA, categorias)
    except ia.ErrorIA as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "categoria": categoria, "confianza": confianza, "modelo": ia.ultimo_modelo}


def dias_de_retencion():
    try:
        dias = int(os.environ.get("RETENCION_TELEMETRIA_DIAS") or RETENCION_POR_DEFECTO)
    except ValueError:
        return RETENCION_POR_DEFECTO
    return dias if dias >= 1 else RETENCION_POR_DEFECTO


def lecturas_a_podar(dias):
    return lecturas_prescindibles(timezone.now() - timedelta(days=dias))


def podar(dias, tope=PODA_TOPE):
    """Borra por lotes hasta `tope` lecturas, para terminar dentro del límite de la web. Devuelve (borradas, las que faltan)."""
    lecturas, borradas = lecturas_a_podar(dias), 0
    while borradas < tope:
        ids = list(lecturas.order_by("pk").values_list("pk", flat=True)[:min(PODA_LOTE, tope - borradas)])
        if not ids:
            return borradas, 0
        Telemetria.objects.filter(pk__in=ids).delete()
        borradas += len(ids)
    return borradas, lecturas.count()


# ───────────────────────────── cuentas ─────────────────────────────

def rol_de(u):
    """Rol visible de una cuenta con las consultas ya traídas por `cuentas_con_rol` (mismo orden que crm.servicios.rol:
    una prueba compara las dos para que no se separen)."""
    grupos = {g.name for g in u.groups.all()}
    if u.is_superuser or "administradores" in grupos:     # misma regla que crm.servicios.rol
        return "admin"
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


def usuarios_por_tipo(q="", tipo=""):
    """Para la pantalla Usuarios: cuántas cuentas hay de cada tipo (siempre sobre todas) y las filas de la tabla, filtradas por tipo y
    por la búsqueda. Devuelve (conteos {rol: n}, otros, filas [(usuario, rol)], hay_mas). `tipo` vacío = todos."""
    todos = list(cuentas_con_rol())
    roles = {u.pk: rol_de(u) for u in todos}
    conteos = {r: 0 for r, _ in cuentas.ROLES}
    otros = 0
    for r in roles.values():
        if r in conteos:
            conteos[r] += 1
        else:
            otros += 1
    pks = set(cuentas_con_rol(q).values_list("pk", flat=True)) if q else None
    filas = [(u, roles[u.pk]) for u in todos if (not tipo or roles[u.pk] == tipo) and (pks is None or u.pk in pks)]
    return conteos, otros, filas[:FILAS_MAXIMAS], len(filas) > FILAS_MAXIMAS


@transaction.atomic
def cambiar_activa(objetivo, activa, quien):
    """Activa o desactiva una cuenta. Una solicitud de empresa se reconoce por ser B2B, sin vendedor y con cuenta inactiva
    (crm.servicios.solicitudes_empresa): este botón no debe crear ni saltarse esa cola. Lanza ErrorOperacion con el motivo."""
    cliente = getattr(objetivo, "cliente", None)
    vendedor = getattr(objetivo, "vendedor", None)
    b2b_sin_vendedor = cliente is not None and cliente.tipo_cliente.codigo == "B2B" and cliente.vendedor_id is None
    if activa:
        if b2b_sin_vendedor and not objetivo.is_active:
            raise ErrorOperacion(f"{cliente.nombre} es una solicitud pendiente: se aprueba en CRM, Solicitudes, donde se le asigna vendedor.")
    else:
        if objetivo.pk == quien.pk:
            raise ErrorOperacion("No puedes desactivar tu propia cuenta.")
        admin_empresa = objetivo.is_superuser or objetivo.groups.filter(name="administradores").exists()
        otros = get_user_model().objects.filter(is_active=True).filter(Q(is_superuser=True) | Q(groups__name="administradores")).exclude(pk=objetivo.pk)
        if admin_empresa and not otros.exists():
            raise ErrorOperacion("Es el último administrador activo.")
        if b2b_sin_vendedor:
            raise ErrorOperacion(f"{cliente.nombre} no tiene vendedor: aparecería como solicitud y podría borrarse al rechazarla. Asígnale un vendedor primero, en Datos, Clientes.")
        if vendedor is not None and (vendedor.cliente_set.exists() or vendedor.prospecto_set.filter(etapa__es_final=False).exists()):
            raise ErrorOperacion(f"{vendedor.nombre} tiene clientes o prospectos abiertos: reasigna su cartera primero, en Datos.")
    objetivo.is_active = activa
    objetivo.save(update_fields=["is_active"])
    if vendedor is not None:
        vendedor.activo = activa
        vendedor.save(update_fields=["activo"])
    return objetivo


def clientes_sin_cuenta():
    """Clientes que no pueden ingresar al portal (p. ej. los que nacen al ganar un prospecto), con el vendedor y el tipo."""
    from clientes.models import Cliente
    return Cliente.objects.filter(usuario__isnull=True).select_related("tipo_cliente", "vendedor").order_by("nombre")
