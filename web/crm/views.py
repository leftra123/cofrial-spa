from functools import wraps

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalogo.models import Producto
from clientes.models import Vendedor
from pedidos import servicios as pedidos

from . import ia, servicios as s
from .models import CategoriaRequerimiento, EtapaPipeline, Prospecto, Requerimiento

ERRORES = (pedidos.ErrorDeNegocio, ValueError)


def con_rol(*roles):
    """Permiso por rol (Tabla 2 del informe). Los clientes del portal no entran al CRM."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f"/cuenta/entrar/?next={request.path}")
            mi_rol = s.rol(request.user)
            if mi_rol not in roles:
                return render(request, "403.html", {"detalle": "Tu cuenta no tiene acceso a esta sección del CRM."}, status=403)
            request.rol = mi_rol
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


TODOS = ("admin", "gerencia", "vendedor", "despachador")
COMERCIAL = ("admin", "gerencia", "vendedor")


def _avisar(request, error):
    for m in getattr(error, "mensajes", [str(error) or "Dato no válido."]):
        messages.error(request, m)


def _contexto(request, **extra):
    return {"rol": request.rol, "puede_editar": s.puede_editar(request.user), **extra}


@con_rol(*TODOS)
def panel(request):
    if request.rol == "despachador":
        return redirect("crm_alertas")
    return render(request, "crm/panel.html", _contexto(request, ind=s.indicadores(request.user)))


@con_rol(*COMERCIAL)
def embudo(request):
    prospectos = list(s.prospectos_visibles(request.user).order_by("-creado_en"))
    columnas = [{"etapa": e, "prospectos": [p for p in prospectos if p.etapa_id == e.pk]} for e in EtapaPipeline.objects.all()]
    return render(request, "crm/embudo.html", _contexto(request, columnas=columnas, sin_prospectos=not prospectos))


@con_rol("admin", "vendedor")
def prospecto_nuevo(request):
    vendedores = Vendedor.objects.filter(activo=True)
    campo_error = ""                  # el campo a corregir: el formulario vuelve con lo que se escribió y ese campo marcado
    if request.method == "POST":
        p = request.POST
        vendedor = s.vendedor_de(request.user) or vendedores.filter(pk=p.get("vendedor") or 0).first()
        if vendedor is None:
            messages.error(request, "Elige el vendedor responsable.")
            campo_error = "vendedor"
        elif not p.get("nombre_contacto", "").strip():
            messages.error(request, "Indica el nombre del contacto.")
            campo_error = "nombre_contacto"
        elif not (p.get("email", "").strip() or p.get("telefono", "").strip()):
            messages.error(request, "Ingresa al menos un correo o un teléfono.")
            campo_error = "email"
        else:
            try:
                monto = int(p["monto"]) if p.get("monto") else None
            except ValueError:
                monto = None
            nuevo = Prospecto.objects.create(
                vendedor=vendedor, etapa=EtapaPipeline.objects.get(orden_etapa=1), nombre_contacto=p["nombre_contacto"].strip(),
                empresa=p.get("empresa", "").strip(), email=p.get("email", "").strip(), telefono=p.get("telefono", "").strip(),
                origen=p.get("origen", "otro"), monto_estimado_clp=monto)
            messages.success(request, "Prospecto creado.")
            return redirect("crm_prospecto", pk=nuevo.pk)
    return render(request, "crm/prospecto_nuevo.html", _contexto(request, origenes=Prospecto.ORIGENES, vendedores=vendedores,
                                                                 es_admin=request.rol == "admin", v=request.POST, campo_error=campo_error))


def _prospecto(request, pk):
    p = s.prospectos_visibles(request.user).filter(pk=pk).first()
    if p is None:
        raise Http404("Prospecto no encontrado")      # el de otro vendedor no se distingue de uno inexistente (RN-09)
    return p


@con_rol(*COMERCIAL)
def prospecto_detalle(request, pk):
    p = _prospecto(request, pk)
    return render(request, "crm/prospecto.html", _contexto(
        request, p=p, interacciones=p.interaccion_set.select_related("vendedor").order_by("-registrada_en"),
        destinos=s.transiciones_de(p), tipos=[t for t, _ in p.interaccion_set.model.TIPOS]))


@require_POST
@con_rol(*COMERCIAL)
def prospecto_mover(request, pk):
    _prospecto(request, pk)
    try:
        nuevo = s.mover_prospecto(request.user, pk, request.POST.get("etapa") or 0, request.POST.get("motivo", ""), request.POST.get("rut", ""))
        messages.success(request, f"Prospecto en \"{nuevo.etapa.nombre}\".")
        if nuevo.etapa.es_ganada:
            return redirect("crm_cliente", pk=nuevo.cliente_id)
    except ERRORES as e:
        _avisar(request, e)
    return redirect("crm_prospecto", pk=pk)


@require_POST
@con_rol(*COMERCIAL)
def prospecto_interaccion(request, pk):
    p = _prospecto(request, pk)
    try:
        s.registrar_interaccion(request.user, request.POST.get("tipo", "nota"), request.POST.get("detalle", ""), prospecto=p)
        messages.success(request, "Interacción registrada.")
    except ERRORES as e:
        _avisar(request, e)
    return redirect("crm_prospecto", pk=pk)


@con_rol(*COMERCIAL)
def clientes(request):
    return render(request, "crm/clientes.html", _contexto(request, clientes=s.clientes_visibles(request.user).order_by("nombre")))


def _cliente(request, pk):
    c = s.clientes_visibles(request.user).filter(pk=pk).first()
    if c is None:
        raise Http404("Cliente no encontrado")
    return c


@con_rol(*COMERCIAL)
def cliente_ficha(request, pk):
    c = _cliente(request, pk)
    return render(request, "crm/cliente.html", _contexto(
        request, c=c, ordenes=s.ordenes_de_cliente(c), direcciones=c.direccion_set.select_related("comuna"),
        interacciones=c.interaccion_set.select_related("vendedor").order_by("-registrada_en"),
        productos=Producto.objects.filter(activo=True, stock_disponible__gt=0).order_by("nombre"),
        pide_oc=c.tipo_cliente.codigo == "B2B"))


@require_POST
@con_rol(*COMERCIAL)
def cliente_interaccion(request, pk):
    c = _cliente(request, pk)
    try:
        s.registrar_interaccion(request.user, request.POST.get("tipo", "nota"), request.POST.get("detalle", ""), cliente=c)
        messages.success(request, "Interacción registrada.")
    except ERRORES as e:
        _avisar(request, e)
    return redirect("crm_cliente", pk=pk)


@require_POST
@con_rol(*COMERCIAL)
def cliente_pedido(request, pk):
    c = _cliente(request, pk)
    try:
        cantidades = {int(k[2:]): int(v) for k, v in request.POST.items() if k.startswith("q_") and v.strip()}
        orden = s.crear_pedido_para_cliente(request.user, c.pk, cantidades, request.POST.get("direccion") or 0, request.POST.get("numero_oc", ""),
                                            request.POST.get("tipo_interaccion", ""), request.POST.get("detalle_interaccion", ""))
        messages.success(request, f"Pedido N.º {orden.orden_id} creado a nombre de {c.nombre}.")
    except ERRORES as e:
        _avisar(request, e)
    return redirect("crm_cliente", pk=pk)


@con_rol(*COMERCIAL)
def requerimientos(request):
    return render(request, "crm/requerimientos.html", _contexto(
        request, reqs=Requerimiento.objects.select_related("cliente", "categoria_requerimiento").order_by("-creado_en"),
        categorias=CategoriaRequerimiento.objects.all(), umbral=s.UMBRAL_CONFIANZA))


@con_rol(*COMERCIAL)
def requerimiento_detalle(request, pk):
    """Un requerimiento con el texto original, el desglose de la IA y, si es de temperatura, el dato real de la base al lado."""
    r = get_object_or_404(Requerimiento.objects.select_related("cliente", "categoria_requerimiento", "orden__despacho__camion__rango_temperatura", "orden__estado_orden"), pk=pk)
    d = r.desglose or None
    dato = s.telemetria_del_viaje(r.orden) if r.orden_id and d and (d.get("motivo_principal") == "temperatura_inadecuada" or "temperatur" in r.descripcion.lower()) else None
    return render(request, "crm/requerimiento.html", _contexto(request, r=r, d=d, dato=dato, umbral=s.UMBRAL_CONFIANZA, categorias=CategoriaRequerimiento.objects.all()))


@require_POST
@con_rol(*COMERCIAL)
def requerimiento_clasificar(request, pk):
    try:
        s.clasificar_manual(request.user, pk, int(request.POST.get("categoria") or 0))
        messages.success(request, "Requerimiento clasificado.")
    except (ObjectDoesNotExist, *ERRORES):
        messages.error(request, "No se pudo clasificar el requerimiento.")
    return redirect("crm_requerimientos")


@require_POST
@con_rol(*COMERCIAL)
def requerimiento_ia(request, pk):
    try:
        r = s.reintentar_ia(request.user, pk)
        if r.estado == "clasificado":
            messages.success(request, f"La IA lo clasificó como \"{r.categoria_requerimiento}\" (confianza {r.confianza_ia}).")
        elif getattr(r, "ia_no_disponible", False):
            messages.warning(request, "La IA no está disponible ahora (revisa la clave o la conexión). El requerimiento sigue sin clasificar: clasifícalo a mano.")
        else:
            messages.warning(request, "La IA no estuvo lo bastante segura (confianza bajo 0,60); clasifícalo a mano.")
    except (ObjectDoesNotExist, *ERRORES):
        messages.error(request, "No se pudo clasificar el requerimiento.")
    return redirect("crm_requerimientos")


@con_rol(*COMERCIAL)
def ia_panel(request):
    """Explica la IA y permite probarla en vivo: estado de los proveedores, una prueba lado a lado y un resumen de lo que ha hecho."""
    categorias = list(CategoriaRequerimiento.objects.values_list("nombre", flat=True))
    asunto = request.POST.get("asunto", "Camión con carga caliente")
    texto = request.POST.get("descripcion", "El camión llegó con la carga tibia, la temperatura estaba muy alta y rechazamos tres cajas.")
    prompt = filas = None
    if request.method == "POST":
        if not texto.strip():
            messages.error(request, "Escribe un mensaje de cliente para probar la IA.")
        else:
            prompt, filas = ia.comparar(asunto[:150], texto[:1000], categorias)
    todos = Requerimiento.objects.all()
    resumen = {"total": todos.count(),
               "por_ia": todos.filter(confianza_ia__isnull=False, categoria_requerimiento__isnull=False, clasificado_manual=False).count(),
               "ia_dudo": todos.filter(confianza_ia__isnull=False, categoria_requerimiento__isnull=True).count(),
               "manual": todos.filter(Q(clasificado_manual=True) | Q(confianza_ia__isnull=True, categoria_requerimiento__isnull=False)).count(),
               "sin_clasificar": todos.filter(estado="sin_clasificar").count()}
    ultimos = list(todos.select_related("cliente", "categoria_requerimiento").order_by("-creado_en")[:12])
    return render(request, "crm/ia.html", _contexto(request, ia=ia.estado(), categorias=categorias, asunto=asunto, texto=texto, prompt=prompt,
                                                    filas=filas, resumen=resumen, ultimos=ultimos, umbral=s.UMBRAL_CONFIANZA, acierto=s.acierto_de_la_ia()))


@con_rol(*TODOS)
def alertas(request):
    return render(request, "crm/alertas.html", _contexto(request, ordenes=s.ordenes_afectadas(request.user)))


@con_rol(*TODOS)
def demanda(request):
    """Productos que los clientes esperan (avisos de stock pendientes): oportunidad de venta y guía para reponer."""
    from catalogo import avisos
    return render(request, "crm/demanda.html", _contexto(request, filas=avisos.demanda_en_espera()))
