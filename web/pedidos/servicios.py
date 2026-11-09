"""Reglas de negocio del carrito y las órdenes (RN-01 a RN-08 del informe, sección de canales).

Toda la lógica vive aquí y no en las vistas, para que el portal, el CRM y las pruebas usen las mismas reglas.
"""
from django.conf import settings
from django.db import transaction
from django.db.models import F

from catalogo import avisos
from catalogo.models import Categoria, PrecioProducto, Producto
from clientes import geo
from clientes.models import Cliente, Comuna, Direccion
from cofrial import entradas

from . import documentos
from .documentos import ErrorDeNegocio     # una regla de negocio impide la operación; el mensaje se muestra tal cual al usuario
from .models import Carrito, CarritoItem, EstadoOrden, Orden, OrdenItem


RECHAZADA = "Rechazada en recepción"                # el cliente rechazó todas las líneas: el camión llegó, no se vendió nada (RN-23)
RECEPCION_CERRADA = ("Entregada", RECHAZADA)         # el cliente ya resolvió la recepción: una falla posterior del camión no lo afecta (RN-13)
SIN_VENTA = ("Cancelada", RECHAZADA)                 # órdenes que no son venta; misma regla que SIN_VENTA en grafana/generar_dashboard.py
MONTO_ACEPTADO = (F("cantidad") - F("cantidad_rechazada")) * F("precio_unitario_clp")      # de una línea (RN-23); igual que v_orden_total.total_clp


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


def lineas_en_carrito(cliente):
    """Productos distintos en el carrito abierto (líneas), no la suma de unidades."""
    return CarritoItem.objects.filter(carrito__cliente=cliente, carrito__estado="abierto").count()


def _validar_cantidad(cantidad):
    if cantidad < 1:
        raise ErrorDeNegocio("La cantidad debe ser al menos 1.")
    if cantidad > settings.CANTIDAD_MAXIMA_POR_LINEA:
        raise ErrorDeNegocio(f"La cantidad máxima por producto es {settings.CANTIDAD_MAXIMA_POR_LINEA}; para pedidos mayores contacta a tu vendedor.")


def agregar(cliente, producto_id, cantidad):
    _validar_cantidad(cantidad)
    try:
        producto = Producto.objects.get(pk=producto_id, activo=True)
    except Producto.DoesNotExist:
        raise ErrorDeNegocio("El producto no existe o ya no está disponible.")
    if precio_de(cliente, producto.pk) is None:
        raise ErrorDeNegocio(f"{producto.nombre} no tiene precio en tu lista.")
    carrito = carrito_abierto(cliente)
    avisos.marcar_atendidos(cliente, producto.pk)          # si esperaba este producto, el aviso ya cumplió su función
    with transaction.atomic():
        item, creado = CarritoItem.objects.get_or_create(carrito=carrito, producto=producto, defaults={"cantidad": cantidad})
        if not creado:
            item = CarritoItem.objects.select_for_update().get(pk=item.pk)     # dos «Agregar» seguidos suman los dos, no se pisan
            _validar_cantidad(item.cantidad + cantidad)
            item.cantidad += cantidad
            item.save(update_fields=["cantidad"])
    return item


def fijar_cantidad(cliente, producto_id, cantidad):
    carrito = carrito_abierto(cliente)
    if cantidad < 1:
        CarritoItem.objects.filter(carrito=carrito, producto_id=producto_id).delete()
    else:
        _validar_cantidad(cantidad)
        CarritoItem.objects.filter(carrito=carrito, producto_id=producto_id).update(cantidad=cantidad)


def lineas(cliente):
    """Líneas del carrito con precio, subtotal y si hay stock; el precio se calcula, no se guarda (modelo en 3FN)."""
    filas = []
    for item in CarritoItem.objects.filter(carrito=carrito_abierto(cliente)).select_related("producto").order_by("producto__nombre"):
        precio = precio_de(cliente, item.producto_id) or 0
        filas.append({"producto": item.producto, "cantidad": item.cantidad, "precio": precio,
                      "subtotal": precio * item.cantidad, "hay_stock": item.producto.activo and item.cantidad <= item.producto.stock_disponible})
    return filas


def total(filas):
    return sum(f["subtotal"] for f in filas)


RECIBE_MAXIMO = 80          # largo de orden.recibe_nombre
_LETRAS_EXTRA = " .'’-"      # además de letras: espacio, punto, apóstrofo y guion (María José O'Higgins-Soto Jr.)


def nombre_de_quien_recibe(texto):
    """Quien recibe el pedido, elegido por el comprador. Vacío = recibe el titular de la cuenta (se guarda vacío y se muestra su nombre).
    Un nombre se normaliza (espacios sobrantes fuera) y debe tener hasta 80 caracteres, al menos 2 letras y solo letras, espacio, punto,
    apóstrofo o guion: no se aceptan números ni símbolos que no son parte de un nombre. Este dato NO viaja a los proveedores de IA."""
    nombre = " ".join((texto or "").split())
    if not nombre:
        return ""
    if len(nombre) > RECIBE_MAXIMO:
        raise ErrorDeNegocio(f"El nombre de quien recibe admite hasta {RECIBE_MAXIMO} caracteres.")
    if sum(c.isalpha() for c in nombre) < 2 or any(not (c.isalpha() or c in _LETRAS_EXTRA) for c in nombre):
        raise ErrorDeNegocio("Escribe el nombre de quien recibe solo con letras (puedes usar espacios, punto, guion o apóstrofo).")
    return nombre


def opciones_de_quien_recibe(cliente, limite=8):
    """Personas que ESTE cliente eligió antes para recibir (las más recientes primero), sin repetir y sin el titular, que siempre es la
    primera opción. Solo salen de las órdenes del propio cliente."""
    titular = cliente.nombre.casefold()
    vistos, salida = set(), []
    for nombre in Orden.objects.filter(direccion__cliente=cliente).exclude(recibe_nombre="").order_by("-creada_en").values_list("recibe_nombre", flat=True)[:100]:
        if nombre.casefold() not in vistos and nombre.casefold() != titular:
            vistos.add(nombre.casefold())
            salida.append(nombre)
    return salida[:limite]


