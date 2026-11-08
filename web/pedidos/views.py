from functools import wraps

from django.contrib import messages
from django.http import Http404
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from clientes.models import Comuna
from cofrial import entradas
from crm import servicios as crm
from crm.models import Requerimiento

from . import documentos, mercadopago as mp, servicios as s


def solo_clientes(vista):
    """Exige sesión iniciada y que la cuenta corresponda a un cliente (B2B o B2C)."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.method != "GET":             # se explica por qué pide ingresar de nuevo; el carrito está en la base y no se pierde
                messages.info(request, "Tu sesión terminó. Ingresa de nuevo: tu carrito sigue guardado.")
            return redirect(entradas.url_de_ingreso(request, "/carrito/"))
        cliente = s.cliente_de(request.user)
        if cliente is None:
            if request.method == "POST":            # una cuenta del equipo no compra, no cancela ni abre reclamos como cliente: se le dice claro
                return render(request, "403.html", {"detalle": "Las cuentas del equipo no compran, no cancelan pedidos ni abren reclamos como cliente. "
                                                               "Para un pedido a nombre de un cliente, usa la ficha del cliente en el CRM."}, status=403)
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
    mensajes = [{"tipo": m.level_tag, "texto": str(m)} for m in get_messages(request)]
    n = s.lineas_en_carrito(cliente)
    return JsonResponse({"ok": not any(m["tipo"] == "error" for m in mensajes), "mensajes": mensajes, "carrito_n": n}, json_dumps_params={"ensure_ascii": False})


@require_POST
@solo_clientes
def agregar(request, cliente):
    try:
        s.agregar(cliente, entradas.entero(request.POST.get("producto", 0)), entradas.entero(request.POST.get("cantidad", 1)))
        messages.success(request, "Producto agregado al carrito.")
    except (s.ErrorDeNegocio, ValueError) as e:
        _mostrar_errores(request, e) if isinstance(e, s.ErrorDeNegocio) else messages.error(request, "Cantidad no válida.")
    if request.headers.get("X-Requested-With") == "fetch":         # mejora progresiva: la tienda agrega sin recargar; sin JavaScript sigue la redirección de siempre
        return _respuesta_json(request, cliente)
    destino = request.POST.get("volver") or "/catalogo/"
    seguro = url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()) and destino.startswith("/")
    return redirect(destino if seguro else "/catalogo/")           # misma validación que /avisos/pedir/: sin redirección abierta


@ensure_csrf_cookie
@solo_clientes
def ver_carrito(request, cliente):
    filas = s.lineas(cliente)
    sin_stock = [f for f in filas if not f["hay_stock"]]
    es_b2c = cliente.tipo_cliente.codigo == "B2C"
    mp_brick = es_b2c and mp.activo() and filas and not sin_stock
    total = s.total(filas)
    ctx = {
        "filas": filas, "total": total, "cliente": cliente, "sin_stock": sin_stock,
        "direcciones": cliente.direccion_set.select_related("comuna"), "comunas": Comuna.objects.order_by("nombre"),
        "pide_oc": cliente.tipo_cliente.codigo == "B2B",
        "recibe_opciones": s.opciones_de_quien_recibe(cliente), "recibe_maximo": s.RECIBE_MAXIMO,
        "mp_brick": mp_brick,
    }
    if mp_brick:
        ctx["mp_brick_cfg"] = {
            "publicKey": mp.clave_publica(),
            "amount": total,
            "email": mp.email_cliente_mp(cliente),
            "csrf": get_token(request),
            "urlPago": "/carrito/mp/pagar/",
            "sinStock": False,
        }
    return render(request, "pedidos/carrito.html", ctx)


@require_POST
@solo_clientes
def actualizar(request, cliente):
    try:
        s.fijar_cantidad(cliente, entradas.entero(request.POST["producto"]), entradas.entero(request.POST["cantidad"]))
    except (KeyError, ValueError):
        messages.error(request, "Cantidad no válida.")
    except s.ErrorDeNegocio as e:
        _mostrar_errores(request, e)
    return redirect("carrito")


@require_POST
@solo_clientes
def direccion_nueva(request, cliente):
    """CU-04, A2: el cliente agrega otra dirección desde el carrito (una empresa con varias sucursales, un particular que se mudó)."""
    try:
        d = s.agregar_direccion(cliente, request.POST.get("calle_numero", ""), request.POST.get("comuna"))
        messages.success(request, f"Agregamos «{d}» a tus direcciones.")
        if d.lat is None:
            messages.warning(request, "No pudimos ubicar esa dirección en el mapa. Puedes comprar igual; la revisaremos antes de despachar.")
    except s.ErrorDeNegocio as e:
        _mostrar_errores(request, e)
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


def _quien_recibe_del_formulario(post):
    """Dos formas de elegir quién recibe: una persona de la lista (`recibe`) o un nombre nuevo (`recibe_nuevo`, que tiene prioridad si se escribió)."""
    return (post.get("recibe_nuevo") or "").strip() or post.get("recibe", "")


def _mensaje_ordenes_creadas(ordenes):
    orden = ordenes[0]
    if len(ordenes) > 1:
        numeros = " y ".join(f"N.º {o.orden_id}" for o in ordenes)
        mensaje = f"Tu compra se dividió en {len(ordenes)} pedidos, uno por rango de temperatura, porque cada uno viaja en su camión: {numeros}."
    else:
        mensaje = f"Orden {orden.orden_id} recibida."
    emitidos = list(documentos.Documento.objects.filter(orden__in=ordenes, tipo__in=("boleta", "factura")).order_by("folio"))
    if emitidos:
        nombre = emitidos[0].get_tipo_display().lower()
        folios = " y ".join(str(d.folio) for d in emitidos)
        mensaje += f" Pago aprobado y {nombre} N.º {folios} emitida." if len(emitidos) == 1 else f" Pago aprobado y {nombre}s N.º {folios} emitidas."
    return mensaje, orden


@require_POST
@solo_clientes
def confirmar(request, cliente):
    direccion = request.POST.get("direccion") or 0
    numero_oc = request.POST.get("numero_oc", "")
    if cliente.tipo_cliente.codigo == "B2C" and mp.activo():
        messages.info(request, "Completa el pago con Mercado Pago en el formulario del carrito.")
        return redirect("carrito")
    try:
        ordenes = s.generar_ordenes(cliente, direccion, numero_oc, recibe=_quien_recibe_del_formulario(request.POST), comprobante=request.POST.get("comprobante") or None, giro=request.POST.get("giro", ""))
    except s.ErrorDeNegocio as e:
        _mostrar_errores(request, e)
        return redirect("carrito")
    mensaje, orden = _mensaje_ordenes_creadas(ordenes)
    messages.success(request, mensaje)
    return redirect(f"/pedidos/{orden.orden_id}/?nueva=1")


@require_POST
@solo_clientes
def mp_pagar_brick(request, cliente):
    """Recibe el formData del Payment Brick y crea el pago en MP."""
    import json
    from django.http import JsonResponse
    if cliente.tipo_cliente.codigo != "B2C" or not mp.activo():
        return JsonResponse({"ok": False, "mensaje": "El pago con Mercado Pago no está disponible."}, status=403)
    try:
        datos = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "mensaje": "Solicitud no válida."}, status=400)
    try:
        checkout = mp.pagar_con_brick(cliente, datos.get("direccion"), datos.get("formData") or {}, datos.get("comprobante"), datos.get("giro", ""), recibe=str(datos.get("recibe") or ""))
        return JsonResponse({"ok": True, "redirect": f"/pedidos/{checkout.primera_orden_id}/?nueva=1"},
                            json_dumps_params={"ensure_ascii": False})
    except s.ErrorDeNegocio as e:
        return JsonResponse({"ok": False, "mensaje": " ".join(e.mensajes)}, status=400,
                            json_dumps_params={"ensure_ascii": False})


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
    return render(request, "pedidos/lista.html", {"ordenes": ordenes, "es_b2b": cliente.tipo_cliente.codigo == "B2B"})


def _orden_del_cliente(cliente, orden_id):
    orden = s.ordenes_de(cliente).filter(pk=orden_id).first()
    if orden is None:
        raise Http404("Orden no encontrada")           # una orden ajena no se distingue de una inexistente
    return orden


@solo_clientes
def detalle(request, cliente, orden_id):
    orden = _orden_del_cliente(cliente, orden_id)
    en_la_puerta = orden.estado_orden.nombre == "Camión en la puerta"
    docs = documentos.documentos_de_orden(orden)
    items = list(orden.ordenitem_set.select_related("producto"))
    for i in items:
        i.subtotal = i.cantidad_aceptada * i.precio_unitario_clp
    cerrada = orden.estado_orden.nombre in s.RECEPCION_CERRADA
    return render(request, "pedidos/detalle.html", {
        "es_b2b": cliente.tipo_cliente.codigo == "B2B", "orden": orden, "documentos": docs,
        "venta": next((d for d in docs if d.tipo in ("boleta", "factura")), None),
        "items": items, "total": s.total_orden(orden), "rechazo": s.rechazo_de(orden) if cerrada else None,
        "revision": s.revision_de(orden) if en_la_puerta else None,          # paso de revisión al recibir: productos y temperatura del viaje
        "reclamo": s.reclamo_al_recibir(orden) if cerrada else None,
        "seg": s.seguimiento(orden) if not orden.estado_orden.es_final or cerrada else None,
        "viaje_sigue": bool(orden.despacho_id) and s.Orden.objects.filter(despacho_id=orden.despacho_id, estado_orden__nombre__in=("Despachada", "Camión en la puerta")).exclude(pk=orden.pk).exists(),
        "puede_cancelar": not orden.estado_orden.es_final and orden.estado_orden.orden_flujo == 1})


@solo_clientes
def comprobante(request, cliente, orden_id, documento_id):
    """La boleta o factura ya emitida de este pedido: se consulta en pantalla y se descarga en PDF."""
    from django.http import HttpResponse
    orden = _orden_del_cliente(cliente, orden_id)
    doc = documentos.Documento.objects.filter(pk=documento_id, orden=orden, tipo__in=("boleta", "factura")).select_related("orden").first()
    if doc is None:
        raise Http404("Documento no encontrado")
    if request.GET.get("descarga"):
        pdf = documentos.comprobante_pdf(doc)
        respuesta = HttpResponse(pdf, content_type="application/pdf")
        respuesta["Content-Disposition"] = f'attachment; filename="{doc.tipo}-{doc.folio}.pdf"'
        return respuesta
    filas, neto = documentos.lineas_de_documento(doc)
    return render(request, "pedidos/comprobante.html", {
        "orden": orden, "doc": doc, "cliente_doc": orden.direccion.cliente, "es_b2b": cliente.tipo_cliente.codigo == "B2B",
        "items": filas, "total": neto, "notas": documentos.Documento.objects.filter(referencia=doc, tipo="nota_credito").order_by("documento_id"),
        "rechazo": s.rechazo_de(orden)})


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
    orden = s.ordenes_de(cliente).filter(pk=entradas.entero(ref)).first() if entradas.es_entero(ref) else None     # solo una orden propia
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


def _rechazos_del_formulario(post):
    """Los campos rechazo_<producto_id> y motivo_<producto_id> del paso de revisión: {producto_id: (cantidad, motivo)}. Valida el servicio."""
    return {int(clave[len("rechazo_"):]): (valor, post.get("motivo_" + clave[len("rechazo_"):], ""))
            for clave, valor in post.items() if clave.startswith("rechazo_") and entradas.es_entero(clave[len("rechazo_"):])}


def _mensaje_de_rechazo(rechazo, es_b2b):
    """Qué pasó con la mercadería y con el dinero, en una frase para el cliente."""
    clp = documentos._clp
    if rechazo["nota"]:
        dinero = f"Emitimos la {rechazo['nota']} por {clp(rechazo['nota'].monto_clp)}" + (f" y registramos la devolución de {clp(rechazo['devuelto'])}." if rechazo["devuelto"] else ".")
    elif rechazo["total"]:
        dinero = "No se emitirá factura por este pedido." if es_b2b else "No se te cobra."
    else:
        dinero = "La factura será solo por lo que recibiste."
    if rechazo["total"]:
        return f"Registramos que rechazaste todo el pedido. {dinero} Ventas te contactará."
    u = rechazo["unidades"]
    return f"Pedido recibido con {u} unidad{'es' if u != 1 else ''} rechazada{'s' if u != 1 else ''}. {dinero} Ventas te contactará."


@solo_clientes
def entrega(request, cliente, orden_id):
    """Confirmación de la entrega en la puerta. GET: estado de la entrega (JSON). POST: accion=aceptar (con resultado, tipo_problema, problema y, por producto,
    rechazo_<id> y motivo_<id>) | no_recibido (+ motivo); responde
    JSON si lo pide la pantalla (X-Requested-With: fetch o Accept: application/json) y, si no, vuelve a la orden con un mensaje."""
    from django.http import JsonResponse
    orden = _orden_del_cliente(cliente, orden_id)
    quiere_json = request.headers.get("X-Requested-With") == "fetch" or "application/json" in request.headers.get("Accept", "")
    if request.method == "GET":
        datos = s.entrega_de(orden)
        if request.GET.get("revision") and datos["puede_responder"]:          # el diálogo de la campanita arma el paso de revisión con esto
            datos["revision"] = s.revision_de(orden)
        return JsonResponse(datos, json_dumps_params={"ensure_ascii": False})
    accion = request.POST.get("accion", "")
    con_problema = accion == "aceptar" and request.POST.get("resultado") == "falla"      # sin «resultado» (clientes antiguos de la API) todo llegó bien
    try:
        orden = s.resolver_entrega(cliente, orden_id, accion, request.POST.get("problema" if con_problema else "motivo", ""),
                                   con_problema=con_problema, tipo_problema=request.POST.get("tipo_problema", "otro"),
                                   rechazos=_rechazos_del_formulario(request.POST) if con_problema else None)      # con «todo llegó bien» no se rechaza nada, aunque el formulario traiga números
        rechazo = s.rechazo_de(orden)
        if rechazo:
            mensaje = _mensaje_de_rechazo(rechazo, cliente.tipo_cliente.codigo == "B2B")
        elif orden.estado_orden.nombre == "Entregada":
            mensaje = ("Pedido entregado exitosamente. Registramos el problema que nos contaste y ventas te contactará."
                       if con_problema else "Pedido entregado exitosamente. Gracias por confirmar la recepción.")
        else:
            mensaje = "Registramos que no pudiste recibir tu pedido. Nuestro equipo te contactará para reprogramar."
        ok = True
    except s.ErrorDeNegocio as e:
        mensaje, ok = " ".join(e.mensajes), False
    if quiere_json:
        orden = _orden_del_cliente(cliente, orden_id)
        return JsonResponse({"ok": ok, "mensaje": mensaje, "entrega": s.entrega_de(orden)}, status=200 if ok else 400,
                            json_dumps_params={"ensure_ascii": False})
    (messages.success if ok else messages.error)(request, mensaje)
    return redirect("orden", orden_id=orden_id)


def _checkout_del_cliente(cliente, request):
    ref = request.GET.get("external_reference") or request.GET.get("external_reference_id") or ""
    checkout = mp.checkout_por_referencia(ref) if ref else None
    if checkout and checkout.cliente_id != cliente.cliente_id:
        raise Http404("Checkout no encontrado")
    payment_id = request.GET.get("payment_id") or request.GET.get("collection_id")
    if checkout is None and payment_id and mp.activo():
        try:
            checkout = mp.procesar_pago_mp(str(payment_id))
        except s.ErrorDeNegocio:
            checkout = None
    elif checkout and payment_id and checkout.estado == "pendiente" and mp.activo():
        try:
            checkout = mp.procesar_pago_mp(str(payment_id))
        except s.ErrorDeNegocio:
            pass
    return checkout


def _redirigir_tras_mp(request, cliente, checkout, ok_default, err_default):
    if checkout and checkout.estado == "completado" and checkout.primera_orden_id:
        ordenes = list(checkout.ordenes.order_by("orden_id"))
        if ordenes:
            messages.success(request, _mensaje_ordenes_creadas(ordenes)[0])
            return redirect(f"/pedidos/{checkout.primera_orden_id}/?nueva=1")
    if checkout and checkout.estado == "fallido":
        messages.error(request, err_default)
    elif checkout and checkout.estado == "pendiente":
        messages.info(request, "Tu pago está pendiente de confirmación. Cuando Mercado Pago lo apruebe, crearemos tu pedido.")
    else:
        messages.info(request, ok_default if checkout is None else err_default)
    return redirect("carrito")


@require_GET
@solo_clientes
def mp_vuelta_exito(request, cliente):
    checkout = _checkout_del_cliente(cliente, request)
    return _redirigir_tras_mp(request, cliente, checkout,
                              "Gracias. Estamos confirmando tu pago.",
                              "No pudimos confirmar el pago. Revisa tu carrito e intenta de nuevo.")


@require_GET
@solo_clientes
def mp_vuelta_fallo(request, cliente):
    checkout = _checkout_del_cliente(cliente, request)
    if checkout and checkout.estado == "pendiente" and mp.activo():
        payment_id = request.GET.get("payment_id") or request.GET.get("collection_id")
        if payment_id:
            try:
                checkout = mp.procesar_pago_mp(str(payment_id))
            except s.ErrorDeNegocio:
                pass
    return _redirigir_tras_mp(request, cliente, checkout,
                              "Volviste del checkout de pago.",
                              "El pago no fue aprobado. Tu carrito sigue disponible.")


@require_GET
@solo_clientes
def mp_vuelta_pendiente(request, cliente):
    checkout = _checkout_del_cliente(cliente, request)
    return _redirigir_tras_mp(request, cliente, checkout,
                              "Tu pago quedó pendiente.",
                              "El pago no fue aprobado. Tu carrito sigue disponible.")


@csrf_exempt
def mp_webhook(request):
    """Notificaciones IPN/Webhook de Mercado Pago (sin sesión)."""
    from django.http import HttpResponse
    if request.method != "POST":
        return HttpResponse(status=405)
    if not mp.activo():
        return HttpResponse(status=204)
    payment_id = request.GET.get("data.id") or request.GET.get("id")
    try:
        mp.procesar_notificacion_webhook(request.body, payment_id_query=payment_id)
    except s.ErrorDeNegocio as e:
        logger = __import__("logging").getLogger("cofrial.mercadopago")
        logger.warning("Webhook MP: %s", " ".join(e.mensajes))
    return HttpResponse(status=200)
