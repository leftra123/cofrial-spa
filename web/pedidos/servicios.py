"""Reglas de negocio del carrito y las órdenes (RN-01 a RN-08 del informe, sección de canales).

Toda la lógica vive aquí y no en las vistas, para que el portal, el CRM y las pruebas usen las mismas reglas.
"""
from django.db import transaction
from django.db.models import F

from catalogo import avisos
from catalogo.models import Categoria, PrecioProducto, Producto
from clientes.models import Cliente, Direccion

from .models import Carrito, CarritoItem, EstadoOrden, Orden, OrdenItem


class ErrorDeNegocio(Exception):
    """Una regla de negocio impide la operación; el mensaje se muestra tal cual al usuario."""

    def __init__(self, *mensajes):
        super().__init__(" ".join(mensajes))
        self.mensajes = list(mensajes)


def cliente_de(usuario):
    if not usuario.is_authenticated:
        return None
    return Cliente.objects.select_related("tipo_cliente__lista_precio").filter(usuario=usuario).first()


def precio_de(cliente, producto_id):
    """RN-01: el precio sale de la lista del tipo de cliente; no hay precio sin lista."""
    return (PrecioProducto.objects.filter(lista_precio=cliente.tipo_cliente.lista_precio_id, producto_id=producto_id)
            .values_list("precio_clp", flat=True).first())


# ------------------------------------------------------------------------------------ carrito
def carrito_abierto(cliente):
    """RN-03: un solo carrito abierto por cliente."""
    carrito, _ = Carrito.objects.get_or_create(cliente=cliente, estado="abierto")
    return carrito


def agregar(cliente, producto_id, cantidad):
    if cantidad < 1:
        raise ErrorDeNegocio("La cantidad debe ser al menos 1.")
    try:
        producto = Producto.objects.get(pk=producto_id, activo=True)
    except Producto.DoesNotExist:
        raise ErrorDeNegocio("El producto no existe o ya no está disponible.")
    if precio_de(cliente, producto.pk) is None:
        raise ErrorDeNegocio(f"{producto.nombre} no tiene precio en tu lista.")
    carrito = carrito_abierto(cliente)
    avisos.marcar_atendidos(cliente, producto.pk)          # si esperaba este producto, el aviso ya cumplió su función
    item, creado = CarritoItem.objects.get_or_create(carrito=carrito, producto=producto, defaults={"cantidad": cantidad})
    if not creado:
        item.cantidad += cantidad
        item.save(update_fields=["cantidad"])
    return item


def fijar_cantidad(cliente, producto_id, cantidad):
    carrito = carrito_abierto(cliente)
    if cantidad < 1:
        CarritoItem.objects.filter(carrito=carrito, producto_id=producto_id).delete()
    else:
        CarritoItem.objects.filter(carrito=carrito, producto_id=producto_id).update(cantidad=cantidad)


def lineas(cliente):
    """Líneas del carrito con precio, subtotal y si hay stock; el precio se calcula, no se guarda (modelo en 3FN)."""
    filas = []
    for item in CarritoItem.objects.filter(carrito=carrito_abierto(cliente)).select_related("producto").order_by("producto__nombre"):
        precio = precio_de(cliente, item.producto_id) or 0
        filas.append({"producto": item.producto, "cantidad": item.cantidad, "precio": precio,
                      "subtotal": precio * item.cantidad, "hay_stock": item.cantidad <= item.producto.stock_disponible})
    return filas


def total(filas):
    return sum(f["subtotal"] for f in filas)