def _contexto_desde_carrito(cliente, direccion_id, numero_oc="", recibe=""):
    """Valida dirección, quién recibe, carrito, stock y precios; devuelve el contexto para generar órdenes o un checkout MP."""
    numero_oc = (numero_oc or "").strip()[:30]
    pendiente = cliente.tipo_cliente.codigo == "B2B" and not numero_oc
    try:
        direccion_id = entradas.entero(direccion_id)
    except ValueError:
        direccion_id = 0
    direccion = Direccion.objects.filter(pk=direccion_id, cliente=cliente).first()
    if direccion is None:
        raise ErrorDeNegocio("Elige una dirección de entrega que pertenezca a tu cuenta.")
    recibe = nombre_de_quien_recibe(recibe)
    carrito = Carrito.objects.select_for_update().filter(cliente=cliente, estado="abierto").first()
    items = list(CarritoItem.objects.filter(carrito=carrito).select_related("producto")) if carrito else []
    if not items:
        raise ErrorDeNegocio("Tu carrito está vacío.")
    productos = {p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=[i.producto_id for i in items]).order_by("pk")}
    retirados = [p.nombre for p in productos.values() if not p.activo]
    if retirados:                                          # se retiró del catálogo después de agregarlo al carrito: ya no se vende
        raise ErrorDeNegocio("Ya no vendemos " + ", ".join(retirados) + ". Quítalo del carrito para generar la orden.")
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
    for i in items:
        grupos.setdefault(rango_de_categoria[productos[i.producto_id].categoria_id], []).append(i)
    return {"direccion": direccion, "carrito": carrito, "items": items, "productos": productos, "precios": precios,
            "grupos": grupos, "pendiente": pendiente, "numero_oc": numero_oc, "recibe": recibe}


MAX_DIRECCIONES = 20


def _coordenadas_en_chile(lat, long):
    """Las coordenadas que mandó el navegador, o None si no sirven: vienen del cliente, así que no se les cree sin revisar."""
    try:
        lat, long = float(lat), float(long)
    except (TypeError, ValueError):
        return None
    return (lat, long) if -56.0 <= lat <= -17.0 and -76.0 <= long <= -66.0 else None    # NaN e infinito no pasan estas comparaciones


def agregar_direccion(cliente, calle_numero, comuna_id, lat=None, long=None):
    """Dirección nueva de un cliente; la primera queda como principal. La ubicación en el mapa es de mejor esfuerzo. `lat` y `long` son la
    posición que el cliente pidió usar desde su navegador; si no vienen o no sirven, se busca la dirección en OpenStreetMap."""
    calle_numero = (calle_numero or "").strip()
    if not calle_numero or len(calle_numero) > 150:
        raise ErrorDeNegocio("Escribe la calle y el número (hasta 150 caracteres).")
    comuna = Comuna.objects.filter(pk=entradas.entero(comuna_id)).first() if entradas.es_entero(comuna_id) else None
    if comuna is None:
        raise ErrorDeNegocio("Elige una comuna de la lista.")
    existentes = cliente.direccion_set.count()
    if existentes >= MAX_DIRECCIONES:
        raise ErrorDeNegocio(f"Se admiten hasta {MAX_DIRECCIONES} direcciones por cliente.")
    punto = _coordenadas_en_chile(lat, long) or (None, None)
    direccion = Direccion.objects.create(cliente=cliente, calle_numero=calle_numero, comuna=comuna, es_principal=existentes == 0, lat=punto[0], long=punto[1])
    geo.ubicar(direccion)
    return direccion


# ------------------------------------------------------------------------------------ órdenes
def elegir_comprobante(cliente, comprobante=None, giro=""):
    """La boleta usa el nombre y el RUT ya guardados en la cuenta. La factura, además, exige el giro.

    Elige solo el público. La institución compra a crédito y recibe factura después de la entrega: una boleta suya
    quedaría sin cobro, porque no pasa por un pago al comprar. Si no se elige nada, queda el comprobante del canal.
    El RUT no se vuelve a pedir ni se reemplaza: es el que se validó al crear la cuenta."""
    if comprobante not in (None, "", "boleta", "factura"):
        raise ErrorDeNegocio("Elige boleta o factura.")
    explicito = bool(comprobante)
    b2b = cliente.tipo_cliente.codigo == "B2B"
    if b2b and comprobante == "boleta":
        raise ErrorDeNegocio("Las instituciones reciben factura después de la entrega.")
    comprobante = comprobante or ("factura" if b2b else "boleta")
    giro = str(giro or "").strip()[:80]
    if comprobante == "factura" and giro and giro != cliente.giro:
        cliente.giro = giro
        cliente.save(update_fields=["giro"])
    if comprobante == "factura" and explicito and not cliente.giro:
        raise ErrorDeNegocio("Para la factura indica el giro. El RUT y la razón social son los de tu cuenta.")
    return comprobante


@transaction.atomic
def generar_ordenes(cliente, direccion_id, numero_oc="", cobrar_b2c_al_crear=True, checkout_pago=None, recibe="", comprobante=None, giro=""):
    """Convierte el carrito en órdenes. RN-02, RN-03, RN-04, RN-05 y RN-06 se aplican aquí, en una sola transacción.

    RN-09: la cadena de frío no se mezcla en un camión, así que un carrito con productos de más de un rango de temperatura
    (p. ej. congelados y refrigerados) se divide en una orden por rango, con la misma dirección, la misma OC y la misma persona que recibe.
    Devuelve la lista.
    """
    comprobante = elegir_comprobante(cliente, comprobante, giro)
    ctx = _contexto_desde_carrito(cliente, direccion_id, numero_oc, recibe)
    direccion, carrito, items, productos, precios, grupos = ctx["direccion"], ctx["carrito"], ctx["items"], ctx["productos"], ctx["precios"], ctx["grupos"]
    pendiente, numero_oc = ctx["pendiente"], ctx["numero_oc"]

    estado = EstadoOrden.objects.get(orden_flujo=1)
    ordenes = []
    for rango_id in sorted(grupos):
        orden = Orden.objects.create(direccion=direccion, numero_oc=numero_oc, oc_pendiente=pendiente, estado_orden=estado,
                                     checkout_pago=checkout_pago, recibe_nombre=ctx["recibe"], comprobante=comprobante)
        if pendiente:
            orden.numero_oc = referencia_web(orden)
            orden.save(update_fields=["numero_oc"])
        for i in grupos[rango_id]:
            OrdenItem.objects.create(orden=orden, producto_id=i.producto_id, cantidad=i.cantidad,
                                     precio_unitario_clp=precios[i.producto_id])
            Producto.objects.filter(pk=i.producto_id).update(stock_disponible=F("stock_disponible") - i.cantidad)
        if cliente.tipo_cliente.codigo == "B2C" and cobrar_b2c_al_crear:
            if comprobante == "factura":
                documentos.cobrar_factura_contado(orden)
            else:
                documentos.cobrar_b2c(orden)
        ordenes.append(orden)
    carrito.estado = "convertido"
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
    confirmar_vencidas()                  # quien lee las órdenes ve ya aplicada la confirmación automática (el simulador también la ejecuta)
    return (Orden.objects.filter(direccion__cliente=cliente).select_related("estado_orden", "direccion__comuna", "despacho")
            .order_by("-creada_en"))


