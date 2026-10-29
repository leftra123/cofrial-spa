"""Reglas de negocio del CRM (RN-09 a RN-15 del informe, sección de arquitectura funcional del CRM)."""
from django.db import transaction
from django.db.models import Count, F, Max, Q, Sum
from django.utils import timezone

from catalogo.asistente import estado_de_pedido
from catalogo.models import ListaPrecio
from clientes.models import Cliente, TipoCliente, Vendedor
from cofrial import entradas
from flota.models import Telemetria
from pedidos import documentos, servicios as pedidos
from pedidos.models import Documento, Orden

from . import ia
from .models import CategoriaRequerimiento, EtapaPipeline, Interaccion, Prospecto, Requerimiento

ROLES = ("admin", "gerencia", "vendedor", "despachador")
TEXTO_MAXIMO = 4000          # caracteres de un detalle o una consulta; lo que se envía a la IA y se guarda no crece sin límite


class ErrorDeNegocio(pedidos.ErrorDeNegocio):
    pass


def rol(usuario):
    """Rol principal de una cuenta del CRM. Los clientes del portal no tienen rol: no entran al CRM."""
    if not usuario.is_authenticated:
        return None
    if usuario.is_superuser:
        return "admin"
    grupos = set(usuario.groups.values_list("name", flat=True))
    if "gerencia" in grupos:
        return "gerencia"
    if Vendedor.objects.filter(usuario=usuario, activo=True).exists():
        return "vendedor"
    if "despachadores" in grupos:
        return "despachador"
    return None


def vendedor_de(usuario):
    return Vendedor.objects.filter(usuario=usuario).first()


def ve_todo(usuario):
    return rol(usuario) in ("admin", "gerencia")


# ---------------------------------------------------------------- RN-09: cada vendedor ve solo su cartera
def clientes_visibles(usuario):
    base = Cliente.objects.select_related("tipo_cliente", "vendedor")
    return base if ve_todo(usuario) else base.filter(vendedor__usuario=usuario)


def prospectos_visibles(usuario):
    base = Prospecto.objects.select_related("etapa", "vendedor")
    return base if ve_todo(usuario) else base.filter(vendedor__usuario=usuario)


def puede_editar(usuario):
    """Gerencia solo lee (Tabla 2); administrador y vendedor escriben dentro de su alcance."""
    return rol(usuario) in ("admin", "vendedor")


# ---------------------------------------------------------------- solicitudes de cuenta de empresa (registro B2B)
def solicitudes_empresa():
    """Empresas que se registraron solas y esperan aprobación: cliente B2B sin vendedor y con la cuenta aún inactiva."""
    return Cliente.objects.filter(tipo_cliente__codigo="B2B", vendedor__isnull=True, usuario__is_active=False)


def _solicitud(usuario, cliente_id):
    if not puede_editar(usuario):
        raise ErrorDeNegocio("Tu rol solo puede revisar las solicitudes; las aprueba un vendedor o el administrador.")
    c = solicitudes_empresa().select_for_update(of=("self",)).filter(pk=cliente_id).first()
    if c is None:
        raise ErrorDeNegocio("Esa solicitud ya no está pendiente: otra persona la revisó.")
    return c


@transaction.atomic
def aprobar_empresa(usuario, cliente_id, vendedor_id=None):
    """Activa la cuenta de la empresa y la deja en una cartera: la del vendedor que aprueba, o la que elige el administrador."""
    c = _solicitud(usuario, cliente_id)
    if rol(usuario) == "vendedor":
        vendedor = vendedor_de(usuario)
    else:
        vendedor = Vendedor.objects.filter(pk=entradas.entero(vendedor_id) if vendedor_id else None, activo=True).first()
        if vendedor is None:
            raise ErrorDeNegocio("Elige el vendedor que atenderá a esta empresa.")
    c.vendedor = vendedor
    c.save(update_fields=["vendedor"])
    type(c.usuario).objects.filter(pk=c.usuario_id).update(is_active=True)
    Interaccion.objects.create(vendedor=vendedor, cliente=c, tipo="nota",
                               detalle=f"Cuenta de empresa aprobada por {usuario.get_username()}: ya puede comprar con la lista institucional.")
    return c


