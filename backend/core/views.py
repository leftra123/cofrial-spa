from collections import defaultdict

from django.contrib import messages
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import cuentas, servicios
from .cuentas import login_requerido
from .models import Comuna, Direccion, EstadoOrden, Orden, OrdenItem, PrecioProducto, Producto

# Perfil de compra -> lista de precios (tabla lista_precio). Solo para quien mira sin cuenta.
PERFILES = {"b2b": "Institucional B2B", "b2c": "Público B2C"}


def health(request):
    """Comprueba que la app responde y que la BD (local o RDS) es alcanzable."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        db = "ok"
    except Exception as exc:
        db = f"error: {exc.__class__.__name__}"
    return JsonResponse({"app": "ok", "db": db}, status=200 if db == "ok" else 503)


ESCALA_MIN, ESCALA_MAX = -30, 10  # °C que cubre la escala de temperatura dibujada en el catálogo


def _escala(rango):
    """Posición (en %) del rango de conservación sobre la escala de -30 a +10 °C."""
    ancho = ESCALA_MAX - ESCALA_MIN
    izq = max(0.0, (float(rango.temp_min_c) - ESCALA_MIN) / ancho * 100)
    der = min(100.0, (float(rango.temp_max_c) - ESCALA_MIN) / ancho * 100)
    return {"izq": round(izq, 1), "ancho": round(max(der - izq, 2.0), 1), "cero": round(-ESCALA_MIN / ancho * 100, 1),
            "congelado": float(rango.temp_max_c) < 0}


def catalogo(request):
    """Catálogo de refrigerados y congelados.

    Con sesión iniciada se usa la lista de precios del cliente (RN-01) y se puede comprar;
    sin sesión, ?perfil=b2b|b2c deja mirar las dos listas.
    """
    cliente = cuentas.cliente_de_sesion(request)
    if cliente:
        perfil = cliente.tipo_cliente.codigo.lower()
        precios = servicios.precios_del_cliente(cliente)
        lista = cliente.tipo_cliente.lista_precio.nombre
    else:
        perfil = request.GET.get("perfil", "b2c").lower()
        if perfil not in PERFILES:
            perfil = "b2c"
        lista = PERFILES[perfil]
        precios = dict(PrecioProducto.objects.filter(lista_precio__nombre=lista).values_list("producto_id", "precio_clp"))
    productos = Producto.objects.filter(activo=True).select_related("categoria__rango_temperatura").order_by("categoria__nombre", "nombre")
    grupos = {}
    for p in productos:
        rango = p.categoria.rango_temperatura
        grupo = grupos.setdefault(p.categoria.nombre, {"nombre": p.categoria.nombre, "rango": rango, "items": [], **_escala(rango)})
        grupo["items"].append({"p": p, "precio": precios.get(p.producto_id)})
    return render(request, "core/catalogo.html", {"grupos": list(grupos.values()), "perfil": perfil, "lista": lista, "cliente": cliente})


# ---- cuentas ----------------------------------------------------------------------------

def entrar(request):
    if cuentas.cliente_de_sesion(request):
        return redirect("catalogo")
    siguiente = request.POST.get("next") or request.GET.get("next") or ""
    if request.method == "POST":
        try:
            cuentas.iniciar_sesion(request, request.POST.get("email"), request.POST.get("password"))
            return redirect(cuentas.destino_seguro(request, siguiente))
        except cuentas.ErrorCuenta as exc:
            messages.error(request, str(exc))
    return render(request, "core/entrar.html", {"siguiente": siguiente, "email": request.POST.get("email", "")})


@require_POST
def salir(request):
    cuentas.cerrar_sesion(request)
    return redirect("catalogo")


def registro(request):
    if cuentas.cliente_de_sesion(request):
        return redirect("catalogo")
    datos = request.POST if request.method == "POST" else {}
    if request.method == "POST":
        try:
            usuario = cuentas.registrar_b2c(datos.get("nombre"), datos.get("rut"), datos.get("email"), datos.get("password"),
                                            datos.get("calle_numero"), datos.get("comuna_id"))
            cuentas.iniciar_sesion(request, usuario.email, datos.get("password"))
            messages.success(request, "Tu cuenta está lista. Ya puedes comprar.")
            return redirect("catalogo")
        except cuentas.ErrorCuenta as exc:
            messages.error(request, str(exc))
    return render(request, "core/registro.html", {"comunas": Comuna.objects.order_by("nombre"), "d": datos})


# ---- compra -----------------------------------------------------------------------------

@require_POST
def agregar(request):
    cliente = cuentas.cliente_de_sesion(request)
    if cliente is None:
        messages.error(request, "Inicia sesión para agregar productos al carrito.")
        return redirect(f"{reverse('entrar')}?next={reverse('catalogo')}")
    try:
        servicios.agregar(cliente, int(request.POST.get("producto_id", 0)), int(request.POST.get("cantidad", 1)))
        messages.success(request, "Producto agregado al carrito.")
    except (servicios.ErrorCompra, ValueError) as exc:
        messages.error(request, str(exc) if isinstance(exc, servicios.ErrorCompra) else "Cantidad no válida.")
    return redirect("catalogo")


@require_POST
@login_requerido
def quitar(request):
    servicios.quitar(cuentas.cliente_de_sesion(request), int(request.POST.get("producto_id", 0)))
    return redirect("carrito")


@login_requerido
def carrito(request):
    cliente = cuentas.cliente_de_sesion(request)
    lineas, total = servicios.detalle(cliente)
    direcciones = Direccion.objects.filter(cliente=cliente).select_related("comuna").order_by("-es_principal", "direccion_id")
    return render(request, "core/carrito.html", {
        "lineas": lineas, "total": total, "direcciones": direcciones, "es_b2b": cliente.tipo_cliente.codigo == "B2B",
        "hay_sin_stock": any(l["sin_stock"] for l in lineas),
    })


@require_POST
@login_requerido
def confirmar(request):
    cliente = cuentas.cliente_de_sesion(request)
    try:
        orden = servicios.confirmar(cliente, request.POST.get("direccion_id"), request.POST.get("numero_oc", ""))
    except servicios.ErrorCompra as exc:
        for m in exc.mensajes:
            messages.error(request, m)
        return redirect("carrito")
    return redirect("orden", orden_id=orden.orden_id)


@login_requerido
def orden(request, orden_id):
    cliente = cuentas.cliente_de_sesion(request)
    o = Orden.objects.select_related("estado_orden", "direccion__comuna").filter(pk=orden_id, direccion__cliente=cliente).first()
    if o is None:
        raise Http404("Orden no encontrada")
    lineas = [{"producto": i.producto, "cantidad": i.cantidad, "precio": i.precio_unitario_clp, "subtotal": i.cantidad * i.precio_unitario_clp}
              for i in OrdenItem.objects.filter(orden=o).select_related("producto").order_by("producto__nombre")]
    estados = [e for e in EstadoOrden.objects.order_by("orden_flujo") if e.nombre != "Cancelada"]
    return render(request, "core/orden.html", {
        "orden": o, "lineas": lineas, "total": sum(l["subtotal"] for l in lineas),
        "estados": estados, "cancelada": o.estado_orden.nombre == "Cancelada", "actual": o.estado_orden.orden_flujo,
    })


@login_requerido
def pedidos(request):
    """Mis pedidos: las órdenes del cliente, de la más nueva a la más antigua."""
    cliente = cuentas.cliente_de_sesion(request)
    ordenes = list(Orden.objects.filter(direccion__cliente=cliente).select_related("estado_orden", "direccion__comuna").order_by("-creada_en", "-orden_id"))
    totales, unidades = defaultdict(int), defaultdict(int)
    for oi in OrdenItem.objects.filter(orden__in=ordenes):
        totales[oi.orden_id] += oi.cantidad * oi.precio_unitario_clp
        unidades[oi.orden_id] += oi.cantidad
    filas = [{"o": o, "total": totales[o.orden_id], "unidades": unidades[o.orden_id]} for o in ordenes]
    return render(request, "core/pedidos.html", {"filas": filas})