def total_orden(orden):
    """Total de lo aceptado: lo que de verdad se vendió (RN-23). Sin rechazos es el pedido completo."""
    return sum(i.cantidad_aceptada * i.precio_unitario_clp for i in orden.ordenitem_set.all())


@transaction.atomic
def cancelar(orden, como="cliente"):
    """RN-07: el cliente cancela solo en «Recibida»; el vendedor hasta «En preparación». Cancelar repone el stock."""
    orden = Orden.objects.select_for_update().select_related("estado_orden").get(pk=orden.pk)
    limite = 1 if como == "cliente" else 3
    sin_concretar = como != "cliente" and orden.estado_orden.nombre == "Entrega no concretada"     # ventas puede dar de baja una entrega fallida
    if not sin_concretar and (orden.estado_orden.es_final or orden.estado_orden.orden_flujo > limite):
        quien = "el cliente" if como == "cliente" else "el vendedor"
        raise ErrorDeNegocio(f"La orden está \"{orden.estado_orden.nombre}\" y {quien} ya no puede cancelarla.")
    for item in orden.ordenitem_set.all():
        Producto.objects.filter(pk=item.producto_id).update(stock_disponible=F("stock_disponible") + item.cantidad)
    orden.estado_orden = EstadoOrden.objects.get(nombre="Cancelada")
    orden.save(update_fields=["estado_orden"])
    documentos.anular_por_cancelacion(orden)                                       # RN-21: si ya se pagó (boleta), se anula y se devuelve
    return orden


@transaction.atomic
def avanzar(orden):
    """Pasa la orden al siguiente estado del flujo (Figura de estados). «Despachada» exige un despacho asignado."""
    orden = Orden.objects.select_for_update().select_related("estado_orden").get(pk=orden.pk)
    if orden.estado_orden.es_final:
        raise ErrorDeNegocio(f"La orden ya está \"{orden.estado_orden.nombre}\".")
    siguiente_de = {"Recibida": "Confirmada", "Confirmada": "En preparación", "En preparación": "Despachada",
                    "Despachada": "Entregada", "Camión en la puerta": "Entregada"}      # de «Despachada» a «Entregada» solo como corrección manual
    if orden.estado_orden.nombre not in siguiente_de:
        raise ErrorDeNegocio(f"La orden está \"{orden.estado_orden.nombre}\": ese estado no avanza con este botón.")
    siguiente = EstadoOrden.objects.get(nombre=siguiente_de[orden.estado_orden.nombre])
    if siguiente.nombre == "Despachada" and orden.despacho_id is None:
        raise ErrorDeNegocio("Asigna un despacho antes de marcar la orden como despachada.")
    orden.estado_orden = siguiente
    orden.save(update_fields=["estado_orden"])
    if siguiente.nombre == "Despachada":
        documentos.emitir_guia(orden)                                              # RN-17: el camión sale con su guía de despacho
    return orden


MISMA_COMPRA_SEG = 5         # las órdenes de una compra dividida se crean en la misma transacción, con milisegundos de diferencia


@transaction.atomic
def repetir_ultimo_pedido(cliente):
    """RN-08: copia al carrito las líneas de la última compra no cancelada, ajustadas al stock; devuelve los avisos.
    Una compra con refrigerados y congelados se dividió en una orden por rango (RN-16), así que se toman todas las de esa compra."""
    from datetime import timedelta
    vigentes = ordenes_de(cliente).exclude(estado_orden__nombre="Cancelada")
    ultima = vigentes.first()
    if ultima is None:
        raise ErrorDeNegocio("Aún no tienes pedidos que repetir.")
    misma_compra = vigentes.filter(direccion=ultima.direccion, creada_en__gte=ultima.creada_en - timedelta(seconds=MISMA_COMPRA_SEG))
    avisos = []
    for item in OrdenItem.objects.filter(orden__in=misma_compra).select_related("producto").order_by("orden_id", "pk"):
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
    from flota import rutas
    camion = orden.despacho.camion
    fin = fin_de_exposicion(orden) if orden.estado_orden.nombre in RECEPCION_CERRADA else None
    todas = Telemetria.objects.filter(camion=camion, camara=orden.camara)      # un pedido solo mira la cámara en la que viaja
    if fin is not None:               # RN-13: quien ya recibió no ve lo que le pasó al camión después de su entrega (resumen hasta ese momento)
        todas = todas.filter(registrado_en__lte=fin)
    desde = (fin or timezone.now()) - timedelta(minutes=60)
    lecturas = list(todas.filter(registrado_en__gte=desde).order_by("registrado_en"))
    ultima = (lecturas[-1] if lecturas else todas.order_by("-registrado_en").first())
    if fin is None:
        from flota.vigente import ultima_vigente
        ultima = ultima_vigente(camion, orden.camara) or ultima         # con el modo demostración, la temperatura forzada (no aplica a una entrega ya cerrada)
    rango = camion.rango_de_camara(orden.camara)
    en_vivo = mapa_en_vivo(orden)                     # el mapa y la posición solo se muestran mientras el camión va o está en la puerta
    return {
        "camion_id": camion.camion_id, "patente": camion.patente, "mapa_en_vivo": en_vivo,
        "banda": {"min": rango.temp_min_c, "max": rango.temp_max_c, "nombre": rango.nombre},
        "ultima": None if ultima is None else {
            "temp_camara": ultima.temp_camara, "lat": ultima.lat if en_vivo else None, "long": ultima.long if en_vivo else None,
            "combustible_pct": ultima.combustible_pct,
            "alerta_ruptura_frio": ultima.alerta_ruptura_frio, "hace_seg": int((timezone.now() - ultima.registrado_en).total_seconds())},
        "destino": None if orden.direccion.lat is None or not en_vivo else {"lat": orden.direccion.lat, "long": orden.direccion.long, "direccion": str(orden.direccion)},
        "hubo_ruptura": any(l.alerta_ruptura_frio for l in lecturas),
        "serie": [{"t": l.registrado_en.isoformat(), "temp": l.temp_camara} for l in lecturas][-120:],
        "salida_en": orden.despacho.salida_en.isoformat() if orden.despacho.salida_en else None,
        "llegada_en": orden.puerta_en.isoformat() if orden.puerta_en else None,          # cuando el camión llegó a ESTA dirección
        "ruta_url": f"/api/pedidos/{orden.orden_id}/ruta/" if en_vivo else None,
        "itinerario": itinerario_de(orden) if en_vivo else None,
        "entrega": entrega_de(orden),
        **_llegada(orden, ultima),
    }


