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
from crm import servicios as crm

from . import servicios as s
from .forms import ClaveNuevaForm, CuentaNuevaForm

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

@solo_admin
def cuentas_lista(request):
    q = request.GET.get("q", "").strip()[:80]
    filas = list(s.cuentas_con_rol(q)[:s.FILAS_MAXIMAS + 1])
    cuentas_ = [{"u": u, "rol": s.ROTULOS.get(s.rol_de(u), s.rol_de(u)), "nombre": s.nombre_de(u), "es_yo": u.pk == request.user.pk}
                for u in filas[:s.FILAS_MAXIMAS]]
    return render(request, "operacion/cuentas.html", {"q": q, "cuentas": cuentas_, "hay_mas": len(filas) > s.FILAS_MAXIMAS})


@sensitive_post_parameters("clave", "clave2")
@solo_admin
def cuenta_nueva(request):
    form = CuentaNuevaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        u = form.guardar()
        log.info("Cuenta creada por %s: %s (%s)", request.user.username, u.username, form.cleaned_data["rol"])
        messages.success(request, f"Cuenta {u.username} creada con el rol {dict(cuentas.ROLES)[form.cleaned_data['rol']]}.")
        return redirect("/operacion/cuentas/")
    return render(request, "operacion/cuenta_nueva.html", {"form": form})


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