@transaction.atomic
def rechazar_empresa(usuario, cliente_id):
    """Borra la solicitud (cliente, dirección y cuenta): nunca compró, porque su cuenta no estaba activa."""
    c = _solicitud(usuario, cliente_id)
    cuenta = c.usuario
    nombre = c.nombre
    c.delete()
    cuenta.delete()
    return nombre


# ---------------------------------------------------------------- RN-10 y RN-11: pipeline
def transiciones_de(prospecto):
    """Etapas a las que puede pasar un prospecto: la siguiente del embudo o «Perdido» (Figura de pipeline)."""
    if prospecto.etapa.es_final:
        return []
    etapas = list(EtapaPipeline.objects.order_by("orden_etapa"))
    abiertas = [e for e in etapas if not e.es_final]
    ganada = next(e for e in etapas if e.es_ganada)
    perdida = next(e for e in etapas if e.es_final and not e.es_ganada)
    idx = abiertas.index(prospecto.etapa)
    siguiente = abiertas[idx + 1] if idx + 1 < len(abiertas) else ganada
    return [siguiente, perdida]


@transaction.atomic
def mover_prospecto(usuario, prospecto_id, etapa_id, motivo="", rut=""):
    prospecto = prospectos_visibles(usuario).select_for_update(of=("self",)).get(pk=prospecto_id)
    if not puede_editar(usuario):
        raise ErrorDeNegocio("Tu rol no puede modificar prospectos.")
    destino = next((e for e in transiciones_de(prospecto) if e.pk == entradas.entero(etapa_id)), None)
    if destino is None:
        raise ErrorDeNegocio(f"No se puede pasar de \"{prospecto.etapa.nombre}\" a esa etapa; el embudo no permite saltos.")
    ahora = timezone.now()
    if destino.es_final and not destino.es_ganada:                      # Perdido
        if not motivo.strip():
            raise ErrorDeNegocio("Perder un prospecto exige indicar el motivo.")
        if len(motivo.strip()) > 200:
            raise ErrorDeNegocio("El motivo admite hasta 200 caracteres.")
        prospecto.motivo_perdida, prospecto.cerrado_en = motivo.strip(), ahora
    elif destino.es_ganada:                                              # RN-11: ganar crea el cliente B2B
        if not rut.strip():
            raise ErrorDeNegocio("Para ganar el prospecto indica el RUT de la empresa.")
        if len(rut.strip()) > 12:
            raise ErrorDeNegocio("El RUT no es válido (máximo 12 caracteres, con puntos y guion).")
        if not prospecto.email:
            raise ErrorDeNegocio("El prospecto necesita un correo para crearlo como cliente.")
        if Cliente.objects.filter(rut=rut.strip()).exists():
            raise ErrorDeNegocio("Ya existe un cliente con ese RUT.")
        tipo = TipoCliente.objects.get(codigo="B2B")
        prospecto.cliente = Cliente.objects.create(tipo_cliente=tipo, vendedor=prospecto.vendedor, rut=rut.strip(),
                                                   nombre=prospecto.empresa or prospecto.nombre_contacto,
                                                   email=prospecto.email, telefono=prospecto.telefono)
        prospecto.cerrado_en = ahora
    elif destino.nombre == "Contactado" and not prospecto.interaccion_set.exists():
        raise ErrorDeNegocio("Registra al menos una interacción antes de marcar al prospecto como contactado.")
    prospecto.etapa = destino
    prospecto.save()
    return prospecto


# ---------------------------------------------------------------- RN-12: interacciones
def registrar_interaccion(usuario, tipo, detalle, prospecto=None, cliente=None):
    if not puede_editar(usuario):
        raise ErrorDeNegocio("Tu rol no puede registrar interacciones.")
    if tipo not in dict(Interaccion.TIPOS):
        raise ErrorDeNegocio("Elige un tipo de interacción válido.")
    if not (detalle or "").strip():
        raise ErrorDeNegocio("Escribe el detalle de la interacción.")
    if len(detalle) > TEXTO_MAXIMO:
        raise ErrorDeNegocio(f"El detalle admite hasta {TEXTO_MAXIMO} caracteres.")
    vendedor = vendedor_de(usuario) or (prospecto.vendedor if prospecto else cliente.vendedor)
    if vendedor is None:
        raise ErrorDeNegocio("El cliente no tiene vendedor asignado; asígnalo antes de registrar interacciones.")
    return Interaccion.objects.create(vendedor=vendedor, prospecto=prospecto, cliente=cliente, tipo=tipo, detalle=detalle.strip())