def fin_de_exposicion(orden, ahora=None):
    """RN-13: hasta cuándo la carga de esta orden estuvo en el camión, y por tanto hasta cuándo cuenta una ruptura de frío para ella. Un viaje
    puede llevar a varios clientes: quien ya recibió no se ve afectado por una falla posterior; quien aún no recibe (en la puerta o con la
    entrega sin concretar) sigue a bordo hasta el regreso. Es la misma regla que `crm.servicios.fin_de_exposicion` (PR de casos de uso):
    cuando ambos estén en `main`, el CRM puede importar esta función y dejar una sola."""
    from django.utils import timezone
    d = orden.despacho
    if orden.estado_orden.nombre in RECEPCION_CERRADA:
        return orden.entrega_resuelta_en or d.llegada_en or ahora or timezone.now()
    return d.regreso_en or ahora or timezone.now()


def mapa_en_vivo(orden):
    """RN-16: el cliente ve el mapa en vivo solo con el pedido «Despachada» (en ruta) o «Camión en la puerta»."""
    return orden.estado_orden.nombre in ("Despachada", "Camión en la puerta")


def itinerario_de(orden):
    """Un único itinerario por pedido: en qué parada del viaje va este pedido y por qué el camión puede pasar antes por otra entrega.
    Solo cuenta paradas («parada 2 de 3», «antes pasamos por otra entrega»): nunca el nombre, la dirección ni las coordenadas de otro cliente.
    Las «anteriores» son las paradas previas del viaje cuyos pedidos siguen «Despachada»; las que el camión ya atendió no cuentan."""
    d = orden.despacho
    marcas = ((d.ruta_geojson or {}).get("paradas") or []) if d else []
    ids = [m["direccion_id"] for m in marcas]
    if orden.direccion_id not in ids:
        return None
    n, total = ids.index(orden.direccion_id), len(ids)
    antes = (Orden.objects.filter(despacho=d, direccion_id__in=ids[:n], estado_orden__nombre="Despachada")
             .values("direccion_id").distinct().count())
    if total == 1:
        texto = "Este viaje lleva solo tu pedido: el camión va directo a tu dirección."
    elif antes:
        otras = "otra entrega" if antes == 1 else f"{antes} entregas más"
        texto = f"Tu pedido es la parada {n + 1} de {total}. Antes pasamos por {otras}, por eso la línea del mapa es una guía hasta tu dirección."
    elif n:
        texto = f"Tu pedido es la parada {n + 1} de {total}. Ya hicimos las entregas anteriores: el camión va directo a tu dirección."
    else:
        texto = f"Tu pedido es la parada 1 de {total}: es la primera entrega del viaje y el camión va directo a tu dirección."
    return {"parada": n + 1, "total": total, "antes": antes, "texto": texto}


def ruta_del_pedido(orden):
    """Lo que el cliente puede ver de la ruta: SOLO el tramo desde donde está el camión hasta la parada de este pedido.

    El viaje guardado puede llevar a varios clientes (base -> parada 1 -> parada 2 -> base) y es el que ve el despachador. El filtro es
    de este lado, el servidor, y no del mapa: la respuesta nunca trae la polilínea completa, las paradas de otros clientes ni los
    tramos de otras entregas, aunque alguien lea el JSON a mano. Si el camión todavía debe pasar por la parada de otro cliente antes
    de llegar a esta, el tramo por calles pasaría por la casa de ese cliente: en ese caso se entrega una línea recta (aproximada)
    entre el camión y esta dirección, que no revela nada de la ruta de los demás."""
    from django.conf import settings

    from flota import rutas
    if orden.despacho_id is None or not mapa_en_vivo(orden):
        return None
    ruta = rutas.asegurar_ruta(orden.despacho)
    propia = next((p for p in (ruta or {}).get("paradas", []) if p["direccion_id"] == orden.direccion_id), None)
    if propia is None:
        return None
    from flota.models import Telemetria
    ultima = Telemetria.objects.filter(camion_id=orden.despacho.camion_id).order_by("-registrado_en").first()
    posicion = (ultima.lat, ultima.long) if ultima else (settings.BASE_LOGISTICA["lat"], settings.BASE_LOGISTICA["long"])
    destino = [propia["lat"], propia["long"]]
    puntos, hasta = ruta["puntos"], propia["indice"]
    actual = min(range(hasta + 1), key=lambda i: rutas.km_entre(puntos[i], posicion))     # el vértice de la ruta más cercano al camión, sin pasarse de esta parada
    antes_de_la_propia = [p for p in ruta["paradas"] if p is not propia and actual < p["indice"] <= hasta]
    if antes_de_la_propia:
        tramo, aproximada = [list(posicion), destino], True
    else:
        tramo, aproximada = [list(posicion)] + [list(p) for p in puntos[actual + 1:hasta + 1]], ruta["aproximada"]
        if len(tramo) == 1 or tramo[-1] != destino:
            tramo.append(destino)
    return {"puntos": tramo, "parada": {"lat": propia["lat"], "long": propia["long"]}, "aproximada": aproximada,
            "km": round(rutas.largo_km(tramo), 2)}


# ---------- llegada estimada y avisos (campanita) ----------
# La velocidad y el factor de calles salen de la configuración (VELOCIDAD_MEDIA_KMH y FACTOR_CALLES) y el simulador IoT usa las mismas
# variables: así la hora de llegada que ve el cliente coincide con el movimiento del camión. Con el tiempo acelerado de la demostración, el
# multiplicador sale de la misma tabla que lee el simulador (flota/tiempo.py): la hora sigue siendo la del reloj, la que de verdad va a llegar.


def _km(lat1, lon1, lat2, lon2):
    from math import asin, cos, radians, sin, sqrt
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 12742 * asin(sqrt(a))


def _redondear5(momento):
    from datetime import timedelta
    return momento.replace(second=0, microsecond=0) - timedelta(minutes=momento.minute % 5)


def _ultima_parada_atendida(orden, ruta, parada):
    """Vértice de la última parada anterior a `parada` que el camión ya atendió (0 si ninguna): desde ahí se mide lo que le falta."""
    anteriores = {p["direccion_id"]: p["indice"] for p in ruta["paradas"] if p["indice"] < parada["indice"]}
    if not anteriores:
        return 0
    pendientes = set(Orden.objects.filter(despacho=orden.despacho, direccion_id__in=anteriores, estado_orden__nombre="Despachada").values_list("direccion_id", flat=True))
    return max((indice for direccion_id, indice in anteriores.items() if direccion_id not in pendientes), default=0)


