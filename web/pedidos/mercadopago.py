"""Mercado Pago: Payment Brick embebido + consulta de pagos / webhook. Modo prueba en el proyecto académico."""
import json
import logging
import re
import uuid
from urllib import error, request

from django.conf import settings
from django.db import transaction

from . import documentos, servicios as s
from .documentos import ErrorDeNegocio
from .models import CheckoutPago

logger = logging.getLogger("cofrial.mercadopago")

API = "https://api.mercadopago.com"


class ErrorMercadoPago(ErrorDeNegocio):
    """Fallo al hablar con la API de Mercado Pago."""


def activo():
    return bool(getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")) and bool(getattr(settings, "MERCADOPAGO_PUBLIC_KEY", ""))


def emulador():
    """Sin credenciales de Mercado Pago, el carrito ofrece un emulador de su pago con tarjeta: mismo flujo (aprobado o rechazado, pedido y boleta
    solo si se aprueba), pero nada sale a internet y no se cobra. Con credenciales reales el emulador desaparece."""
    modo = str(getattr(settings, "MP_EMULADOR", "1")).strip().lower()
    if modo in ("0", "false", ""):
        return False
    return True if modo == "forzar" else not activo()


def forzar_emulador():
    """MP_EMULADOR=forzar: el emulador reemplaza al formulario real aunque haya credenciales (una defensa no debe depender de la red de Mercado Pago)."""
    return str(getattr(settings, "MP_EMULADOR", "1")).strip().lower() == "forzar"


def clave_publica():
    return getattr(settings, "MERCADOPAGO_PUBLIC_KEY", "") or ""


def _token():
    token = getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")
    if not token:
        raise ErrorMercadoPago("Mercado Pago no está configurado.")
    return token


def _mensaje_error_http(cuerpo_err, defecto):
    try:
        datos = json.loads(cuerpo_err)
    except json.JSONDecodeError:
        return defecto
    for causa in datos.get("cause") or []:
        if isinstance(causa, dict):
            desc = (causa.get("description") or "").strip()
            if "payer.email" in desc.lower() or "valid email" in desc.lower():
                return "Necesitamos un correo válido asociado a tu cuenta para pagar con Mercado Pago."
    msg = (datos.get("message") or datos.get("error") or "").strip()
    if msg.lower() == "internal_error":
        return (
            "Mercado Pago rechazó la operación con un error interno (HTTP 500, sin detalle). "
            "El carrito y la base no se modificaron. Vuelve a intentar en un minuto."
        )
    return msg or defecto


def email_cliente_mp(cliente):
    """Correo para el Brick. Con cuenta .test usa MERCADOPAGO_PAYER_EMAIL si está definido."""
    forzado = (getattr(settings, "MERCADOPAGO_PAYER_EMAIL", "") or "").strip()
    if forzado:
        return forzado
    try:
        return _resolver_email_mp(cliente, {})
    except ErrorMercadoPago:
        return ""


def _resolver_email_mp(cliente, payer):
    forzado = (getattr(settings, "MERCADOPAGO_PAYER_EMAIL", "") or "").strip()
    candidatos = [
        (payer or {}).get("email"),
        getattr(cliente, "email", None),
    ]
    u = getattr(cliente, "usuario", None)
    if u is not None:
        candidatos.extend([getattr(u, "email", None), getattr(u, "username", None)])
    for raw in candidatos:
        e = (raw or "").strip().lower()
        if not e or "@" not in e or e.startswith("@") or e.endswith("@"):
            continue
        local, _, dominio = e.partition("@")
        if not local or not dominio or "." not in dominio:
            continue
        if forzado and (dominio.endswith(".test") or e.endswith("@testuser.com")):
            return forzado
        if dominio.endswith(".test") or e.endswith("@testuser.com"):
            raise ErrorMercadoPago(
                "La cuenta de demostración usa un correo .test. Mercado Pago responde error interno si el pagador no es un usuario de prueba de tu aplicación. "
                "En el panel de desarrolladores crea un comprador de prueba y copia su correo en MERCADOPAGO_PAYER_EMAIL del archivo .env."
            )
        return e
    raise ErrorMercadoPago("Tu cuenta no tiene un correo válido para pagar. Actualiza tus datos de cliente.")


def _normalizar_payer(cliente, payer):
    """Completa el correo de la cuenta. El tipo de documento se deja como lo tokenizó el Brick."""
    payer = dict(payer or {})
    payer["email"] = _resolver_email_mp(cliente, payer)
    ident = dict(payer.get("identification") or {})
    tipo = (ident.get("type") or "").strip()
    numero = re.sub(r"[^0-9kK]", "", str(ident.get("number") or ""))
    if tipo and numero:
        payer["identification"] = {"type": tipo, "number": numero}
    else:
        payer.pop("identification", None)
    return payer


def _api(metodo, ruta, cuerpo=None, error_usuario=None, idempotencia=None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }
    if idempotencia:
        headers["X-Idempotency-Key"] = str(idempotencia)[:64]
    peticion = request.Request(f"{API}{ruta}", data=datos, method=metodo, headers=headers)
    defecto = error_usuario or "No pudimos procesar el pago con Mercado Pago. Intenta de nuevo."
    try:
        with request.urlopen(peticion, timeout=25) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except error.HTTPError as e:
        cuerpo_err = e.read().decode("utf-8", errors="replace")[:800]
        seguro = dict(cuerpo or {})
        if "token" in seguro:
            seguro["token"] = "…"
        logger.warning("Mercado Pago HTTP %s %s cuerpo=%s respuesta=%s", metodo, ruta, seguro, cuerpo_err)
        raise ErrorMercadoPago(_mensaje_error_http(cuerpo_err, defecto)) from e
    except error.URLError as e:
        logger.warning("Mercado Pago red %s: %s", ruta, e)
        raise ErrorMercadoPago("No hay conexión con Mercado Pago en este momento.") from e


def monto_a_cobrar(cliente, ctx):
    """Lo que se cobra en Mercado Pago. El institucional informa precios netos: el pago lleva el IVA."""
    neto = sum(ctx["precios"][i.producto_id] * i.cantidad for i in ctx["items"])
    if cliente.tipo_cliente.codigo == "B2B":
        return round(neto * (1 + documentos.IVA))
    return neto


def _crear_checkout(cliente, ctx, comprobante="boleta"):
    monto = monto_a_cobrar(cliente, ctx)
    checkout = CheckoutPago.objects.create(cliente=cliente, direccion=ctx["direccion"], numero_oc=ctx["numero_oc"],
                                           recibe_nombre=ctx["recibe"], comprobante=comprobante, monto_clp=monto, external_reference=f"TMP-{uuid.uuid4().hex}")
    checkout.external_reference = f"COF-{checkout.checkout_id:08d}"
    checkout.save(update_fields=["external_reference"])
    return checkout, monto


def _referencia_pago(pago):
    return str(pago.get("id") or "")


DETALLES_DE_RECHAZO = {
    "cc_rejected_insufficient_amount": "la tarjeta no tiene fondos suficientes.",
    "cc_rejected_other_reason": "el banco rechazó la tarjeta.",
    "cc_rejected_bad_filled_card_number": "revisa el número de la tarjeta.",
    "cc_rejected_bad_filled_date": "revisa la fecha de vencimiento.",
    "cc_rejected_bad_filled_security_code": "revisa el código de seguridad.",
    "cc_rejected_call_for_authorize": "debes autorizar el pago con tu banco.",
}


@transaction.atomic
def _aplicar_respuesta_pago(checkout, pago, fallar_si_rechazado=True):
    checkout = CheckoutPago.objects.select_for_update().get(pk=checkout.pk)
    if checkout.estado == "completado":
        return checkout
    checkout.payment_id = _referencia_pago(pago)
    estado = (pago.get("status") or "").lower()
    if estado == "approved":
        monto_mp = int(float(pago.get("transaction_amount") or 0))
        if monto_mp and abs(monto_mp - checkout.monto_clp) > 1:
            logger.warning("Monto MP %s distinto al checkout %s", monto_mp, checkout.monto_clp)
        ordenes = s.generar_ordenes(checkout.cliente, checkout.direccion_id, checkout.numero_oc,
                                    cobrar_b2c_al_crear=False, checkout_pago=checkout, recibe=checkout.recibe_nombre, comprobante=checkout.comprobante)
        ref = checkout.payment_id
        for orden in ordenes:
            if checkout.comprobante == "factura":
                documentos.cobrar_factura_contado(orden, medio="mercadopago", referencia=ref)
            else:
                documentos.cobrar_b2c(orden, medio="mercadopago", referencia=ref)
        checkout.estado = "completado"
        checkout.primera_orden_id = ordenes[0].pk
        checkout.save(update_fields=["estado", "payment_id", "primera_orden_id"])
        return checkout
    if estado in ("rejected", "cancelled"):
        checkout.estado = "fallido"
        checkout.save(update_fields=["estado", "payment_id"])
        if fallar_si_rechazado:
            codigo = pago.get("status_detail") or ""
            detalle = DETALLES_DE_RECHAZO.get(codigo) or codigo.replace("_", " ")
            raise ErrorMercadoPago(f"El pago no fue aprobado{(': ' + detalle) if detalle else '.'}")
        return checkout
    checkout.save(update_fields=["payment_id"])
    if fallar_si_rechazado:
        raise ErrorMercadoPago("Tu pago quedó pendiente. Cuando Mercado Pago lo confirme, crearemos tu pedido.")
    return checkout


@transaction.atomic
def pagar_con_brick(cliente, direccion_id, form_data, comprobante=None, giro="", recibe=""):
    """Valida el carrito, crea el pago en MP con el token del Brick y materializa la orden si queda approved."""
    if not isinstance(form_data, dict):
        raise ErrorMercadoPago("Datos de pago incompletos.")
    comprobante = s.elegir_comprobante(cliente, comprobante, giro)
    ctx = s._contexto_desde_carrito(cliente, direccion_id, "", recibe)
    checkout, monto = _crear_checkout(cliente, ctx, comprobante)
    payer = _normalizar_payer(cliente, form_data.get("payer"))
    cuerpo = {
        "transaction_amount": int(monto),
        "token": form_data.get("token"),
        "description": f"Compra Cofrial {checkout.external_reference}",
        "installments": int(form_data.get("installments") or 1),
        "payment_method_id": form_data.get("payment_method_id"),
        "external_reference": checkout.external_reference,
        "payer": payer,
    }
    if form_data.get("issuer_id"):
        emisor = str(form_data["issuer_id"])
        cuerpo["issuer_id"] = int(emisor) if emisor.isdigit() else form_data["issuer_id"]
    if not cuerpo["token"]:
        raise ErrorMercadoPago("No recibimos los datos de la tarjeta. Intenta de nuevo.")
    pago = _api("POST", "/v1/payments", cuerpo, error_usuario="Mercado Pago rechazó el pago. Revisa los datos de la tarjeta.",
                idempotencia=checkout.external_reference)
    return _aplicar_respuesta_pago(checkout, pago)


def obtener_pago(payment_id):
    return _api("GET", f"/v1/payments/{payment_id}")


def checkout_por_referencia(external_reference):
    if not external_reference:
        return None
    return CheckoutPago.objects.filter(external_reference=external_reference).first()


@transaction.atomic
def procesar_pago_mp(payment_id):
    """Consulta el pago en MP y, si está approved, materializa órdenes (webhook / retorno)."""
    pago = obtener_pago(payment_id)
    checkout = checkout_por_referencia(pago.get("external_reference") or "")
    if checkout is None:
        logger.info("Pago MP %s sin checkout local (ref=%s)", payment_id, pago.get("external_reference"))
        return None
    try:
        return _aplicar_respuesta_pago(checkout, pago, fallar_si_rechazado=False)
    except ErrorMercadoPago:
        checkout.refresh_from_db()
        return checkout


def procesar_notificacion_webhook(cuerpo, payment_id_query=None):
    payment_id = payment_id_query
    if cuerpo:
        if isinstance(cuerpo, bytes):
            cuerpo = cuerpo.decode("utf-8", errors="replace")
        if cuerpo.strip():
            try:
                datos = json.loads(cuerpo) if isinstance(cuerpo, str) else cuerpo
            except json.JSONDecodeError:
                datos = {}
            if isinstance(datos.get("data"), dict):
                payment_id = payment_id or datos["data"].get("id")
            payment_id = payment_id or datos.get("id")
    if not payment_id:
        return None
    return procesar_pago_mp(str(payment_id))


# Resultados del emulador, con los mismos nombres de titular que usa Mercado Pago en sus tarjetas de prueba.
TITULARES_EMULADOR = {
    "APRO": ("approved", "accredited", "Pago aprobado"),
    "FUND": ("rejected", "cc_rejected_insufficient_amount", "Fondos insuficientes"),
    "OTHE": ("rejected", "cc_rejected_other_reason", "Rechazado por error general"),
}


@transaction.atomic
def pagar_emulado(cliente, direccion_id, titular, comprobante=None, giro="", recibe=""):
    """Igual que `pagar_con_brick`, pero la respuesta de Mercado Pago la fabrica el emulador según el titular elegido. Todo lo demás es lo de siempre:
    el carrito se valida, se crea el `CheckoutPago` y solo un pago aprobado genera la orden, el documento pagado y el descuento de stock."""
    if not emulador():
        raise ErrorMercadoPago("El emulador de pagos no está disponible.")
    if titular not in TITULARES_EMULADOR:
        raise ErrorMercadoPago("Elige cómo quieres que responda el pago de prueba.")
    comprobante = s.elegir_comprobante(cliente, comprobante, giro)
    ctx = s._contexto_desde_carrito(cliente, direccion_id, "", recibe)
    checkout, monto = _crear_checkout(cliente, ctx, comprobante)
    estado, detalle, _ = TITULARES_EMULADOR[titular]
    pago = {"id": f"EMU-{uuid.uuid4().hex[:12]}", "status": estado, "status_detail": detalle, "transaction_amount": monto,
            "external_reference": checkout.external_reference}
    return _aplicar_respuesta_pago(checkout, pago)
