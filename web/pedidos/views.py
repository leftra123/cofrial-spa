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


def _respuesta_json(request, cliente):
    """Mismo resultado que la redirección, en JSON: los mensajes (que así no reaparecen en la página siguiente) y cuántos productos hay en el carrito."""
    from django.contrib.messages import get_messages
    from django.http import JsonResponse
    from .models import CarritoItem
    mensajes = [{"tipo": m.level_tag, "texto": str(m)} for m in get_messages(request)]
    n = sum(CarritoItem.objects.filter(carrito__cliente=cliente, carrito__estado="abierto").values_list("cantidad", flat=True))
    return JsonResponse({"ok": not any(m["tipo"] == "error" for m in mensajes), "mensajes": mensajes, "carrito_n": n}, json_dumps_params={"ensure_ascii": False})


@require_POST
@solo_clientes
def agregar(request, cliente):
    try:
        s.agregar(cliente, int(request.POST.get("producto", 0)), int(request.POST.get("cantidad", 1)))
        messages.success(request, "Producto agregado al carrito.")
    except (s.ErrorDeNegocio, ValueError) as e:
        _mostrar_errores(request, e) if isinstance(e, s.ErrorDeNegocio) else messages.error(request, "Cantidad no válida.")
    if request.headers.get("X-Requested-With") == "fetch":         # mejora progresiva: la tienda agrega sin recargar; sin JavaScript sigue la redirección de siempre
        return _respuesta_json(request, cliente)
    return redirect(request.POST.get("volver") or "catalogo")


@solo_clientes
def ver_carrito(request, cliente):
    filas = s.lineas(cliente)
    return render(request, "pedidos/carrito.html", {"filas": filas, "total": s.total(filas), "cliente": cliente,
                                                    "sin_stock": [f for f in filas if not f["hay_stock"]],
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
        ordenes = s.generar_ordenes(cliente, request.POST.get("direccion") or 0, request.POST.get("numero_oc", ""))
    except s.ErrorDeNegocio as e:
        _mostrar_errores(request, e)
        return redirect("carrito")
    orden = ordenes[0]
    if len(ordenes) > 1:
        numeros = " y ".join(f"N.º {o.orden_id}" for o in ordenes)
        messages.success(request, f"Tu compra se dividió en {len(ordenes)} pedidos, uno por rango de temperatura, porque cada uno viaja en su camión: {numeros}.")
    else:
        messages.success(request, f"Orden {orden.orden_id} recibida.")
    return redirect(f"/pedidos/{orden.orden_id}/?nueva=1")


@solo_clientes
def seguimiento(request, cliente):
    """«Seguir mi pedido» de la barra superior: lleva al pedido más reciente que sigue en curso, o a la lista."""
    ordenes = s.ordenes_de(cliente)
    activa = ordenes.filter(estado_orden__es_final=False).first()
    if activa:
        return redirect("orden", orden_id=activa.orden_id)
    if ordenes.exists():            # sin esta nota el enlace parecía no hacer nada: el cliente caía en la lista sin saber por qué
        messages.info(request, "No tienes pedidos en curso ahora. Aquí está el historial de tus órdenes.")
    return redirect("pedidos")


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
def registrar_oc(request, cliente, orden_id):
    """El cliente institucional agrega su orden de compra a un pedido que quedó «OC pendiente»."""
    try:
        s.registrar_oc(cliente, orden_id, request.POST.get("numero_oc", ""))
        messages.success(request, "Registramos tu orden de compra. Gracias.")
    except s.ErrorDeNegocio as e:
        _mostrar_errores(request, e)
    return redirect("orden", orden_id=orden_id)


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
                             else f"Recibimos tu consulta y la derivamos a \"{r.categoria_requerimiento}\".")
            return redirect("soporte")
        except s.ErrorDeNegocio as e:
            _mostrar_errores(request, e)
    return render(request, "pedidos/soporte.html", {
        "orden": orden, "requerimientos": Requerimiento.objects.filter(cliente=cliente).select_related("categoria_requerimiento").order_by("-creado_en")})


def api_avisos(request):
    """Avisos de la campanita: solo de las órdenes del cliente que inició sesión."""
    from django.http import JsonResponse
    cliente = s.cliente_de(request.user) if request.user.is_authenticated else None
    if cliente is None:
        return JsonResponse({"detail": "Inicia sesión con una cuenta de cliente."}, status=403)
    return JsonResponse({"avisos": s.avisos_de_llegada(cliente)}, json_dumps_params={"ensure_ascii": False})


@solo_clientes
def entrega(request, cliente, orden_id):
    """Confirmación de la entrega en la puerta. GET: estado de la entrega (JSON). POST: accion=aceptar | no_recibido (+ motivo); responde
    JSON si lo pide la pantalla (X-Requested-With: fetch o Accept: application/json) y, si no, vuelve a la orden con un mensaje."""
    from django.http import JsonResponse
    orden = _orden_del_cliente(cliente, orden_id)
    quiere_json = request.headers.get("X-Requested-With") == "fetch" or "application/json" in request.headers.get("Accept", "")
    if request.method == "GET":
        return JsonResponse(s.entrega_de(orden), json_dumps_params={"ensure_ascii": False})
    try:
        orden = s.resolver_entrega(cliente, orden_id, request.POST.get("accion", ""), request.POST.get("motivo", ""))
        mensaje = ("Gracias por confirmar la recepción." if orden.estado_orden.nombre == "Entregada"
                   else "Registramos que no pudiste recibir tu pedido. Nuestro equipo te contactará para reprogramar.")
        ok = True
    except s.ErrorDeNegocio as e:
        mensaje, ok = " ".join(e.mensajes), False
    if quiere_json:
        orden = _orden_del_cliente(cliente, orden_id)
        return JsonResponse({"ok": ok, "mensaje": mensaje, "entrega": s.entrega_de(orden)}, status=200 if ok else 400,
                            json_dumps_params={"ensure_ascii": False})
    (messages.success if ok else messages.error)(request, mensaje)
    return redirect("orden", orden_id=orden_id)
