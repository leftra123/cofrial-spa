"""Pantallas del administrador: reponer stock, crear cuentas y dar clave a cuentas existentes. Solo el rol admin (superusuario)."""
import logging
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from catalogo.models import Producto
from clientes import cuentas
from clientes.models import Cliente
from crm import servicios as crm

from . import servicios as s
from .forms import ClaveNuevaForm, ClienteCuentaForm, CuentaNuevaForm

log = logging.getLogger("cofrial.operacion")


def solo_admin(vista):
    """Anónimo → entrar; cualquier otra cuenta que no sea administradora → 403. Es la misma regla de /admin/ (superusuario)."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/cuenta/entrar/?next={request.path}")
        if crm.rol(request.user) != "admin":
            return render(request, "403.html", {"detalle": "Esta sección es solo del administrador."}, status=403)
        return vista(request, *args, **kwargs)
    return envoltura


@solo_admin
def indice(request):
    return render(request, "operacion/indice.html")


# ───────────────────────────── stock ─────────────────────────────

@solo_admin
def stock(request):
    q = request.GET.get("q", "").strip()[:80]
    filas = list(s.productos(q)[:s.FILAS_MAXIMAS + 1])
    return render(request, "operacion/stock.html", {"q": q, "filas": filas[:s.FILAS_MAXIMAS], "hay_mas": len(filas) > s.FILAS_MAXIMAS,
                                                    "maximo": s.REPOSICION_MAXIMA})


@require_POST
@solo_admin
def stock_sumar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    try:
        producto, listos = s.reponer(producto.pk, request.POST.get("cantidad", ""))
    except s.ErrorOperacion as e:
        messages.error(request, f"{producto.nombre}: {e}")
    else:
        mensaje = f"Stock repuesto: {producto.nombre} ahora tiene {producto.stock_disponible} {producto.unidad_medida}."
        if listos:
            mensaje += f" {listos} aviso{'s' if listos != 1 else ''} de clientes ya se pueden atender."
        messages.success(request, mensaje)
        log.info("Stock repuesto por %s: %s", request.user.username, producto.sku)
    q = request.POST.get("q", "").strip()[:80]
    return redirect("/operacion/stock/" + ("?" + urlencode({"q": q}) if q else ""))


# ───────────────────────────── cuentas ─────────────────────────────

TIPOS = [r for r, _ in cuentas.ROLES]


def _tipo(valor):
    """Un tipo de cuenta de la lista de roles; cualquier otra cosa se ignora (el parámetro viene de la URL)."""
    return valor if valor in TIPOS else ""


@solo_admin
def cuentas_lista(request):
    """Usuarios: una tarjeta por tipo con su cantidad (filtra la tabla y tiene su botón Agregar) y la tabla con búsqueda."""
    q = request.GET.get("q", "").strip()[:80]
    tipo = _tipo(request.GET.get("tipo", ""))
    conteos, otros, filas, hay_mas = s.usuarios_por_tipo(q, tipo)
    sin_cuenta = s.clientes_sin_cuenta()
    return render(request, "operacion/cuentas.html", {
        "q": q, "tipo": tipo, "tipo_nombre": dict(cuentas.ROLES).get(tipo, ""), "hay_mas": hay_mas, "otros": otros,
        "tarjetas": [{"rol": r, "nombre": n, "n": conteos[r], "activa": r == tipo} for r, n in cuentas.ROLES],
        "total": sum(conteos.values()) + otros,
        "cuentas": [{"u": u, "rol": s.ROTULOS.get(rol, rol), "nombre": s.nombre_de(u), "es_yo": u.pk == request.user.pk} for u, rol in filas],
        "sin_cuenta": list(sin_cuenta[:20]), "sin_cuenta_n": sin_cuenta.count()})


@sensitive_post_parameters("clave", "clave2")
@solo_admin
def cuenta_nueva(request):
    tipo = _tipo(request.GET.get("tipo", ""))                # /operacion/cuentas/nueva/?tipo=vendedor: el tipo viene elegido
    datos = None
    if request.method == "POST":
        datos = request.POST.copy()
        if tipo:
            datos["rol"] = tipo                                  # con tipo en la URL el rol no se elige: es ese
    form = CuentaNuevaForm(datos, tipo=tipo or None)
    if request.method == "POST" and form.is_valid():
        u = form.guardar()
        log.info("Cuenta creada por %s: %s (%s)", request.user.username, u.username, form.cleaned_data["rol"])
        messages.success(request, f"Cuenta {u.username} creada con el rol {dict(cuentas.ROLES)[form.cleaned_data['rol']]}.")
        return redirect("/operacion/cuentas/" + ("?" + urlencode({"tipo": tipo}) if tipo else ""))
    return render(request, "operacion/cuenta_nueva.html", {"form": form, "tipo": tipo, "tipo_nombre": dict(cuentas.ROLES).get(tipo, "")})


@sensitive_post_parameters("clave", "clave2")
@solo_admin
def cuenta_clave(request, pk):
    objetivo = get_object_or_404(get_user_model().objects.select_related("vendedor", "cliente__tipo_cliente").prefetch_related("groups"), pk=pk)
    form = ClaveNuevaForm(objetivo, request.POST or None)
    es_yo = objetivo.pk == request.user.pk
    if request.method == "POST" and form.is_valid():
        form.guardar()
        if es_yo:
            update_session_auth_hash(request, objetivo)             # cambiar la propia clave no cierra la sesión del administrador
        log.info("Clave asignada por %s a %s", request.user.username, objetivo.username)
        messages.success(request, f"Clave nueva guardada para {objetivo.username}." + (" Tu sesión sigue abierta." if es_yo else ""))
        return redirect("/operacion/cuentas/")
    return render(request, "operacion/cuenta_clave.html", {"form": form, "objetivo": objetivo, "es_yo": es_yo,
                                                           "rol": s.ROTULOS.get(s.rol_de(objetivo)), "nombre": s.nombre_de(objetivo)})


@sensitive_post_parameters("clave", "clave2")
@solo_admin
def cliente_cuenta(request, pk):
    """Cuenta del portal para un cliente que ya existe y no puede ingresar (p. ej. el que nace al ganar un prospecto). Se enlaza al
    cliente existente: no se crea otro ni se pide de nuevo el RUT ni la dirección."""
    cliente = get_object_or_404(Cliente.objects.select_related("tipo_cliente", "usuario", "vendedor"), pk=pk)
    ficha = f"/crm/clientes/{cliente.pk}/"
    if cliente.usuario_id:
        messages.warning(request, f"{cliente.nombre} ya tiene cuenta del portal: {cliente.usuario.username}.")
        return redirect(ficha)
    correo = cliente.email.strip().lower()
    inicial = {"usuario": correo} if correo and not get_user_model().objects.filter(username__iexact=correo).exists() else {}
    form = ClienteCuentaForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        try:
            u = form.guardar(cliente)
        except cuentas.ErrorCuenta as e:
            form.add_error(e.campo if e.campo in form.fields else None, str(e))
        else:
            log.info("Cuenta del portal creada por %s para el cliente %s: %s", request.user.username, cliente.pk, u.username)
            messages.success(request, f"Cuenta {u.username} creada para {cliente.nombre}. Ya puede ingresar al portal.")
            return redirect(ficha)
    return render(request, "operacion/cliente_cuenta.html", {"form": form, "c": cliente})