def _ventana(centro, multiplicador):
    """Ventana de llegada alrededor de la hora estimada. Con tiempo acelerado el viaje entero dura minutos: la ventana de siempre (unos 20 min) no diría nada."""
    from datetime import timedelta
    if multiplicador > 1:
        minuto = centro.replace(second=0, microsecond=0)
        return {"desde": minuto.isoformat(), "hasta": (minuto + timedelta(minutes=2)).isoformat()}
    return {"desde": _redondear5(centro - timedelta(minutes=5)).isoformat(),
            "hasta": (_redondear5(centro + timedelta(minutes=10)) + timedelta(minutes=5)).isoformat()}


def _llegada(orden, ultima):
    """Distancia que falta y ventana estimada de llegada («entre las 15:10 y las 15:30»). Solo mientras el camión va en camino a esta dirección.
    Con la ruta guardada, los km son los que faltan por esa ruta; sin ella, la distancia en línea recta por el factor de calles."""
    from datetime import timedelta
    from django.conf import settings
    from django.utils import timezone
    from flota import tiempo
    multiplicador = tiempo.multiplicador()
    cerca_km = tiempo.umbral_cerca_km(multiplicador)
    vacio = {"km_restantes": None, "eta": None, "cerca": False, "minutos": None, "cerca_km": cerca_km, "tiempo_x": multiplicador}
    d = orden.despacho
    if ultima is None or orden.direccion.lat is None or d.salida_en is None or orden.estado_orden.nombre != "Despachada":
        return vacio
    if timezone.now() - ultima.registrado_en > timedelta(minutes=10):      # sin señal reciente no se inventa una hora
        return vacio
    from flota import rutas
    ruta = d.ruta_geojson
    parada = next((p for p in (ruta or {}).get("paradas", []) if p["direccion_id"] == orden.direccion_id), None)
    if ruta and parada and not ruta.get("aproximada"):
        km = rutas.km_hasta(ruta, (ultima.lat, ultima.long), parada["indice"], _ultima_parada_atendida(orden, ruta, parada))
    else:
        km = _km(ultima.lat, ultima.long, orden.direccion.lat, orden.direccion.long) * settings.FACTOR_CALLES
    minutos = tiempo.minutos_de_viaje(km, multiplicador)
    return {**vacio, "km_restantes": round(km, 1), "cerca": km <= cerca_km, "minutos": max(1, round(minutos)),
            "eta": _ventana(timezone.now() + timedelta(minutes=minutos), multiplicador)}


def en_minutos(minutos):
    """«en cerca de un minuto» / «en unos 4 min»: la hora estimada nunca es exacta, así que no se dice como si lo fuera."""
    return "en cerca de un minuto" if (minutos or 0) <= 1 else f"en unos {minutos} min"


def _resumen_del_pedido(orden, documentos):
    """Datos del pedido que acompañan a cada aviso, para que muestre lo correcto: estado, lo que paga el cliente y su documento
    (el tributario si ya existe: factura o boleta; si no, la guía de despacho). `documentos` es {tipo: Documento} de esta orden."""
    from . import documentos as docs
    elegido = next((documentos[t] for t in ("factura", "boleta", "guia_despacho") if t in documentos), None)
    b2b = orden.direccion.cliente.tipo_cliente.codigo == "B2B"
    return {"estado": orden.estado_orden.nombre, "total_clp": docs.monto_con_iva(orden) if b2b else total_orden(orden), "con_iva": b2b,
            "documento": None if elegido is None else {"tipo": elegido.tipo, "nombre": elegido.get_tipo_display(), "etiqueta": str(elegido)}}


def _accion_del_aviso(aviso, pedido):
    """El botón de cada tipo de aviso lleva a una pantalla que existe y sirve para lo que el aviso dice (la prueba los recorre todos)."""
    n, tipo = aviso["orden_id"], aviso["tipo"]
    if tipo == "puerta" and aviso.get("destacado"):
        return {"texto": "Revisar y recibir", "url": f"/pedidos/{n}/#entrega"}
    if tipo in ("salio", "ventana", "cerca"):
        return {"texto": "Ver dónde va", "url": f"/pedidos/{n}/#seg"}
    if tipo == "llego" and pedido["documento"]:
        return {"texto": f"Ver {pedido['documento']['nombre'].lower()}", "url": f"/pedidos/{n}/#documentos"}
    if tipo == "no_concretada":
        return {"texto": "Escribir a ventas", "url": f"/soporte/?orden={n}"}
    if tipo == "frio":
        return {"texto": "Reportar un problema", "url": f"/soporte/?orden={n}"}
    return {"texto": "Ver pedido", "url": f"/pedidos/{n}/"}


