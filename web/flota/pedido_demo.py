"""Pedido de prueba cercano: crea, para la demostración, un pedido «En preparación» de un cliente de Temuco o Padre Las Casas, listo para armar su despacho.
Los clientes de Angol, Victoria o Pucón hacen viajes de horas; con estos el camión llega en minutos y la prueba se puede repetir a gusto.
Usa los mismos servicios que el carrito (stock, precios, estado inicial): no inventa nada. No toca el carrito de un cliente que ya tiene cosas en él."""
from catalogo.models import Producto
from clientes.models import Direccion
from pedidos import servicios as s

from . import servicios

COMUNAS_CERCANAS = ("Temuco", "Padre Las Casas")
RANGOS = ("Refrigerado", "Congelado")
ETAPA_EN_PREPARACION = 3          # orden_flujo de «En preparación»


class ErrorPedidoDemo(Exception):
    """No se pudo armar el pedido; el mensaje es para mostrarlo."""


def crear(rango):
    if rango not in RANGOS:
        raise ErrorPedidoDemo("Elige refrigerado o congelado.")
    productos = list(Producto.objects.filter(activo=True, stock_disponible__gte=3, categoria__rango_temperatura__nombre=rango).order_by("stock_disponible", "nombre"))
    if not productos:
        raise ErrorPedidoDemo(f"No hay productos {rango.lower()}s con stock para armar el pedido.")
    direcciones = (Direccion.objects.filter(comuna__nombre__in=COMUNAS_CERCANAS, lat__isnull=False, long__isnull=False, cliente__usuario__is_active=True)
                   .select_related("cliente__tipo_cliente", "comuna").order_by("comuna__nombre", "cliente__nombre", "pk"))
    for d in direcciones:
        cliente = d.cliente
        if s.lineas_en_carrito(cliente):
            continue
        for p in productos:
            try:
                s.agregar(cliente, p.pk, 1)
                orden = s.generar_ordenes(cliente, d.pk)[0]
            except s.ErrorDeNegocio:
                s.fijar_cantidad(cliente, p.pk, 0)          # no deja a medias el carrito de nadie
                continue
            while orden.estado_orden.orden_flujo < ETAPA_EN_PREPARACION:
                orden = s.avanzar(orden)
            return {"orden": orden.pk, "cliente": cliente.nombre, "comuna": d.comuna.nombre, "rango": rango, "producto": p.nombre}
    raise ErrorPedidoDemo("Ningún cliente cercano está libre para un pedido de prueba (todos tienen algo en el carrito).")


PLAN_DE_PREPARACION = ("Refrigerado", "Congelado", "Refrigerado")        # tres entregas cercanas, en camiones distintos


def preparar(usuario):
    """Deja la demostración andando con un solo clic: crea pedidos cercanos, los despacha en camiones libres y sanos y pide «Pedido bueno» para
    cada viaje (sin rupturas de frío; el cliente decide al recibir). Devuelve qué hizo y lo que no pudo."""
    from . import escenarios, sugerencias
    hechos, omitidos = [], []
    for rango in PLAN_DE_PREPARACION:
        try:
            pedido = crear(rango)
        except ErrorPedidoDemo as e:
            omitidos.append(str(e))
            continue
        camion = next((c for c in sugerencias.opciones_camion() if c["apto_auto"] and rango in c["rangos"]), None)
        if camion is None:
            omitidos.append(f"El pedido N.º {pedido['orden']} quedó listo, pero no hay un camión {rango.lower()} libre y sano para despacharlo.")
            continue
        try:
            despacho = servicios.despachar(camion["id"], [pedido["orden"]])
            escenarios.crear(escenarios.validar({"tipo": "entrega_perfecta", "despacho_id": despacho.despacho_id}), usuario, "boton")
        except (s.ErrorDeNegocio, escenarios.ErrorEscenario) as e:
            omitidos.append(f"Pedido N.º {pedido['orden']}: {' '.join(getattr(e, 'mensajes', [str(e)]))}")
            continue
        hechos.append({**pedido, "camion": camion["id"], "despacho": despacho.despacho_id})
    return {"viajes": hechos, "omitidos": omitidos, "en_reparacion": dejar_en_reparacion(usuario)}


MOTIVOS_DEMO = (("equipo_frio", "Demostración: el equipo de frío está en el taller."), ("sensor", "Demostración: se cambia el sensor de temperatura."),
                ("otro", "Demostración: mantención programada."))


def dejar_en_reparacion(usuario, cuantos=len(MOTIVOS_DEMO)):
    """Deja unos camiones libres «en revisión técnica» para que la flota no sea solo camiones sanos. Toma los de código más alto (los menos probables en un
    viaje de prueba) y marca la nota como «Demostración»: «Borrar lo de la demostración» los devuelve a servicio."""
    from django.db import IntegrityError, transaction
    from .models import RevisionCamion
    libres = [c for c in servicios.camiones_libres() if not c.dos_camaras][::-1]
    hechos = []
    for camion, (motivo, nota) in zip(libres, MOTIVOS_DEMO[:cuantos]):
        try:
            with transaction.atomic():
                RevisionCamion.objects.create(camion=camion, motivo=motivo, nota=nota, abierta_por=usuario)
        except IntegrityError:
            continue
        hechos.append({"camion": camion.camion_id, "motivo": dict(RevisionCamion.MOTIVOS)[motivo]})
    return hechos
