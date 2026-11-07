"""Vistas del panel común: una lista y un formulario para todas las tablas de tablas.py. Solo el rol admin."""
import logging

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q, RestrictedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .servicios import FILAS_MAXIMAS
from .tablas import GRUPOS, TABLAS, formulario_de
from .vistas import solo_admin

log = logging.getLogger("cofrial.operacion")


def _tabla(slug):
    try:
        return TABLAS[slug]
    except KeyError:
        raise Http404


def _no_permitido(request, texto):
    return render(request, "403.html", {"detalle": texto}, status=403)


def _objeto(tabla, pk):
    """Un pk que no calza con el tipo de la clave (texto en una clave numérica) es un 404, no un error."""
    try:
        return get_object_or_404(tabla.modelo, pk=pk)
    except (TypeError, ValueError):
        raise Http404


def _valor(fila, atributo):
    valor = atributo(fila) if callable(atributo) else fila
    if not callable(atributo):
        for parte in atributo.split("."):
            valor = getattr(valor, parte, None)
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    return "—" if valor in (None, "") else valor


@solo_admin
def indice(request):
    grupos = [{"nombre": g, "tablas": [{"t": t, "n": t.modelo.objects.count()} for t in TABLAS.values() if t.grupo == g]} for g in GRUPOS]
    return render(request, "operacion/datos.html", {"grupos": [g for g in grupos if g["tablas"]]})


@solo_admin
def lista(request, slug):
    tabla = _tabla(slug)
    q = request.GET.get("q", "").strip()[:80]
    qs = tabla.modelo.objects.select_related(*tabla.relacionados).order_by(*tabla.orden)
    for palabra in q.split():
        filtro = Q()
        for campo in tabla.busqueda:
            filtro |= Q(**{f"{campo}__icontains": palabra})
        qs = qs.filter(filtro)
    filas = list(qs[:FILAS_MAXIMAS + 1])
    return render(request, "operacion/tabla.html", {
        "tabla": tabla, "q": q, "hay_mas": len(filas) > FILAS_MAXIMAS, "columnas": [c for c, _ in tabla.columnas],
        "filas": [{"pk": f.pk, "celdas": [_valor(f, a) for _, a in tabla.columnas]} for f in filas[:FILAS_MAXIMAS]]})


def _formulario(request, tabla, objeto=None):
    Formulario = formulario_de(tabla)
    form = Formulario(request.POST or None, instance=objeto)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            nuevo = form.save(commit=False)
            if tabla.al_guardar:
                tabla.al_guardar(form, nuevo)
            nuevo.save()
            form.save_m2m()
        log.info("%s %s: %s por %s", "Editado" if objeto else "Creado", tabla.slug, nuevo.pk, request.user.username)
        messages.success(request, f"{tabla.titulo}: «{nuevo}» guardado.")
        return redirect(f"/operacion/datos/{tabla.slug}/")
    return render(request, "operacion/fila.html", {"tabla": tabla, "form": form, "objeto": objeto})


@solo_admin
def nuevo(request, slug):
    tabla = _tabla(slug)
    if not tabla.crear:
        return _no_permitido(request, f"{tabla.titulo}: esta tabla no admite altas desde aquí.")
    return _formulario(request, tabla)


@solo_admin
def fila(request, slug, pk):
    tabla = _tabla(slug)
    if not tabla.editar:
        return _no_permitido(request, f"{tabla.titulo}: esta tabla es de solo lectura.")
    return _formulario(request, tabla, _objeto(tabla, pk))


@require_POST
@solo_admin
def borrar(request, slug, pk):
    tabla = _tabla(slug)
    if not tabla.borrar:
        return _no_permitido(request, f"{tabla.titulo}: esta tabla no admite borrados.")
    objeto = _objeto(tabla, pk)
    motivo = tabla.protegida(objeto) if tabla.protegida else ""
    if motivo:
        messages.error(request, f"No se puede borrar «{objeto}»: {motivo}")
        return redirect(f"/operacion/datos/{slug}/")
    nombre = str(objeto)
    try:
        with transaction.atomic():
            objeto.delete()
    except (ProtectedError, RestrictedError, IntegrityError):
        messages.error(request, f"No se puede borrar «{nombre}»: otros datos lo están usando.")
    else:
        log.info("Borrado %s: %s por %s", slug, pk, request.user.username)
        messages.success(request, f"{tabla.titulo}: «{nombre}» borrado.")
    return redirect(f"/operacion/datos/{slug}/")