# ---------------------------------------------------------------- RN-13: alerta de frío sobre las órdenes
def ordenes_con_alerta(ordenes):
    """Agrega a cada orden `alertas_frio`: lecturas con alerta del camión del despacho durante el viaje."""
    resultado = []
    ahora = timezone.now()
    for o in ordenes:
        n = 0
        d = o.despacho
        if d is not None and d.salida_en is not None:
            n = Telemetria.objects.filter(camion_id=d.camion_id, alerta_ruptura_frio=True, registrado_en__gte=d.salida_en,
                                          registrado_en__lte=d.llegada_en or ahora).count()
        o.alertas_frio = n
        resultado.append(o)
    return resultado


def ordenes_de_cliente(cliente):
    ordenes = Orden.objects.filter(direccion__cliente=cliente).select_related("estado_orden", "despacho__camion").order_by("-creada_en")
    ordenes = list(ordenes)
    for o in ordenes:
        o.total = pedidos.total_orden(o)
    return ordenes_con_alerta(ordenes)


def ordenes_afectadas(usuario):
    """Órdenes con alerta de frío durante su viaje, dentro del alcance del usuario (para el seguimiento de alertas)."""
    cartera = clientes_visibles(usuario).values_list("pk", flat=True)
    base = Orden.objects.filter(despacho__isnull=False, despacho__salida_en__isnull=False).select_related(
        "estado_orden", "despacho__camion", "direccion__cliente")
    if rol(usuario) != "despachador":
        base = base.filter(direccion__cliente_id__in=cartera)
    return [o for o in ordenes_con_alerta(list(base.order_by("-creada_en"))) if o.alertas_frio]


# ---------------------------------------------------------------- RN-15: pedido a nombre del cliente
@transaction.atomic
def crear_pedido_para_cliente(usuario, cliente_id, cantidades, direccion_id, numero_oc, tipo_interaccion, detalle_interaccion):
    """El vendedor genera el pedido de un cliente que aún llama, y queda registrada la interacción que lo originó."""
    cliente = clientes_visibles(usuario).get(pk=cliente_id)
    if not puede_editar(usuario):
        raise ErrorDeNegocio("Tu rol no puede crear pedidos.")
    if tipo_interaccion not in ("llamada", "correo"):
        raise ErrorDeNegocio("Indica si el pedido llegó por llamada o por correo.")
    registrar_interaccion(usuario, tipo_interaccion, detalle_interaccion, cliente=cliente)
    carrito = pedidos.carrito_abierto(cliente)
    carrito.carritoitem_set.all().delete()
    for producto_id, cantidad in cantidades.items():
        if cantidad > 0:
            pedidos.agregar(cliente, producto_id, cantidad)
    return pedidos.generar_orden(cliente, direccion_id, numero_oc)


# ---------------------------------------------------------------- RN-14: clasificación con IA y manual
ASUNTO_AUTOMATICO = "Entrega no concretada del pedido"   # lo escribe el sistema cuando el cliente dice «No pude recibirlo»
CATEGORIA_ENTREGA = "Problema en la entrega"   # la usa por defecto un requerimiento creado por una entrega no concretada
UMBRAL_CONFIANZA = 0.60            # supuesto del informe (RN-14): por debajo, revisión manual


def clasificar_con_ia(requerimiento):
    """RN-14. Clasifica con IA y guarda la confianza. Si la API falla o la confianza es menor que el umbral,
    el requerimiento queda «sin clasificar» para revisión manual. Nunca lanza ni pierde el requerimiento.
    Si el requerimiento está ligado a un pedido, además se intenta el desglose del texto; si ese falla, solo queda sin desglose."""
    categorias = {c.nombre: c for c in CategoriaRequerimiento.objects.all()}
    try:
        nombre, confianza = ia.clasificar(requerimiento.asunto, requerimiento.descripcion, list(categorias))
    except ia.ErrorIA as e:
        ia.log.warning("Requerimiento %s sin clasificar por IA: %s", requerimiento.pk, e)
        requerimiento.ia_no_disponible = True          # solo para informar a quien lo pidió; no se guarda
        desglosar_requerimiento(requerimiento)
        return requerimiento
    requerimiento.confianza_ia = round(confianza, 2)
    requerimiento.categoria_ia = categorias[nombre]                 # lo que propuso la IA, aunque no alcance el umbral (sirve para medir su acierto)
    if confianza >= UMBRAL_CONFIANZA:
        requerimiento.categoria_requerimiento = categorias[nombre]
        requerimiento.estado = "clasificado"
    requerimiento.save(update_fields=["confianza_ia", "categoria_ia", "categoria_requerimiento", "estado"])
    desglosar_requerimiento(requerimiento)
    return requerimiento


