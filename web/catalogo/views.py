import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.http import Http404
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from clientes.models import Cliente, TipoCliente
from cofrial import entradas

from . import avisos

from .models import AvisoStock, Categoria, PrecioProducto, Producto, RangoTemperatura

STOCK_BAJO = 20      # por debajo se avisa «Quedan pocas unidades»


def lista_del_visitante(request):
    """Cliente con sesión: la lista de su tipo (B2B institucional o B2C público). Visitante: la pública B2C."""
    if request.user.is_authenticated:
        cliente = Cliente.objects.select_related("tipo_cliente").filter(usuario=request.user).first()
        if cliente:
            return cliente.tipo_cliente
    return TipoCliente.objects.select_related("lista_precio").filter(codigo="B2C").first()


def _precios(perfil):
    if not perfil:
        return {}
    return dict(PrecioProducto.objects.filter(lista_precio=perfil.lista_precio).values_list("producto_id", "precio_clp"))


def _estado_stock(p):
    if p.stock_disponible <= 0:
        return "nada", "Sin stock"
    if p.stock_disponible <= STOCK_BAJO:
        return "poco", f"Quedan {p.stock_disponible}"
    return "ok", "En stock"


@lru_cache(maxsize=1)
def _creditos():
    """Fotos referenciales descargadas con `descargar_imagenes` (autor y licencia). Sin archivo, todo usa la ilustración."""
    try:
        return json.loads((Path(settings.BASE_DIR) / "static" / "productos" / "creditos.json").read_text())
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _ilustraciones_ia():
    """Ilustraciones SVG creadas con IA por `generar_ilustraciones` (modelo que las creó)."""
    try:
        return json.loads((Path(settings.BASE_DIR) / "static" / "productos" / "ia" / "creditos.json").read_text())
    except (OSError, ValueError):
        return {}


def _propia(sku):
    """Imagen propia puesta a mano en static/productos/propias/<SKU>.(jpg|png|webp); tiene prioridad sobre todo lo demás."""
    carpeta = Path(settings.BASE_DIR) / "static" / "productos" / "propias"
    for ext in ("jpg", "jpeg", "png", "webp"):
        if (carpeta / f"{sku}.{ext}").exists():
            return f"productos/propias/{sku}.{ext}"
    return None


def _fila(p, precios):
    clase, texto = _estado_stock(p)
    propia = _propia(p.sku)
    credito = {"propia": True} if propia else _creditos().get(p.sku)
    return {"p": p, "precio": precios.get(p.producto_id), "stock_clase": clase, "stock_texto": texto,
            "foto": propia or (f"productos/{p.sku}.jpg" if credito else None), "credito": credito,
            "ilustracion_ia": f"productos/ia/{p.sku}.svg" if p.sku in _ilustraciones_ia() and not credito else None,
            "modelo_ia": _ilustraciones_ia().get(p.sku, {}).get("modelo")}


def _cliente(request):
    return Cliente.objects.select_related("tipo_cliente").filter(usuario=request.user).first() if request.user.is_authenticated else None


def listado(request):
    perfil = lista_del_visitante(request)
    precios = _precios(perfil)
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("categoria", "")
    temp = request.GET.get("temperatura", "")
    solo_stock = request.GET.get("stock") == "1"

    productos = Producto.objects.filter(activo=True).select_related("categoria__rango_temperatura").order_by("categoria__nombre", "nombre")
    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(sku__icontains=q) | Q(categoria__nombre__icontains=q))
    if entradas.es_entero(cat):
        productos = productos.filter(categoria_id=entradas.entero(cat))
    if entradas.es_entero(temp):
        productos = productos.filter(categoria__rango_temperatura_id=entradas.entero(temp))
    if solo_stock:
        productos = productos.filter(stock_disponible__gt=0)
    filas = [_fila(p, precios) for p in productos]
    return render(request, "catalogo/listado.html", {
        "filas": filas, "perfil": perfil, "q": q, "cat": cat, "temp": temp, "solo_stock": solo_stock,
        "con_aviso": avisos.minimos_pendientes(_cliente(request)) if _cliente(request) else {},
        "categorias": Categoria.objects.order_by("nombre"), "rangos": RangoTemperatura.objects.order_by("-temp_min_c"),
        "filtrado": bool(q or cat or temp or solo_stock)})


def detalle(request, producto_id):
    p = get_object_or_404(Producto.objects.select_related("categoria__rango_temperatura"), pk=producto_id, activo=True)
    perfil = lista_del_visitante(request)
    fila = _fila(p, _precios(perfil))
    similares = [_fila(s, _precios(perfil)) for s in Producto.objects.filter(activo=True, categoria=p.categoria).exclude(pk=p.pk).order_by("nombre")[:4]]
    cliente = _cliente(request)
    return render(request, "catalogo/detalle.html", {"fila": fila, "perfil": perfil, "similares": similares,
                                                     "con_aviso": avisos.minimos_pendientes(cliente) if cliente else {}})


