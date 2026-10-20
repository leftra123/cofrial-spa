from django.contrib import messages
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import servicios
from .models import Cliente, Direccion, EstadoOrden, OrdenItem, Orden, PrecioProducto, Producto

# Perfil de compra -> lista de precios (tabla lista_precio)
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


def cliente_actual(request):
    """Cliente de la sesión. Es un sustituto temporal del inicio de sesión (pendiente: autenticación)."""
    cid = request.session.get("cliente_id")
    if not cid:
        return None
    return Cliente.objects.select_related("tipo_cliente").filter(pk=cid).first()


def catalogo(request):
    """Catálogo de refrigerados y congelados con el precio de la lista que corresponde.

    Con un cliente elegido se usa su lista de precios y se puede agregar al carrito (RN-01);
    sin cliente, ?perfil=b2b|b2c solo permite mirar.
    """
    cliente = cliente_actual(request)
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
    items = [
        {"p": p, "rango": p.categoria.rango_temperatura, "precio": precios.get(p.producto_id)}
        for p in productos
    ]
    return render(request, "core/catalogo.html", {"items": items, "perfil": perfil, "lista": lista})


@require_POST
def elegir_cliente(request):
    """Sustituto temporal del login: guarda en la sesión con qué cliente se compra."""
    cid = request.POST.get("cliente_id")
    if cid and Cliente.objects.filter(pk=cid).exists():
        request.session["cliente_id"] = int(cid)
    else:
        request.session.pop("cliente_id", None)
    return redirect(request.POST.get("next") or "catalogo")


def _exigir_cliente(request):
    cliente = cliente_actual(request)
    if cliente is None:
        messages.error(request, "Elige con qué cliente compras (arriba a la derecha).")
    return cliente


@require_POST
def agregar(request):
    cliente = _exigir_cliente(request)
    if cliente is None:
        return redirect("catalogo")
    try:
        servicios.agregar(cliente, int(request.POST.get("producto_id", 0)), int(request.POST.get("cantidad", 1)))
        messages.success(request, "Producto agregado al carrito.")
    except (servicios.ErrorCompra, ValueError) as exc:
        messages.error(request, str(exc) if isinstance(exc, servicios.ErrorCompra) else "Cantidad no válida.")
    return redirect("catalogo")


@require_POST
def quitar(request):
    cliente = _exigir_cliente(request)
    if cliente:
        servicios.quitar(cliente, int(request.POST.get("producto_id", 0)))
    return redirect("carrito")


def carrito(request):
    cliente = cliente_actual(request)
    if cliente is None:
        messages.error(request, "Elige con qué cliente compras (arriba a la derecha).")
        return redirect("catalogo")
    lineas, total = servicios.detalle(cliente)
    direcciones = Direccion.objects.filter(cliente=cliente).select_related("comuna").order_by("-es_principal", "direccion_id")
    return render(request, "core/carrito.html", {
        "lineas": lineas, "total": total, "direcciones": direcciones, "es_b2b": cliente.tipo_cliente.codigo == "B2B",
        "hay_sin_stock": any(l["sin_stock"] for l in lineas),
    })


@require_POST
def confirmar(request):
    cliente = _exigir_cliente(request)
    if cliente is None:
        return redirect("catalogo")
    try:
        orden = servicios.confirmar(cliente, request.POST.get("direccion_id"), request.POST.get("numero_oc", ""))
    except servicios.ErrorCompra as exc:
        for m in exc.mensajes:
            messages.error(request, m)
        return redirect("carrito")
    return redirect("orden", orden_id=orden.orden_id)


def orden(request, orden_id):
    cliente = cliente_actual(request)
    o = Orden.objects.select_related("estado_orden", "direccion__comuna").filter(pk=orden_id).first()
    if cliente is None or o is None or o.direccion.cliente_id != cliente.cliente_id:
        raise Http404("Orden no encontrada")
    lineas = [{"producto": i.producto, "cantidad": i.cantidad, "precio": i.precio_unitario_clp, "subtotal": i.cantidad * i.precio_unitario_clp}
              for i in OrdenItem.objects.filter(orden=o).select_related("producto").order_by("producto__nombre")]
    estados = [e for e in EstadoOrden.objects.order_by("orden_flujo") if e.nombre != "Cancelada"]
    return render(request, "core/orden.html", {
        "orden": o, "lineas": lineas, "total": sum(l["subtotal"] for l in lineas),
        "estados": estados, "cancelada": o.estado_orden.nombre == "Cancelada",
        "actual": o.estado_orden.orden_flujo,
    })
