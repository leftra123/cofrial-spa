"""Documentos tributarios simulados y cobranza (RN-17 a RN-22 del informe, sección de canales).

Flujo B2C: al comprar se paga y se emite la boleta. Flujo B2B: al despachar sale la guía; la factura se emite después
de la entrega y se paga a crédito (30 días). Nada se conecta al SII: se guarda tipo, folio, monto, fechas y pagos.
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max, Sum
from django.utils import timezone

from .models import Documento, Orden, Pago

IVA = 0.19
COBRABLES = ("boleta", "factura")        # los documentos contra los que se registran pagos y notas de crédito


class ErrorDeNegocio(Exception):
    """Misma forma que pedidos.servicios.ErrorDeNegocio (se redefine aquí para no importar en círculo)."""

    def __init__(self, *mensajes):
        super().__init__(" ".join(mensajes))
        self.mensajes = list(mensajes)


def _clp(valor):
    return "$" + f"{valor:,}".replace(",", ".")


def _neto_orden(orden):
    return sum(i.cantidad * i.precio_unitario_clp for i in orden.ordenitem_set.all())


def monto_con_iva(orden):
    """Los precios B2B son netos (se suma el IVA); los B2C ya lo incluyen."""
    neto = _neto_orden(orden)
    return round(neto * (1 + IVA)) if orden.direccion.cliente.tipo_cliente.codigo == "B2B" else neto


def _emitir(orden, tipo, monto=None, vence_en=None, referencia=None, motivo=""):
    """Crea el documento con el siguiente folio de su tipo. Si dos emisiones simultáneas eligen el mismo folio, la restricción
    única lo rechaza y se reintenta con el siguiente."""
    for _ in range(5):
        folio = (Documento.objects.filter(tipo=tipo).aggregate(m=Max("folio"))["m"] or 0) + 1
        try:
            with transaction.atomic():
                return Documento.objects.create(tipo=tipo, folio=folio, orden=orden, monto_clp=monto, vence_en=vence_en,
                                                referencia=referencia, motivo=motivo)
        except IntegrityError:
            if tipo != "nota_credito" and Documento.objects.filter(orden=orden, tipo=tipo).exists():
                raise                                                  # no es un choque de folio: la orden ya tiene ese documento
    raise ErrorDeNegocio("No se pudo asignar el folio del documento; intenta de nuevo.")


# ------------------------------------------------------------------------------------ saldos
def saldos(documentos):
    """{documento_id: saldo} = monto - pagos - notas de crédito que lo rebajan. Dos consultas para toda la lista."""
    ids = [d.pk for d in documentos if d.tipo in COBRABLES]
    pagado = dict(Pago.objects.filter(documento_id__in=ids).values_list("documento_id").annotate(t=Sum("monto_clp")))
    credito = dict(Documento.objects.filter(referencia_id__in=ids, tipo="nota_credito").values_list("referencia_id").annotate(t=Sum("monto_clp")))
    return {d.pk: d.monto_clp - pagado.get(d.pk, 0) - credito.get(d.pk, 0) for d in documentos if d.tipo in COBRABLES}


def saldo(documento):
    return saldos([documento]).get(documento.pk)


def _rebajado(documento):
    return Documento.objects.filter(referencia=documento, tipo="nota_credito").aggregate(t=Sum("monto_clp"))["t"] or 0


def _estado_pago(documento, saldo_, rebajado, hoy):
    """pagado, anulado, vencido o por_cobrar; None para la guía y la nota de crédito, que no se cobran."""
    if saldo_ is None:
        return None
    if saldo_ > 0:
        return "vencido" if documento.vence_en and documento.vence_en < hoy else "por_cobrar"
    return "anulado" if rebajado >= documento.monto_clp else "pagado"


def _con_estado(docs):
    s = saldos(docs)
    ids = [d.pk for d in docs if d.tipo in COBRABLES]
    notas = dict(Documento.objects.filter(referencia_id__in=ids, tipo="nota_credito").values_list("referencia_id").annotate(t=Sum("monto_clp")))
    hoy = timezone.localdate()
    for d in docs:
        d.saldo = s.get(d.pk)
        d.estado_pago = _estado_pago(d, d.saldo, notas.get(d.pk, 0), hoy)
    return docs


def documentos_de_orden(orden):
    return _con_estado(list(Documento.objects.filter(orden=orden).select_related("referencia").order_by("emitido_en", "documento_id")))


def documentos_de_cliente(cliente):
    return _con_estado(list(Documento.objects.filter(orden__direccion__cliente=cliente).select_related("referencia", "orden")
                            .order_by("-emitido_en", "-documento_id")))


# ------------------------------------------------------------------------------------ emisión
@transaction.atomic
def emitir_guia(orden):
    """RN-17: al despachar sale la guía de despacho, que ampara el traslado. No cobra nada y es única por orden."""
    return Documento.objects.filter(orden=orden, tipo="guia_despacho").first() or _emitir(orden, "guia_despacho")


@transaction.atomic
def cobrar_b2c(orden):
    """RN-18: el cliente B2C paga al comprar (Webpay simulado): se emite la boleta y queda pagada."""
    monto = monto_con_iva(orden)
    boleta = _emitir(orden, "boleta", monto)
    Pago.objects.create(documento=boleta, monto_clp=monto, medio="webpay", referencia=f"AUT-{orden.orden_id:06d}")
    return boleta


@transaction.atomic
def emitir_factura(orden):
    """RN-19: la factura se emite a una orden B2B ya entregada, una sola vez, con vencimiento según el crédito del cliente."""
    orden = Orden.objects.select_for_update(of=("self",)).select_related("estado_orden", "direccion__cliente__tipo_cliente").get(pk=orden.pk)
    tipo = orden.direccion.cliente.tipo_cliente
    if tipo.codigo != "B2B":
        raise ErrorDeNegocio("Solo los clientes institucionales reciben factura; el público recibe boleta.")
    if orden.estado_orden.nombre != "Entregada":
        raise ErrorDeNegocio(f"La orden está «{orden.estado_orden.nombre}»; la factura se emite cuando ya fue entregada.")
    if Documento.objects.filter(orden=orden, tipo="factura").exists():
        raise ErrorDeNegocio("Esta orden ya tiene factura.")
    return _emitir(orden, "factura", monto_con_iva(orden), vence_en=timezone.localdate() + timedelta(days=tipo.dias_credito))


# ------------------------------------------------------------------------------------ pagos y notas de crédito
def _cobrable(documento_id):
    documento = Documento.objects.select_for_update().filter(pk=documento_id, tipo__in=COBRABLES).first()
    if documento is None:
        raise ErrorDeNegocio("Documento no encontrado o no admite pagos.")
    return documento


@transaction.atomic
def registrar_pago(documento_id, monto, medio, referencia=""):
    """RN-20: un pago no puede superar el saldo pendiente del documento."""
    documento = _cobrable(documento_id)
    if medio not in dict(Pago.MEDIOS) or medio == "devolucion":
        raise ErrorDeNegocio("Elige un medio de pago válido.")
    pendiente = saldo(documento)
    if monto < 1:
        raise ErrorDeNegocio("El monto del pago debe ser mayor que cero.")
    if monto > pendiente:
        raise ErrorDeNegocio(f"El pago supera el saldo pendiente de {_clp(pendiente)}.")
    return Pago.objects.create(documento=documento, monto_clp=monto, medio=medio, referencia=(referencia or "").strip()[:60])


@transaction.atomic
def emitir_nota_credito(documento_id, monto, motivo):
    """RN-21: la nota de crédito rebaja un documento (reclamo, cadena de frío rota, cancelación). Exige motivo y no puede
    superar lo que aún no se ha rebajado. Si el cliente ya había pagado, el excedente se le devuelve en el mismo acto."""
    documento = _cobrable(documento_id)
    motivo = (motivo or "").strip()[:200]
    if not motivo:
        raise ErrorDeNegocio("Indica el motivo de la nota de crédito.")
    disponible = documento.monto_clp - _rebajado(documento)
    if monto < 1 or monto > disponible:
        raise ErrorDeNegocio(f"El monto debe estar entre $1 y {_clp(disponible)}." if disponible else "Este documento ya está rebajado por completo.")
    nota = _emitir(documento.orden, "nota_credito", monto, referencia=documento, motivo=motivo)
    excedente = -saldo(documento)
    if excedente > 0:                                                  # ya estaba pagado: se devuelve lo que sobra
        Pago.objects.create(documento=documento, monto_clp=-excedente, medio="devolucion", referencia=f"NC-{nota.folio}")
    return nota


def anular_por_cancelacion(orden):
    """Cancelar una orden con boleta o factura emitida la anula completa con una nota de crédito (RN-21)."""
    for doc in Documento.objects.filter(orden=orden, tipo__in=COBRABLES):
        disponible = doc.monto_clp - _rebajado(doc)
        if disponible > 0:
            emitir_nota_credito(doc.pk, disponible, "Orden cancelada")


# ------------------------------------------------------------------------------------ cobranza (CRM)
def entregadas_sin_factura(clientes):
    """RN-22: órdenes B2B entregadas que aún no se facturaron: venta hecha que todavía no se puede cobrar."""
    ordenes = list(Orden.objects.filter(direccion__cliente__in=clientes, direccion__cliente__tipo_cliente__codigo="B2B", estado_orden__nombre="Entregada")
                   .exclude(documento__tipo="factura").select_related("direccion__cliente__tipo_cliente", "estado_orden").order_by("creada_en"))
    for o in ordenes:
        o.monto = monto_con_iva(o)
    return ordenes


def facturas_abiertas(clientes):
    """Facturas con saldo pendiente, las que vencen antes primero; cada una trae saldo, estado y días de atraso."""
    facturas = _con_estado(list(Documento.objects.filter(tipo="factura", orden__direccion__cliente__in=clientes)
                                .select_related("orden__direccion__cliente").order_by("vence_en", "folio")))
    hoy = timezone.localdate()
    abiertas = [f for f in facturas if f.saldo > 0]
    for f in abiertas:
        f.dias_atraso = max(0, (hoy - f.vence_en).days)
    return abiertas


def resumen_cobranza(clientes):
    sin_facturar = entregadas_sin_factura(clientes)
    abiertas = facturas_abiertas(clientes)
    vencidas = [f for f in abiertas if f.estado_pago == "vencido"]
    return {"sin_facturar": sin_facturar, "monto_sin_facturar": sum(o.monto for o in sin_facturar),
            "facturas": abiertas, "por_cobrar": sum(f.saldo for f in abiertas),
            "vencido": sum(f.saldo for f in vencidas), "n_vencidas": len(vencidas)}