@require_POST
def pedir_aviso(request):
    cliente = _cliente(request)
    if cliente is None:
        messages.error(request, "Ingresa con tu cuenta de cliente para pedir un aviso.")
        from cofrial.acceso import inicio_de
        return redirect(inicio_de(request.user) if request.user.is_authenticated else "/cuenta/entrar/")
    try:
        a = avisos.pedir(cliente, entradas.entero(request.POST.get("producto", 0)), entradas.entero(request.POST.get("cantidad", 0)))
        messages.success(request, f"Listo: te avisaremos cuando haya al menos {a.cantidad_minima} de {a.producto.nombre}.")
    except (avisos.ErrorAviso, ValueError) as e:
        messages.error(request, str(e) if isinstance(e, avisos.ErrorAviso) else "Indica una cantidad válida.")
    destino = request.POST.get("volver") or "/avisos/"
    seguro = url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()) and destino.startswith("/")
    return redirect(destino if seguro else "/avisos/")           # «/\\sitio.com» y «//sitio.com» no son del sitio: sin redirección abierta


def mis_avisos(request):
    cliente = _cliente(request)
    if cliente is None:
        if request.user.is_authenticated:           # una cuenta del equipo no tiene avisos de stock: va a su inicio, no al login (volvería a «/avisos/» en bucle)
            from cofrial.acceso import inicio_de
            messages.info(request, "Los avisos de stock son de las cuentas de clientes.")
            return redirect(inicio_de(request.user))
        return redirect("/cuenta/entrar/?next=/avisos/")
    lista = list(avisos.pendientes(cliente))
    for a in lista:
        a.disponible = a.producto.stock_disponible >= a.cantidad_minima
    return render(request, "catalogo/avisos.html", {"avisos": lista})


@require_POST
def quitar_aviso(request, aviso_id):
    cliente = _cliente(request)
    if cliente is not None:
        AvisoStock.objects.filter(pk=aviso_id, cliente=cliente, atendido_en__isnull=True).delete()
        messages.success(request, "Quitamos el aviso.")
    return redirect("/avisos/")


def _ficha(p):
    r = p.categoria.rango_temperatura
    return {"sku": p.sku, "nombre": p.nombre, "descripcion": p.descripcion, "categoria": p.categoria.nombre,
            "unidad": p.get_unidad_medida_display(), "disponible": p.stock_disponible > 0,
            "conservacion": {"rango": r.nombre, "temp_min_c": float(r.temp_min_c), "temp_max_c": float(r.temp_max_c)}}


def api_productos(request, sku=None):
    """Características de los productos por SKU, solo lectura y sin precios (dependen del perfil del cliente). Pensada para apps que consultan el SKU."""
    from django.http import Http404, JsonResponse
    base = Producto.objects.filter(activo=True).select_related("categoria__rango_temperatura")
    if sku is None:
        return JsonResponse({"productos": [_ficha(p) for p in base.order_by("sku")]}, json_dumps_params={"ensure_ascii": False})
    p = base.filter(sku__iexact=sku).first()
    if p is None:
        raise Http404("SKU no encontrado")
    r = JsonResponse(_ficha(p), json_dumps_params={"ensure_ascii": False})
    r["Access-Control-Allow-Origin"] = "*"
    return r


def api_asistente(request):
    """Asistente de IA de la tienda (ver catalogo/asistente.py): solo lectura, el contexto se arma en el servidor con los datos de ESTA sesión."""
    from django.conf import settings
    from django.http import Http404, JsonResponse
    from . import asistente
    if request.method != "POST" or not settings.ASISTENTE_ACTIVO:
        raise Http404
    try:
        datos = json.loads(request.body or b"{}")
        datos = datos if isinstance(datos, dict) else {}
    except ValueError:
        datos = {}

    def entero(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    clave = f"u{request.user.pk}" if request.user.is_authenticated else "ip" + request.META.get("REMOTE_ADDR", "?")
    try:
        r = asistente.responder(datos.get("mensaje"), _cliente(request), lista_del_visitante(request), clave,
                                producto_id=entero(datos.get("producto_id")), orden_id=entero(datos.get("orden_id")))
    except asistente.Rechazo as e:
        return JsonResponse({"respuesta": e.texto, "acciones": [], "origen": "regla"}, status=e.estado, json_dumps_params={"ensure_ascii": False})
    return JsonResponse(r, json_dumps_params={"ensure_ascii": False})
