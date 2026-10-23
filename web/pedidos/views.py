from functools import wraps

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from crm import servicios as crm
from crm.models import Requerimiento

from . import servicios as s


def solo_clientes(vista):
    """Exige sesión iniciada y que la cuenta corresponda a un cliente (B2B o B2C)."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/cuenta/entrar/?next={request.path}")
        cliente = s.cliente_de(request.user)
        if cliente is None:
            messages.error(request, "Tu cuenta no está asociada a un cliente. Entra con una cuenta de cliente.")
            return redirect("catalogo")
        return vista(request, cliente, *args, **kwargs)
    return envoltura


def _mostrar_errores(request, error):
    for m in error.mensajes:
        messages.error(request, m)


@require_POST
@solo_clientes
def agregar(request, cliente):
    try:
        s.agregar(cliente, int(request.POST.get("producto", 0)), int(request.POST.get("cantidad", 1)))
        messages.success(request, "Producto agregado al carrito.")
    except (s.ErrorDeNegocio, ValueError) as e:
        _mostrar_errores(request, e) if isinstance(e, s.ErrorDeNegocio) else messages.error(request, "Cantidad no válida.")
    return redirect(request.POST.get("volver") or "catalogo")


@solo_clientes
def ver_carrito(request, cliente):
    filas = s.lineas(cliente)
    return render(request, "pedidos/carrito.html", {"filas": filas, "total": s.total(filas), "cliente": cliente,
                                                    "direcciones": cliente.direccion_set.select_related("comuna"),
                                                    "pide_oc": cliente.tipo_cliente.codigo == "B2B"})


@require_POST
@solo_clientes
def actualizar(request, cliente):
    try:
        s.fijar_cantidad(cliente, int(request.POST["producto"]), int(request.POST["cantidad"]))
    except (KeyError, ValueError):
        messages.error(request, "Cantidad no válida.")
    return redirect("carrito")


@require_POST
@solo_clientes
def repetir(request, cliente):
    try:
        for aviso in s.repetir_ultimo_pedido(cliente):
            messages.warning(request, aviso)
        messages.success(request, "Copiamos tu último pedido al carrito.")
    except s.ErrorDeNegocio as e:
        _mostrar_errores(request, e)
    return redirect("carrito")


@require_POST
@solo_clientes
def confirmar(request, cliente):
    try:
        orden = s.generar_orden(cliente, request.POST.get("direccion") or 0, request.POST.get("numero_oc", ""))
    except s.ErrorDeNegocio as e:
        _mostrar_errores(request, e)
        return redirect("carrito")
    messages.success(request, f"Orden {orden.orden_id} recibida.")
    return redirect("orden", orden_id=orden.orden_id)


@solo_clientes
def seguimiento(request, cliente):
    """«Seguir mi pedido» de la barra superior: lleva al pedido más reciente que sigue en curso, o a la lista."""
    activa = s.ordenes_de(cliente).filter(estado_orden__es_final=False).first()
    return redirect("orden", orden_id=activa.orden_id) if activa else redirect("pedidos")


@solo_clientes
def mis_pedidos(request, cliente):
    ordenes = list(s.ordenes_de(cliente))
    for o in ordenes:
        o.total = s.total_orden(o)
    return render(request, "pedidos/lista.html", {"ordenes": ordenes})


def _orden_del_cliente(cliente, orden_id):
    orden = s.ordenes_de(cliente).filter(pk=orden_id).first()
    if orden is None:
        raise Http404("Orden no encontrada")           # una orden ajena no se distingue de una inexistente
    return orden


@solo_clientes
def detalle(request, cliente, orden_id):
    orden = _orden_del_cliente(cliente, orden_id)
    return render(request, "pedidos/detalle.html", {
        "es_b2b": cliente.tipo_cliente.codigo == "B2B", "orden": orden, "items": orden.ordenitem_set.select_related("producto"), "total": s.total_orden(orden),
        "seg": s.seguimiento(orden) if not orden.estado_orden.es_final or orden.estado_orden.nombre == "Entregada" else None,
        "puede_cancelar": not orden.estado_orden.es_final and orden.estado_orden.orden_flujo == 1})


@require_POST
@solo_clientes
def cancelar(request, cliente, orden_id):
    orden = _orden_del_cliente(cliente, orden_id)
    try:
        s.cancelar(orden, como="cliente")
        messages.success(request, "Orden cancelada; el stock quedó repuesto.")
    except s.ErrorDeNegocio as e:
        _mostrar_errores(request, e)
    return redirect("orden", orden_id=orden_id)


@solo_clientes
def soporte(request, cliente):
    """CU-09: el cliente registra una consulta o reclamo; la IA la clasifica (RN-14) y llega a la bandeja del CRM."""
    ref = request.POST.get("orden") or request.GET.get("orden") or ""
    orden = s.ordenes_de(cliente).filter(pk=int(ref)).first() if ref.isdigit() else None     # solo una orden propia
    if request.method == "POST":
        try:
            r = crm.crear_requerimiento(cliente, request.POST.get("asunto", ""), request.POST.get("descripcion", ""), orden=orden)
            messages.success(request, "Recibimos tu consulta. Te responderemos a la brevedad." if r.estado != "clasificado"
                             else f"Recibimos tu consulta y la derivamos a «{r.categoria_requerimiento}».")
            return redirect("soporte")
        except s.ErrorDeNegocio as e:
            _mostrar_errores(request, e)
    return render(request, "pedidos/soporte.html", {
        "orden": orden, "requerimientos": Requerimiento.objects.filter(cliente=cliente).select_related("categoria_requerimiento").order_by("-creado_en")})