def avisos_de_llegada(cliente):
    """Avisos para la campanita del cliente, calculados desde el estado de sus órdenes (no se guardan): salió, cerca y llegó.
    Cada aviso tiene un id estable para que el navegador sepa cuáles ya vio."""
    from datetime import timedelta
    from django.utils import timezone
    from django.utils.timezone import localtime
    from flota.models import Telemetria

    hace_un_dia = timezone.now() - timedelta(hours=24)
    salida = []
    hora = lambda x: localtime(x).strftime("%H:%M")
    ordenes_listadas = list(ordenes_de(cliente).select_related("despacho__camion", "direccion__cliente__tipo_cliente", "estado_orden"))
    for o in ordenes_listadas:
        d = o.despacho
        if d is None or d.salida_en is None:
            continue
        if (o.entrega_resuelta_en or (d.regreso_en if o.estado_orden.es_final else None) or timezone.now()) < hace_un_dia:
            continue
        nombre = o.estado_orden.nombre
        salida.append({"id": f"{o.orden_id}-salio", "orden_id": o.orden_id, "tipo": "salio", "cuando": d.salida_en.isoformat(),
                       "texto": f"Tu pedido N.º {o.orden_id} salió a las {hora(d.salida_en)}."})
        if o.puerta_en:
            salida.append({"id": f"{o.orden_id}-puerta", "orden_id": o.orden_id, "tipo": "puerta", "cuando": o.puerta_en.isoformat(),
                           "destacado": nombre == "Camión en la puerta",       # espera tu respuesta: la pantalla lo muestra como banner, no solo en la campanita
                           "texto": f"Estamos afuera de tu dirección con tu pedido N.º {o.orden_id}. Revísalo y confírmanos si lo recibiste."
                           if nombre == "Camión en la puerta" else f"El camión llegó a tu dirección con el pedido N.º {o.orden_id} a las {hora(o.puerta_en)}."})
        if nombre == "Entregada" and o.entrega_resuelta_en:
            rechazadas = unidades_rechazadas(o)
            salida.append({"id": f"{o.orden_id}-llego", "orden_id": o.orden_id, "tipo": "llego", "cuando": o.entrega_resuelta_en.isoformat(),
                           "texto": f"Recibiste parte de tu pedido N.º {o.orden_id} a las {hora(o.entrega_resuelta_en)}: rechazaste {rechazadas} unidad{'es' if rechazadas != 1 else ''}."
                           if rechazadas else f"Tu pedido N.º {o.orden_id} quedó entregado a las {hora(o.entrega_resuelta_en)} (confirmado automáticamente)."
                           if o.entrega_automatica else f"Pedido entregado exitosamente: tu pedido N.º {o.orden_id} quedó entregado a las {hora(o.entrega_resuelta_en)}."})
        if nombre == "Entrega no concretada":
            salida.append({"id": f"{o.orden_id}-no-concretada", "orden_id": o.orden_id, "tipo": "no_concretada",
                           "cuando": (o.entrega_resuelta_en or o.puerta_en or d.salida_en).isoformat(),
                           "texto": f"No pudimos entregar tu pedido N.º {o.orden_id}. Nuestro equipo te contactará para reprogramar."})
        if nombre == RECHAZADA:
            salida.append({"id": f"{o.orden_id}-rechazada", "orden_id": o.orden_id, "tipo": "rechazada", "cuando": (o.entrega_resuelta_en or o.puerta_en or d.salida_en).isoformat(),
                           "texto": f"Registramos que rechazaste tu pedido N.º {o.orden_id} al recibirlo. No se te cobra y ventas te contactará."})
        if nombre != "Despachada":
            continue
        ultima = Telemetria.objects.filter(camion=d.camion, registrado_en__gte=d.salida_en).order_by("-registrado_en").first()
        if Telemetria.objects.filter(camion=d.camion, camara=o.camara, registrado_en__gte=max(d.salida_en, timezone.now() - timedelta(hours=1)), alerta_ruptura_frio=True).exists():
            salida.append({"id": f"{o.orden_id}-frio", "orden_id": o.orden_id, "tipo": "frio", "cuando": (ultima.registrado_en if ultima else d.salida_en).isoformat(),
                           "texto": f"Detectamos una variación de temperatura en el camión de tu pedido N.º {o.orden_id}. Ya la estamos revisando."})
        info = _llegada(o, ultima)
        if info["eta"]:
            desde, hasta = (localtime(timezone.datetime.fromisoformat(info["eta"][k])).strftime("%H:%M") for k in ("desde", "hasta"))
            salida.append({"id": f"{o.orden_id}-ventana", "orden_id": o.orden_id, "tipo": "ventana", "cuando": ultima.registrado_en.isoformat(),
                           "texto": f"Recibirás tu pedido N.º {o.orden_id} entre las {desde} y las {hasta}."})
        if info["cerca"]:
            salida.append({"id": f"{o.orden_id}-cerca", "orden_id": o.orden_id, "tipo": "cerca", "cuando": ultima.registrado_en.isoformat(),
                           "destacado": True, "minutos": info["minutos"],
                           "texto": f"Tu pedido N.º {o.orden_id} está por llegar: el camión está a menos de {info['cerca_km']} km (llega {en_minutos(info['minutos'])}). Deja a alguien listo para recibirlo."})
    if salida:
        from .models import Documento
        docs_de = {}
        for doc in Documento.objects.filter(orden_id__in={a["orden_id"] for a in salida}).exclude(tipo="nota_credito"):
            docs_de.setdefault(doc.orden_id, {})[doc.tipo] = doc
        resumen = {o.orden_id: _resumen_del_pedido(o, docs_de.get(o.orden_id, {})) for o in ordenes_listadas if o.orden_id in {a["orden_id"] for a in salida}}
        for a in salida:
            a["pedido"] = resumen[a["orden_id"]]
            a["accion"] = _accion_del_aviso(a, a["pedido"])
    return sorted(salida, key=lambda a: a["cuando"], reverse=True)


# ---------- entrega en la puerta (RN-15): el camión llega, el cliente confirma o explica ----------
MOTIVO_MINIMO = 5


def _estado(nombre):
    return EstadoOrden.objects.get(nombre=nombre)


def entrega_de(orden):
    """Estado de la entrega para la pantalla del cliente: si puede confirmar, cuánto tiempo le queda y qué decidió."""
    from datetime import timedelta

    from django.conf import settings
    from django.utils import timezone
    nombre = orden.estado_orden.nombre
    limite = orden.puerta_en + timedelta(seconds=settings.CONFIRMACION_AUTO_SEG) if orden.puerta_en else None
    return {"estado": nombre, "puede_responder": nombre == "Camión en la puerta",
            "puerta_en": orden.puerta_en.isoformat() if orden.puerta_en else None,
            "se_confirma_sola_en_seg": max(0, int((limite - timezone.now()).total_seconds())) if limite and nombre == "Camión en la puerta" else None,
            "resuelta_en": orden.entrega_resuelta_en.isoformat() if orden.entrega_resuelta_en else None,
            "motivo": orden.entrega_motivo or None, "automatica": orden.entrega_automatica, "unidades_rechazadas": unidades_rechazadas(orden)}


# Qué puede haber fallado al recibir. La etiqueta es lo que ve el cliente; la categoría es la del CRM a la que va el reclamo (None = la
# clasifica la IA, como cualquier consulta). Las etiquetas viven en el modelo porque también son el motivo de rechazo de cada línea.
_CATEGORIA_DEL_PROBLEMA = {"temperatura": "Reclamo por temperatura", "faltante": "Problema en la entrega", "danado": "Problema en la entrega", "otro": None}
PROBLEMAS_AL_RECIBIR = {codigo: (etiqueta, _CATEGORIA_DEL_PROBLEMA[codigo]) for codigo, etiqueta in OrdenItem.MOTIVOS_RECHAZO}
ASUNTO_RECLAMO_AL_RECIBIR = "Problema al recibir el pedido"