# ------------------------------------------------------------------------------------ órdenes
@transaction.atomic
def generar_ordenes(cliente, direccion_id, numero_oc=""):
    """Convierte el carrito en órdenes. RN-02, RN-03, RN-04, RN-05 y RN-06 se aplican aquí, en una sola transacción.

    RN-09: la cadena de frío no se mezcla en un camión, así que un carrito con productos de más de un rango de temperatura
    (p. ej. congelados y refrigerados) se divide en una orden por rango, con la misma dirección y la misma OC. Devuelve la lista.
    """
    numero_oc = (numero_oc or "").strip()[:30]
    pendiente = cliente.tipo_cliente.codigo == "B2B" and not numero_oc      # RN-05: sin OC la orden se crea igual, marcada «OC pendiente»
    direccion = Direccion.objects.filter(pk=direccion_id, cliente=cliente).first()    # RN-04
    if direccion is None:
        raise ErrorDeNegocio("Elige una dirección de entrega que pertenezca a tu cuenta.")
    carrito = Carrito.objects.select_for_update().filter(cliente=cliente, estado="abierto").first()
    items = list(CarritoItem.objects.filter(carrito=carrito)) if carrito else []
    if not items:
        raise ErrorDeNegocio("Tu carrito está vacío.")

    # RN-02: se bloquean los productos (en orden de id, para no provocar bloqueos cruzados) antes de validar el stock
    productos = {p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=[i.producto_id for i in items]).order_by("pk")}
    faltantes = [f"{productos[i.producto_id].nombre}: pides {i.cantidad} y quedan {productos[i.producto_id].stock_disponible}."
                 for i in items if i.cantidad > productos[i.producto_id].stock_disponible]
    if faltantes:
        raise ErrorDeNegocio("No hay stock suficiente para generar la orden.", *faltantes)

    precios = {i.producto_id: precio_de(cliente, i.producto_id) for i in items}
    sin_precio = [productos[pid].nombre for pid, pr in precios.items() if pr is None]
    if sin_precio:
        raise ErrorDeNegocio("Productos sin precio en tu lista: " + ", ".join(sin_precio) + ".")

    rango_de_categoria = dict(Categoria.objects.filter(pk__in={p.categoria_id for p in productos.values()})
                              .values_list("pk", "rango_temperatura_id"))
    grupos = {}
    for i in items:                                                                # RN-09: un grupo por rango de temperatura
        grupos.setdefault(rango_de_categoria[productos[i.producto_id].categoria_id], []).append(i)

    estado = EstadoOrden.objects.get(orden_flujo=1)
    ordenes = []
    for rango_id in sorted(grupos):
        orden = Orden.objects.create(direccion=direccion, numero_oc=numero_oc, oc_pendiente=pendiente, estado_orden=estado)
        if pendiente:
            orden.numero_oc = referencia_web(orden)
            orden.save(update_fields=["numero_oc"])
        for i in grupos[rango_id]:
            OrdenItem.objects.create(orden=orden, producto_id=i.producto_id, cantidad=i.cantidad,
                                     precio_unitario_clp=precios[i.producto_id])        # RN-06: precio congelado
            Producto.objects.filter(pk=i.producto_id).update(stock_disponible=F("stock_disponible") - i.cantidad)
        ordenes.append(orden)
    carrito.estado = "convertido"                                                  # RN-03
    carrito.save(update_fields=["estado"])
    return ordenes


def generar_orden(cliente, direccion_id, numero_oc=""):
    """Igual que `generar_ordenes`, pero devuelve solo la primera orden (la que muestra la pantalla de confirmación)."""
    return generar_ordenes(cliente, direccion_id, numero_oc)[0]


def referencia_web(orden):
    """Referencia propia de Cofrial para una orden institucional sin OC: WEB-<año>-<n.º de orden con ceros>."""
    return f"WEB-{orden.creada_en.year}-{orden.orden_id:04d}"


def registrar_oc(cliente, orden_id, numero_oc):
    """El cliente institucional agrega la OC real a una orden que quedó «OC pendiente»; reemplaza la referencia web."""
    numero_oc = (numero_oc or "").strip()
    if not numero_oc:
        raise ErrorDeNegocio("Escribe el número de tu orden de compra.")
    if len(numero_oc) > 30:
        raise ErrorDeNegocio("El número de orden de compra admite hasta 30 caracteres.")
    orden = ordenes_de(cliente).filter(pk=orden_id).first()
    if orden is None:
        raise ErrorDeNegocio("Orden no encontrada.")
    if not orden.oc_pendiente:
        raise ErrorDeNegocio("Esta orden ya tiene su orden de compra.")
    if orden.estado_orden.es_final:
        raise ErrorDeNegocio(f"La orden ya está «{orden.estado_orden.nombre}»; no se puede modificar.")
    orden.numero_oc, orden.oc_pendiente = numero_oc, False
    orden.save(update_fields=["numero_oc", "oc_pendiente"])
    return orden


def ordenes_de(cliente):
    return (Orden.objects.filter(direccion__cliente=cliente).select_related("estado_orden", "direccion__comuna", "despacho")
            .order_by("-creada_en"))


def total_orden(orden):
    return sum(i.cantidad * i.precio_unitario_clp for i in orden.ordenitem_set.all())