def desglosar_requerimiento(requerimiento):
    """Desglose del texto del cliente con IA, guardado junto al requerimiento. Cualquier falla se ignora: el requerimiento ya está guardado."""
    if not requerimiento.orden_id:
        return None
    try:
        estado = estado_de_pedido(requerimiento.orden.estado_orden.nombre)
        texto = requerimiento.descripcion if requerimiento.asunto.startswith(ASUNTO_AUTOMATICO) else f"{requerimiento.asunto}. {requerimiento.descripcion}"
        requerimiento.desglose = ia.desglosar(texto, estado)         # el asunto que arma el sistema no es del cliente: no se manda ni sale como «hecho»
    except ia.ErrorIA as e:
        ia.log.warning("Requerimiento %s sin desglose de IA: %s", requerimiento.pk, e)
        return None
    requerimiento.save(update_fields=["desglose"])
    return requerimiento.desglose


def telemetria_del_viaje(orden):
    """Dato de la BASE (no de la IA) para cruzar con un reclamo de temperatura: última temperatura del camión del viaje, la máxima y si hubo alerta de frío."""
    d = orden.despacho
    if d is None or d.salida_en is None:
        return None
    lecturas = Telemetria.objects.filter(camion_id=d.camion_id, registrado_en__gte=d.salida_en, registrado_en__lte=d.llegada_en or timezone.now())
    ultima = lecturas.order_by("-registrado_en").first()
    if ultima is None:
        return {"camion": d.camion_id, "lecturas": 0}
    return {"camion": d.camion_id, "lecturas": lecturas.count(), "ultima_temp": ultima.temp_camara, "ultima_hora": ultima.registrado_en,
            "max_temp": lecturas.aggregate(m=Max("temp_camara"))["m"], "alertas": lecturas.filter(alerta_ruptura_frio=True).count(),
            "limite": d.camion.rango_temperatura.temp_max_c}


def acierto_de_la_ia():
    """Cuánto acierta la IA cuando ventas corrigió a mano: de los requerimientos que la IA dudó (o no pudo clasificar) y una persona clasificó,
    en cuántos la persona eligió la misma categoría que la IA había propuesto."""
    manuales = Requerimiento.objects.filter(clasificado_manual=True, categoria_ia__isnull=False)
    n = manuales.count()
    coinciden = manuales.filter(categoria_ia=F("categoria_requerimiento")).count()
    return {"corregidos": n, "coinciden": coinciden, "porcentaje": round(100 * coinciden / n) if n else None}


def crear_requerimiento(cliente, asunto, descripcion, orden=None, categoria_nombre=None):
    """CU-09: el cliente registra su consulta; se guarda siempre y luego se intenta clasificar.
    Con `categoria_nombre` (p. ej. CATEGORIA_ENTREGA) la categoría ya es conocida: se asigna sin pasar por la IA, que solo afina el motivo en el desglose."""
    asunto, descripcion = asunto.strip(), descripcion.strip()
    if not asunto or not descripcion:
        raise ErrorDeNegocio("Indica el asunto y describe tu consulta.")
    if len(descripcion) > TEXTO_MAXIMO:
        raise ErrorDeNegocio(f"La descripción admite hasta {TEXTO_MAXIMO} caracteres; resume tu consulta.")
    r = Requerimiento.objects.create(cliente=cliente, orden=orden, asunto=asunto[:150], descripcion=descripcion)
    if categoria_nombre is None and orden is not None and orden.estado_orden.nombre == "Entrega no concretada":
        categoria_nombre = CATEGORIA_ENTREGA            # lo crea el cliente al decir «No pude recibirlo»: la categoría ya se sabe
    categoria = CategoriaRequerimiento.objects.filter(nombre=categoria_nombre).first() if categoria_nombre else None
    if categoria:
        r.categoria_requerimiento, r.estado = categoria, "clasificado"
        r.save(update_fields=["categoria_requerimiento", "estado"])
        desglosar_requerimiento(r)
        return r
    return clasificar_con_ia(r)


