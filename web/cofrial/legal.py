"""Páginas legales (privacidad, términos, devoluciones, cookies, licencias) y los derechos del titular sobre sus datos:
descargarlos, eliminar la cuenta y pedir rectificación, oposición o bloqueo (Ley 21.719) con su plazo de respuesta. Cofrial SpA es el caso de estudio de un prototipo académico: los textos describen lo que
este sistema hace de verdad y no inventan datos de contacto ni certificaciones de la empresa real."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from functools import wraps

from django.contrib.auth import logout
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalogo.models import AvisoStock
from clientes.cuentas_demo import USUARIOS as CUENTAS_DEMO
from clientes.models import AceptacionLegal, Direccion, SolicitudDerecho, Vendedor
from crm.models import Requerimiento
from pedidos.models import Carrito, Orden, OrdenItem
from pedidos import servicios as pedidos_s
from pedidos.views import solo_clientes

# Versión de los términos y la política de privacidad. Si el texto cambia en algo de fondo, se cambia la fecha:
# cada aceptación guarda la versión que la persona vio.
VERSION = "2026-11-13"

PAGINAS = {
    "privacidad": "Política de privacidad",
    "terminos": "Términos y condiciones",
    "devoluciones": "Devoluciones y reembolsos",
    "cookies": "Cookies y almacenamiento del navegador",
    "licencias": "Créditos y licencias",
}


def _fotos_de_commons():
    """Créditos de las fotos de Wikimedia Commons (las descarga `manage.py descargar_imagenes`); varias licencias exigen nombrar al autor."""
    try:
        datos = json.loads((Path(settings.BASE_DIR) / "static" / "productos" / "creditos.json").read_text())
    except (OSError, ValueError):
        return []
    return [{"sku": sku, **c} for sku, c in sorted(datos.items())]


def pagina(request, nombre):
    if nombre not in PAGINAS:
        raise Http404
    contexto = {"titulo_legal": PAGINAS[nombre], "version": VERSION, "paginas_legales": PAGINAS}
    if nombre == "licencias":
        contexto["fotos"] = _fotos_de_commons()
    return render(request, f"legal/{nombre}.html", contexto)


def _datos_de(cliente):
    """Todo lo que el sistema guarda de un cliente, en un formato que se puede leer y llevar a otro lado (portabilidad)."""
    u = cliente.usuario
    ordenes = []
    for o in Orden.objects.filter(direccion__cliente=cliente).select_related("estado_orden", "direccion__comuna").order_by("orden_id"):
        items = [{"sku": i.producto.sku, "producto": i.producto.nombre, "cantidad": i.cantidad, "precio_unitario_clp": i.precio_unitario_clp,
                  "cantidad_rechazada": i.cantidad_rechazada, "motivo_rechazo": i.motivo_rechazo}
                 for i in OrdenItem.objects.filter(orden=o).select_related("producto")]
        ordenes.append({"orden": o.orden_id, "creada_en": o.creada_en.isoformat(), "estado": o.estado_orden.nombre,
                        "comprobante": o.comprobante, "numero_oc": o.numero_oc, "recibe": o.recibe_nombre,
                        "direccion": f"{o.direccion.calle_numero}, {o.direccion.comuna.nombre}", "items": items})
    return {
        "generado_en": timezone.now().isoformat(),
        "nota": "Copia de los datos personales que Cofrial guarda de tu cuenta (prototipo académico INACAP).",
        "cuenta": {"correo": u.email if u else cliente.email, "creada_en": u.date_joined.isoformat() if u else None,
                   "ultimo_ingreso": u.last_login.isoformat() if u and u.last_login else None},
        "cliente": {"tipo": cliente.tipo_cliente.codigo, "rut": cliente.rut, "nombre": cliente.nombre, "correo": cliente.email,
                    "telefono": cliente.telefono, "giro": cliente.giro, "creado_en": cliente.creado_en.isoformat()},
        "direcciones": [{"direccion": d.calle_numero, "comuna": d.comuna.nombre, "referencia": d.referencia, "principal": d.es_principal,
                         "lat": d.lat, "long": d.long} for d in Direccion.objects.filter(cliente=cliente).select_related("comuna")],
        "pedidos": ordenes,
        "consultas_y_reclamos": [{"asunto": r.asunto, "descripcion": r.descripcion, "estado": r.estado, "creado_en": r.creado_en.isoformat(),
                                  "categoria": str(r.categoria_requerimiento or "")}
                                 for r in Requerimiento.objects.filter(cliente=cliente).select_related("categoria_requerimiento")],
        "avisos_de_stock": [{"producto": a.producto.nombre, "cantidad_minima": a.cantidad_minima, "creado_en": a.creado_en.isoformat(),
                             "atendido_en": a.atendido_en.isoformat() if a.atendido_en else None}
                            for a in AvisoStock.objects.filter(cliente=cliente).select_related("producto")],
        "aceptaciones_de_terminos": [{"version": a.version, "aceptado_en": a.aceptado_en.isoformat(), "ip": a.ip}
                                     for a in AceptacionLegal.objects.filter(usuario=u)] if u else [],
    }


def _solicitudes_de(usuario):
    return [{"numero": x.solicitud_id, "tipo": x.get_tipo_display(), "detalle": x.detalle, "recibida_en": x.creada_en.isoformat(),
             "vence_el": x.vence_el.isoformat(), "estado": x.get_estado_display(), "respuesta": x.respuesta,
             "respondida_en": x.respondida_en.isoformat() if x.respondida_en else None}
            for x in SolicitudDerecho.objects.filter(usuario=usuario)]


def _datos_de_equipo(u):
    """Lo que el sistema guarda de una persona del equipo. Lo que registra en su trabajo (interacciones, despachos) es de los clientes y de la empresa."""
    from crm import servicios as crm
    v = Vendedor.objects.filter(usuario=u).first()
    return {
        "generado_en": timezone.now().isoformat(),
        "nota": "Copia de los datos personales que Cofrial guarda de tu cuenta del equipo (prototipo académico INACAP).",
        "cuenta": {"usuario": u.username, "correo": u.email, "nombre": u.get_full_name(), "rol": crm.rol(u),
                   "grupos": list(u.groups.values_list("name", flat=True)), "creada_en": u.date_joined.isoformat(),
                   "ultimo_ingreso": u.last_login.isoformat() if u.last_login else None},
        "ficha_de_vendedor": {"nombre": v.nombre, "telefono": v.telefono, "activo": v.activo} if v else None,
        "aceptaciones_de_terminos": [{"version": a.version, "aceptado_en": a.aceptado_en.isoformat(), "ip": a.ip}
                                     for a in AceptacionLegal.objects.filter(usuario=u)],
        "solicitudes_sobre_mis_datos": _solicitudes_de(u),
    }


def con_sesion(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/cuenta/entrar/?next={request.path}")
        return vista(request, *args, **kwargs)
    return envoltura


# Lo que se pide por solicitud. El cliente resuelve solo el acceso, la portabilidad y la supresión con los botones de «Mis datos»;
# el equipo no elimina su propia cuenta (la relación laboral la administra la empresa), así que la supresión la pide.
TIPOS_CLIENTE = ("rectificacion", "oposicion", "bloqueo")
TIPOS_EQUIPO = ("rectificacion", "oposicion", "bloqueo", "supresion")
AYUDA_TIPOS = {
    "rectificacion": "Corregir un dato que está mal o incompleto, como tu nombre, teléfono o una dirección.",
    "oposicion": "Que dejemos de usar tus datos para algo que no es necesario para atender tus pedidos.",
    "bloqueo": "Que suspendamos el uso de tus datos mientras resolvemos otra solicitud tuya.",
    "supresion": "Que borremos tus datos personales. Se conserva lo que la ley obliga a guardar.",
}


def _contexto_solicitudes(usuario, tipos):
    nombres = dict(SolicitudDerecho.TIPOS)
    return {"solicitudes": SolicitudDerecho.objects.filter(usuario=usuario),
            "tipos_solicitud": [(t, nombres[t], AYUDA_TIPOS[t]) for t in tipos]}


def _pedidos_abiertos(cliente):
    return Orden.objects.filter(direccion__cliente=cliente, estado_orden__es_final=False).count()


@con_sesion
def mis_datos(request):
    """La misma dirección para clientes y equipo: el cliente la ve en la tienda; el equipo, en el panel interno (menú lateral)."""
    u = request.user
    aceptacion = AceptacionLegal.objects.filter(usuario=u).order_by("-aceptado_en").first()
    cliente = pedidos_s.cliente_de(u)
    if cliente is None:
        return render(request, "cuenta/mis_datos_equipo.html", {
            "vendedor": Vendedor.objects.filter(usuario=u).first(), "aceptacion": aceptacion, **_contexto_solicitudes(u, TIPOS_EQUIPO)})
    return render(request, "cuenta/mis_datos.html", {
        "cliente": cliente, "abiertos": _pedidos_abiertos(cliente), "es_demo": u.username in CUENTAS_DEMO,
        "aceptacion": aceptacion, "version": VERSION, **_contexto_solicitudes(u, TIPOS_CLIENTE)})


@require_POST
@con_sesion
def solicitar(request):
    """Recibe una solicitud de derechos y le da número y plazo. Una abierta por tipo, para que un doble clic no la duplique."""
    u = request.user
    tipos = TIPOS_EQUIPO if pedidos_s.cliente_de(u) is None else TIPOS_CLIENTE
    tipo, detalle = request.POST.get("tipo", ""), request.POST.get("detalle", "").strip()
    if tipo not in tipos:
        messages.error(request, "Elige qué quieres pedir.")
    elif not 10 <= len(detalle) <= 2000:
        messages.error(request, "Cuéntanos qué necesitas en al menos 10 caracteres (máximo 2000).")
    elif SolicitudDerecho.objects.filter(usuario=u, tipo=tipo, estado="recibida").exists():
        messages.error(request, "Ya tienes una solicitud de ese tipo en curso. Puedes ver su plazo más abajo.")
    else:
        x = SolicitudDerecho.objects.create(usuario=u, tipo=tipo, detalle=detalle)
        messages.success(request, f"Recibimos tu solicitud N.º {x.solicitud_id} ({x.get_tipo_display().lower()}). "
                                  f"Te responderemos aquí a más tardar el {x.vence_el:%d/%m/%Y}.")
        return redirect("/cuenta/mis-datos/#md-solicitudes")
    return redirect("/cuenta/mis-datos/#md-solicitar")


@con_sesion
def descargar_datos(request):
    cliente = pedidos_s.cliente_de(request.user)
    datos = _datos_de_equipo(request.user) if cliente is None else {**_datos_de(cliente), "solicitudes_sobre_mis_datos": _solicitudes_de(request.user)}
    cuerpo = json.dumps(datos, ensure_ascii=False, indent=2)
    r = HttpResponse(cuerpo, content_type="application/json; charset=utf-8")
    r["Content-Disposition"] = f'attachment; filename="mis-datos-cofrial-{timezone.localdate():%Y%m%d}.json"'
    r["Cache-Control"] = "no-store"
    return r


@require_POST
@solo_clientes
def eliminar_cuenta(request, cliente):
    """Eliminación a pedido del titular. Se borra o reemplaza lo que identifica a la persona y se cierra el acceso; se conservan
    los pedidos y los documentos tributarios (la ley exige guardarlos) con el RUT, y la constancia de los términos aceptados.
    Se pide la clave otra vez para que nadie lo haga desde una sesión ajena que quedó abierta."""
    u = request.user
    if u.username in CUENTAS_DEMO:
        messages.error(request, "Las cuentas de demostración no se pueden eliminar: las usa la defensa del prototipo.")
        return redirect("mis_datos")
    if not u.check_password(request.POST.get("clave", "")):
        messages.error(request, "La clave no es correcta. No se eliminó nada.")
        return redirect("mis_datos")
    if _pedidos_abiertos(cliente):
        messages.error(request, "Tienes pedidos en curso. Cuando terminen (entregados o cancelados) podrás eliminar la cuenta.")
        return redirect("mis_datos")
    marca = f"eliminado-{u.pk}@eliminado.invalid"
    with transaction.atomic():
        AvisoStock.objects.filter(cliente=cliente).delete()
        Carrito.objects.filter(cliente=cliente).delete()
        Direccion.objects.filter(cliente=cliente).update(calle_numero="(dirección eliminada)", referencia="", lat=None, long=None)
        Orden.objects.filter(direccion__cliente=cliente).update(recibe_nombre="")
        cliente.nombre, cliente.email, cliente.telefono = "Cuenta eliminada", marca, ""
        cliente.save(update_fields=["nombre", "email", "telefono"])
        u.username = u.email = marca
        u.first_name = u.last_name = ""
        u.is_active = False
        u.set_unusable_password()
        u.save()
    logout(request)
    messages.success(request, "Tu cuenta quedó eliminada. Conservamos solo lo que la ley tributaria exige guardar de tus compras.")
    return redirect("/")