@transaction.atomic
def cancelar(orden, como="cliente"):
    """RN-07: el cliente cancela solo en «Recibida»; el vendedor hasta «En preparación». Cancelar repone el stock."""
    orden = Orden.objects.select_for_update().select_related("estado_orden").get(pk=orden.pk)
    limite = 1 if como == "cliente" else 3
    if orden.estado_orden.es_final or orden.estado_orden.orden_flujo > limite:
        quien = "el cliente" if como == "cliente" else "el vendedor"
        raise ErrorDeNegocio(f"La orden está \"{orden.estado_orden.nombre}\" y {quien} ya no puede cancelarla.")
    for item in orden.ordenitem_set.all():
        Producto.objects.filter(pk=item.producto_id).update(stock_disponible=F("stock_disponible") + item.cantidad)
    orden.estado_orden = EstadoOrden.objects.get(nombre="Cancelada")
    orden.save(update_fields=["estado_orden"])
    return orden


@transaction.atomic
def avanzar(orden):
    """Pasa la orden al siguiente estado del flujo (Figura de estados). «Despachada» exige un despacho asignado."""
    orden = Orden.objects.select_for_update().select_related("estado_orden").get(pk=orden.pk)
    if orden.estado_orden.es_final:
        raise ErrorDeNegocio(f"La orden ya está \"{orden.estado_orden.nombre}\".")
    siguiente = EstadoOrden.objects.filter(orden_flujo__gt=orden.estado_orden.orden_flujo, es_final=False).first() \
        or EstadoOrden.objects.get(nombre="Entregada")
    if siguiente.nombre == "Despachada" and orden.despacho_id is None:
        raise ErrorDeNegocio("Asigna un despacho antes de marcar la orden como despachada.")
    orden.estado_orden = siguiente
    orden.save(update_fields=["estado_orden"])
    return orden


@transaction.atomic
def repetir_ultimo_pedido(cliente):
    """RN-08: copia al carrito las líneas de la última orden no cancelada, ajustadas al stock; devuelve los avisos."""
    ultima = ordenes_de(cliente).exclude(estado_orden__nombre="Cancelada").first()
    if ultima is None:
        raise ErrorDeNegocio("Aún no tienes pedidos que repetir.")
    avisos = []
    for item in ultima.ordenitem_set.select_related("producto"):
        p = item.producto
        if not p.activo or p.stock_disponible < 1 or precio_de(cliente, p.pk) is None:
            avisos.append(f"{p.nombre} no está disponible y no se agregó.")
            continue
        cantidad = min(item.cantidad, p.stock_disponible)
        if cantidad < item.cantidad:
            avisos.append(f"{p.nombre}: se ajustó de {item.cantidad} a {cantidad} por stock.")
        agregar(cliente, p.pk, cantidad)
    return avisos


def seguimiento(orden):
    """Datos del envío para el cliente (W6): última lectura del camión, banda de conservación y lecturas de la última hora.

    Sin despacho no hay camión que seguir. La alerta se informa si hubo ruptura de frío en la última hora del camión."""
    from datetime import timedelta

    from django.utils import timezone

    from flota.models import Telemetria

    if orden.despacho_id is None:
        return None
    camion = orden.despacho.camion
    desde = timezone.now() - timedelta(minutes=60)
    lecturas = list(Telemetria.objects.filter(camion=camion, registrado_en__gte=desde).order_by("registrado_en"))
    ultima = (lecturas[-1] if lecturas else Telemetria.objects.filter(camion=camion).order_by("-registrado_en").first())
    from flota.vigente import ultima_vigente
    ultima = ultima_vigente(camion) or ultima         # con el modo demostración, la temperatura forzada
    rango = camion.rango_temperatura
    return {
        "camion_id": camion.camion_id, "patente": camion.patente,
        "banda": {"min": rango.temp_min_c, "max": rango.temp_max_c, "nombre": rango.nombre},
        "ultima": None if ultima is None else {
            "temp_camara": ultima.temp_camara, "lat": ultima.lat, "long": ultima.long, "combustible_pct": ultima.combustible_pct,
            "alerta_ruptura_frio": ultima.alerta_ruptura_frio, "hace_seg": int((timezone.now() - ultima.registrado_en).total_seconds())},
        "destino": None if orden.direccion.lat is None else {"lat": orden.direccion.lat, "long": orden.direccion.long, "direccion": str(orden.direccion)},
        "hubo_ruptura": any(l.alerta_ruptura_frio for l in lecturas),
        "serie": [{"t": l.registrado_en.isoformat(), "temp": l.temp_camara} for l in lecturas][-120:],
        "salida_en": orden.despacho.salida_en.isoformat() if orden.despacho.salida_en else None,
        "llegada_en": orden.despacho.llegada_en.isoformat() if orden.despacho.llegada_en else None,
        **_llegada(orden, ultima),
    }


# ---------- llegada estimada y avisos (campanita) ----------
# La velocidad y el factor de calles salen de la configuración (VELOCIDAD_MEDIA_KMH y FACTOR_CALLES) y el simulador IoT usa las mismas
# variables: así la hora de llegada que ve el cliente coincide con el movimiento del camión.
CERCA_KM = 2