def revision_de(orden):
    """Lo que el cliente revisa antes de confirmar que recibió: los productos con sus cantidades y la temperatura del viaje
    (el mismo dato de `seguimiento`, la última hora del camión). `temperatura` es None si el camión no tiene lecturas."""
    productos = [{"producto_id": i.producto_id, "producto": i.producto.nombre, "cantidad": i.cantidad} for i in orden.ordenitem_set.select_related("producto").order_by("producto__nombre")]
    seg = seguimiento(orden)
    temperatura = None
    if seg and seg["ultima"]:
        temps = [p["temp"] for p in seg["serie"]] or [seg["ultima"]["temp_camara"]]
        banda = seg["banda"]
        temperatura = {"ultima": seg["ultima"]["temp_camara"], "minima": min(temps), "maxima": max(temps), "banda": banda,
                       "hubo_ruptura": seg["hubo_ruptura"] or seg["ultima"]["alerta_ruptura_frio"],
                       "en_rango": not (seg["hubo_ruptura"] or seg["ultima"]["alerta_ruptura_frio"]) and banda["min"] <= seg["ultima"]["temp_camara"] <= banda["max"]}
    ya_tiene_documento = documentos.Documento.objects.filter(orden=orden, tipo__in=documentos.COBRABLES).exists()
    return {"orden_id": orden.orden_id, "recibe": orden.quien_recibe, "productos": productos, "temperatura": temperatura,
            "problemas": [{"codigo": k, "etiqueta": v[0]} for k, v in PROBLEMAS_AL_RECIBIR.items()],
            "efecto": ("Lo que aceptas queda entregado. Lo rechazado se rebaja con una nota de crédito y lo que ya pagaste por eso se te devuelve."
                       if ya_tiene_documento else "Lo que aceptas queda entregado y la factura se emite solo por eso. Lo rechazado no se cobra.")}


def unidades_rechazadas(orden):
    return sum(i.cantidad_rechazada for i in orden.ordenitem_set.all())


def rechazo_de(orden):
    """Lo que el cliente rechazó al recibir, para su pantalla y para el CRM; None si no rechazó nada (la mayoría de los pedidos)."""
    items = list(orden.ordenitem_set.select_related("producto").order_by("producto__nombre"))
    if not any(i.cantidad_rechazada for i in items):
        return None
    nota, devuelto = documentos.nota_de_rechazo(orden)
    return {"lineas": [{"producto": i.producto.nombre, "cantidad": i.cantidad, "rechazada": i.cantidad_rechazada, "aceptada": i.cantidad_aceptada,
                        "motivo": i.get_motivo_rechazo_display()} for i in items if i.cantidad_rechazada],
            "unidades": sum(i.cantidad_rechazada for i in items), "total": not any(i.cantidad_aceptada for i in items),
            "monto": documentos.monto_rechazado(orden), "nota": nota, "devuelto": devuelto}


def _leer_rechazos(orden, rechazos):
    """Valida lo que llegó del formulario: {producto_id: (cantidad, motivo)}. Devuelve [(línea, cantidad, motivo)] solo con lo rechazado de verdad.
    Rechazar 0 es lo normal y no pide motivo; un producto ajeno, un número inválido o más de lo pedido detienen la operación completa."""
    lineas = {i.producto_id: i for i in orden.ordenitem_set.select_for_update(of=("self",)).select_related("producto")}
    salida = []
    for producto_id, (cantidad, motivo) in (rechazos or {}).items():
        item = lineas.get(producto_id)
        if item is None:
            raise ErrorDeNegocio("Ese producto no es parte de este pedido.")
        try:
            n = 0 if cantidad in ("", None) else entradas.entero(cantidad)
        except ValueError:
            raise ErrorDeNegocio(f"Indica cuántas unidades de {item.producto.nombre} rechazas, con un número entre 0 y {item.cantidad}.")
        if n > item.cantidad:
            raise ErrorDeNegocio(f"No puedes rechazar más de lo que pediste: de {item.producto.nombre} pediste {item.cantidad}.")
        if n == 0:
            continue
        if motivo not in PROBLEMAS_AL_RECIBIR:
            raise ErrorDeNegocio(f"Elige el motivo del rechazo de {item.producto.nombre}.")
        salida.append((item, n, motivo))
    return salida


def _categoria_del_rechazo(motivos):
    """Un rechazo con varios motivos va a una sola bandeja: la temperatura manda (cadena de frío); sin categoría conocida, la clasifica la IA."""
    categorias = [_CATEGORIA_DEL_PROBLEMA[m] for m in motivos]
    return "Reclamo por temperatura" if "Reclamo por temperatura" in categorias else next((c for c in categorias if c), None)


def _reclamo_de_rechazo(cliente, orden, rechazadas, comentario, total):
    """El requerimiento para ventas: qué rechazó, por qué y qué pasó con el dinero. Va ligado a la orden, igual que cualquier reclamo al recibir."""
    from crm import servicios as crm
    detalle = [f"- {n} de {item.cantidad} {item.producto.nombre}: {item.get_motivo_rechazo_display()}" for item, n, _ in rechazadas]
    partes = ["El cliente rechazó al recibir:", *detalle]
    if comentario:
        partes.append(f"Comentario del cliente: {comentario[:500]}")
    nota, devuelto = documentos.nota_de_rechazo(orden)
    if nota:
        partes.append(f"Se emitió {nota} por {documentos._clp(nota.monto_clp)}" + (f"; se devolvieron {documentos._clp(devuelto)}." if devuelto else "."))
    elif total:
        partes.append("No hay documento que rebajar y este pedido no se factura.")
    else:
        partes.append("Aún no tiene factura: se emite solo por lo aceptado.")
    resultado = "Rechazo total" if total else "Recepción parcial"
    return crm.crear_requerimiento(cliente, f"{ASUNTO_RECLAMO_AL_RECIBIR} N.º {orden.pk}: {resultado}", "\n".join(partes)[:crm.TEXTO_MAXIMO], orden=orden,
                                   categoria_nombre=_categoria_del_rechazo([m for _, _, m in rechazadas]))