def reintentar_ia(usuario, requerimiento_id):
    if not puede_editar(usuario):
        raise ErrorDeNegocio("Tu rol no puede clasificar requerimientos.")
    return clasificar_con_ia(Requerimiento.objects.get(pk=requerimiento_id))


def clasificar_manual(usuario, requerimiento_id, categoria_id):
    if not puede_editar(usuario):
        raise ErrorDeNegocio("Tu rol no puede clasificar requerimientos.")
    r = Requerimiento.objects.get(pk=requerimiento_id)
    r.categoria_requerimiento, r.estado, r.clasificado_manual = CategoriaRequerimiento.objects.get(pk=categoria_id), "clasificado", True     # una categoría inexistente no se guarda
    r.save(update_fields=["categoria_requerimiento", "estado", "clasificado_manual"])
    return r


def indicadores(usuario):
    """Indicadores del CRM: propios para el vendedor, de todos para gerencia y administrador."""
    prospectos = prospectos_visibles(usuario)
    cerrados = prospectos.filter(etapa__es_final=True)
    ganados = cerrados.filter(etapa__es_ganada=True).count()
    n_cerrados = cerrados.count()
    abiertos = prospectos.filter(etapa__es_final=False)
    ordenes = Orden.objects.filter(direccion__cliente__in=clientes_visibles(usuario)).exclude(estado_orden__nombre="Cancelada")
    cobro = documentos.resumen_cobranza(clientes_visibles(usuario))
    por_canal = {}
    for o in ordenes.select_related("direccion__cliente__tipo_cliente"):
        canal = o.direccion.cliente.tipo_cliente.codigo
        por_canal[canal] = por_canal.get(canal, 0) + pedidos.total_orden(o)
    return {
        "abiertos": abiertos.count(),
        "valor_embudo": abiertos.aggregate(t=Sum("monto_estimado_clp"))["t"] or 0,
        "ganados": ganados, "perdidos": n_cerrados - ganados,
        "conversion": round(100 * ganados / n_cerrados) if n_cerrados else None,
        "ventas_por_canal": sorted(por_canal.items()),
        "pedidos_afectados": len(ordenes_afectadas(usuario)),
        "oc_pendientes": ordenes.filter(oc_pendiente=True).count(),
        "por_cobrar": cobro["por_cobrar"], "vencido": cobro["vencido"], "n_vencidas": cobro["n_vencidas"],
        "sin_facturar": len(cobro["sin_facturar"]),
        "requerimientos_pendientes": Requerimiento.objects.filter(estado="sin_clasificar").count(),
        "por_etapa": list(abiertos.values("etapa__nombre", "etapa__orden_etapa").annotate(n=Count("pk"), monto=Sum("monto_estimado_clp")).order_by("etapa__orden_etapa")),
    }


# ---------------------------------------------------------------- RN-17 a RN-22: documentos y cobranza
def cobranza(usuario):
    """Lo entregado que falta facturar y las facturas por cobrar, dentro de la cartera que el usuario puede ver."""
    return documentos.resumen_cobranza(clientes_visibles(usuario))


def _exigir_edicion(usuario):
    if not puede_editar(usuario):
        raise ErrorDeNegocio("Tu rol no puede emitir documentos ni registrar pagos.")


def facturar(usuario, orden_id):
    _exigir_edicion(usuario)
    orden = Orden.objects.filter(pk=orden_id, direccion__cliente__in=clientes_visibles(usuario)).first()
    if orden is None:
        raise ErrorDeNegocio("Orden no encontrada en tu cartera.")
    return documentos.emitir_factura(orden)


def _documento_visible(usuario, documento_id):
    doc = Documento.objects.filter(pk=documento_id, orden__direccion__cliente__in=clientes_visibles(usuario)).first()
    if doc is None:
        raise ErrorDeNegocio("Documento no encontrado en tu cartera.")
    return doc


def registrar_pago(usuario, documento_id, monto, medio, referencia=""):
    _exigir_edicion(usuario)
    return documentos.registrar_pago(_documento_visible(usuario, documento_id).pk, monto, medio, referencia)


def emitir_nota_credito(usuario, documento_id, monto, motivo):
    _exigir_edicion(usuario)
    return documentos.emitir_nota_credito(_documento_visible(usuario, documento_id).pk, monto, motivo)