def _km(lat1, lon1, lat2, lon2):
    from math import asin, cos, radians, sin, sqrt
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 12742 * asin(sqrt(a))


def _redondear5(momento):
    from datetime import timedelta
    return momento.replace(second=0, microsecond=0) - timedelta(minutes=momento.minute % 5)


def _llegada(orden, ultima):
    """Distancia que falta y ventana estimada de llegada («entre las 15:10 y las 15:30»). Solo mientras el camión va en camino."""
    from datetime import timedelta
    from django.utils import timezone
    vacio = {"km_restantes": None, "eta": None, "cerca": False}
    d = orden.despacho
    if ultima is None or orden.direccion.lat is None or d.salida_en is None or d.llegada_en is not None:
        return vacio
    if timezone.now() - ultima.registrado_en > timedelta(minutes=10):      # sin señal reciente no se inventa una hora
        return vacio
    from django.conf import settings
    km = _km(ultima.lat, ultima.long, orden.direccion.lat, orden.direccion.long) * settings.FACTOR_CALLES
    minutos = km / settings.VELOCIDAD_MEDIA_KMH * 60
    centro = timezone.now() + timedelta(minutes=minutos)
    return {"km_restantes": round(km, 1), "cerca": km <= CERCA_KM,
            "eta": {"desde": _redondear5(centro - timedelta(minutes=5)).isoformat(),
                    "hasta": (_redondear5(centro + timedelta(minutes=10)) + timedelta(minutes=5)).isoformat()}}


def avisos_de_llegada(cliente):
    """Avisos para la campanita del cliente, calculados desde el estado de sus órdenes (no se guardan): salió, cerca y llegó.
    Cada aviso tiene un id estable para que el navegador sepa cuáles ya vio."""
    from datetime import timedelta
    from django.utils import timezone
    from django.utils.timezone import localtime
    from flota.models import Telemetria

    hace_un_dia = timezone.now() - timedelta(hours=24)
    salida = []
    for o in ordenes_de(cliente).select_related("despacho__camion", "direccion", "estado_orden"):
        d = o.despacho
        if d is None or d.salida_en is None:
            continue
        if d.llegada_en is not None and d.llegada_en < hace_un_dia:
            continue
        hora = lambda x: localtime(x).strftime("%H:%M")
        salida.append({"id": f"{o.orden_id}-salio", "orden_id": o.orden_id, "tipo": "salio", "cuando": d.salida_en.isoformat(),
                       "texto": f"Tu pedido N.º {o.orden_id} salió a las {hora(d.salida_en)}."})
        if d.llegada_en is not None:
            salida.append({"id": f"{o.orden_id}-llego", "orden_id": o.orden_id, "tipo": "llego", "cuando": d.llegada_en.isoformat(),
                           "texto": f"Tu pedido N.º {o.orden_id} llegó a las {hora(d.llegada_en)}."})
            continue
        ultima = Telemetria.objects.filter(camion=d.camion, registrado_en__gte=d.salida_en).order_by("-registrado_en").first()
        if Telemetria.objects.filter(camion=d.camion, registrado_en__gte=max(d.salida_en, timezone.now() - timedelta(hours=1)), alerta_ruptura_frio=True).exists():
            salida.append({"id": f"{o.orden_id}-frio", "orden_id": o.orden_id, "tipo": "frio", "cuando": (ultima.registrado_en if ultima else d.salida_en).isoformat(),
                           "texto": f"Detectamos una variación de temperatura en el camión de tu pedido N.º {o.orden_id}. Ya la estamos revisando."})
        info = _llegada(o, ultima)
        if info["eta"]:
            desde, hasta = (localtime(timezone.datetime.fromisoformat(info["eta"][k])).strftime("%H:%M") for k in ("desde", "hasta"))
            salida.append({"id": f"{o.orden_id}-ventana", "orden_id": o.orden_id, "tipo": "ventana", "cuando": ultima.registrado_en.isoformat(),
                           "texto": f"Recibirás tu pedido N.º {o.orden_id} entre las {desde} y las {hasta}."})
        if info["cerca"]:
            salida.append({"id": f"{o.orden_id}-cerca", "orden_id": o.orden_id, "tipo": "cerca", "cuando": ultima.registrado_en.isoformat(),
                           "texto": f"El camión de tu pedido N.º {o.orden_id} está a menos de {CERCA_KM} km."})
    return sorted(salida, key=lambda a: a["cuando"], reverse=True)