def resolver_entrega(cliente, orden_id, accion, motivo="", con_problema=False, tipo_problema="otro", rechazos=None):
    """El cliente responde al aviso «estamos afuera». Los desenlaces, siempre solo mientras la orden está «Camión en la puerta»:
    - `aceptar`: revisó y todo llegó bien; queda «Entregada».
    - `aceptar` con `con_problema` (y en `motivo` qué falló): recibió el pedido pero algo falló. Queda «Entregada» (el camión sí entregó) y se
      crea un requerimiento para ventas ligado a la orden, que es el reclamo; sin tablas nuevas.
    - `aceptar` con `rechazos` ({producto_id: (cantidad, motivo)}): RN-23, recepción parcial. Se guarda lo rechazado por línea, se rebaja el documento
      si ya existe y queda el reclamo. El stock no se repone: en cadena de frío lo rechazado no vuelve a la venta sin revisión.
      Si rechaza todas las unidades queda «Rechazada en recepción» (final): el camión llegó y el cliente decidió no recibir.
    - `no_recibido` con el motivo: no pudo recibirlo, nadie revisó la mercadería; queda «Entrega no concretada» (no final) y se crea un requerimiento para ventas.
    Si el plazo la dio por entregada o ya respondió, no cambia nada y se informa."""
    from django.utils import timezone
    motivo = (motivo or "").strip()
    if accion not in ("aceptar", "no_recibido"):
        raise ErrorDeNegocio("Elige «Recibí mi pedido» o «No pude recibirlo».")
    if accion == "no_recibido" and len(motivo) < MOTIVO_MINIMO:
        raise ErrorDeNegocio("Cuéntanos por qué no pudiste recibirlo (al menos unas palabras).")
    if accion == "aceptar" and con_problema and tipo_problema not in PROBLEMAS_AL_RECIBIR:
        tipo_problema = "otro"
    with transaction.atomic():
        orden = ordenes_de(cliente).select_for_update(of=("self",)).filter(pk=orden_id).first()
        if orden is None:
            raise ErrorDeNegocio("Orden no encontrada.")
        if orden.estado_orden.nombre != "Camión en la puerta":
            raise ErrorDeNegocio(f"El pedido está «{orden.estado_orden.nombre}»: ya no hay una entrega por confirmar.")
        rechazadas = _leer_rechazos(orden, rechazos) if accion == "aceptar" else []
        sin_explicar = accion == "aceptar" and (any(m == "otro" for _, _, m in rechazadas) or (con_problema and not rechazadas))      # el motivo de cada línea ya explica, salvo «Otro problema»
        if sin_explicar and len(motivo) < MOTIVO_MINIMO:
            raise ErrorDeNegocio("Cuéntanos qué falló en tu pedido (al menos unas palabras) o marca que todo llegó bien.")
        for item, n, codigo in rechazadas:
            item.cantidad_rechazada, item.motivo_rechazo = n, codigo
            item.save(update_fields=["cantidad_rechazada", "motivo_rechazo"])
        rechazo_total = bool(rechazadas) and not any(i.cantidad_aceptada for i in orden.ordenitem_set.all())
        orden.estado_orden = _estado("Entrega no concretada" if accion == "no_recibido" else RECHAZADA if rechazo_total else "Entregada")
        orden.entrega_resuelta_en = timezone.now()
        orden.entrega_automatica = False
        if accion == "no_recibido" or rechazo_total:
            orden.entrega_motivo = motivo[:500]
        orden.save(update_fields=["estado_orden", "entrega_resuelta_en", "entrega_automatica", "entrega_motivo"])
        if rechazadas:
            documentos.rebajar_por_rechazo(orden, "; ".join(f"{n} de {item.cantidad} {item.producto.nombre}" for item, n, _ in rechazadas)[:170])
        cerrar_entregas_sin_pendientes([orden.despacho_id])
    from crm import servicios as crm
    if rechazadas:
        _reclamo_de_rechazo(orden.direccion.cliente, orden, rechazadas, motivo, rechazo_total)
    elif accion == "no_recibido":
        crm.crear_requerimiento(orden.direccion.cliente, f"Entrega no concretada del pedido N.º {orden.pk}", motivo, orden=orden)
    elif con_problema:
        etiqueta, categoria = PROBLEMAS_AL_RECIBIR[tipo_problema]
        crm.crear_requerimiento(orden.direccion.cliente, f"{ASUNTO_RECLAMO_AL_RECIBIR} N.º {orden.pk}: {etiqueta}", motivo[:500], orden=orden,
                                categoria_nombre=categoria)
    return orden


def reclamo_al_recibir(orden):
    """El reclamo que el cliente dejó al recibir este pedido (si lo hizo), para mostrárselo en la pantalla del pedido."""
    from crm.models import Requerimiento
    return Requerimiento.objects.filter(orden=orden, asunto__startswith=ASUNTO_RECLAMO_AL_RECIBIR).order_by("-creado_en").first()


def confirmar_vencidas(ahora=None):
    """Da por entregadas («confirmada automáticamente») las órdenes cuyo camión lleva más de CONFIRMACION_AUTO_SEG en la puerta sin
    respuesta. No rechaza nada: el silencio del cliente no es un rechazo, así que se factura el pedido completo. Es una sola sentencia condicional sobre el estado: si el cliente ya respondió entre medio no coincide, y repetirla
    (el simulador y la web la ejecutan) no cambia nada. Devuelve cuántas órdenes cambió."""
    from datetime import timedelta

    from django.conf import settings
    from django.utils import timezone
    ahora = ahora or timezone.now()
    vencidas = Orden.objects.filter(estado_orden__nombre="Camión en la puerta", puerta_en__lte=ahora - timedelta(seconds=settings.CONFIRMACION_AUTO_SEG))
    despachos = list(vencidas.values_list("despacho_id", flat=True).distinct())
    n = vencidas.update(estado_orden=_estado("Entregada"), entrega_resuelta_en=ahora, entrega_automatica=True)
    if n:
        cerrar_entregas_sin_pendientes(despachos)
    return n


def cerrar_entregas_sin_pendientes(despachos):
    """Si uno de estos viajes ya no tiene pedidos en camino ni en la puerta, su recorrido de entregas queda finalizado.

    No cierra un viaje que todavía debe atender otra parada. No marca el regreso a la bodega: eso lo registra el
    simulador cuando el camión llega. Poner `llegada_en` avisa que la última entrega ya se cerró."""
    from django.db.models import Exists, OuterRef
    from django.db.models.functions import Coalesce, Greatest, Now

    from flota.models import Despacho

    pendiente = Orden.objects.filter(despacho_id=OuterRef("pk"), estado_orden__nombre__in=("Despachada", "Camión en la puerta"))
    return Despacho.objects.filter(pk__in=despachos, salida_en__isnull=False, regreso_en__isnull=True).exclude(fase="volviendo").annotate(
        hay_pendiente=Exists(pendiente)).filter(hay_pendiente=False).update(
        fase="volviendo", llegada_en=Greatest(Coalesce(F("llegada_en"), Now()), F("salida_en")))


def llegar_a_la_puerta(ordenes, ahora=None):
    """El camión llegó a la dirección de estas órdenes: las que iban «Despachada» pasan a «Camión en la puerta» y empieza a correr
    el plazo del cliente. Condicional sobre el estado, por lo que repetirla no hace nada. Devuelve cuántas cambió."""
    from django.utils import timezone
    ahora = ahora or timezone.now()
    return Orden.objects.filter(pk__in=[o.pk if hasattr(o, "pk") else o for o in ordenes], estado_orden__nombre="Despachada").update(
        estado_orden=_estado("Camión en la puerta"), puerta_en=ahora)
