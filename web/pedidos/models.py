from django.db import models
from django.db.models import F, Q

from catalogo.models import Producto
from clientes.models import Cliente, Direccion
from flota.models import Despacho


class Carrito(models.Model):
    ESTADOS = [("abierto", "abierto"), ("convertido", "convertido"), ("abandonado", "abandonado")]
    carrito_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    estado = models.CharField(max_length=12, choices=ESTADOS, default="abierto")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "carrito"
        constraints = [models.UniqueConstraint(fields=["cliente"], condition=Q(estado="abierto"), name="uq_carrito_abierto")]


class CarritoItem(models.Model):
    """El precio no se guarda: se calcula con la lista del cliente."""
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.IntegerField()

    class Meta:
        db_table = "carrito_item"
        constraints = [
            models.UniqueConstraint(fields=["carrito", "producto"], name="uq_carrito_producto"),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="carrito_cantidad_positiva"),
        ]


class EstadoOrden(models.Model):
    estado_orden_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30, unique=True)
    orden_flujo = models.SmallIntegerField(unique=True)
    es_final = models.BooleanField(default=False)

    class Meta:
        db_table = "estado_orden"
        verbose_name_plural = "estados de orden"
        ordering = ["orden_flujo"]

    def __str__(self):
        return self.nombre


class Orden(models.Model):
    """El cliente, el canal y el total se obtienen por consulta (vistas v_orden y v_orden_total), no se guardan."""
    orden_id = models.AutoField(primary_key=True)
    direccion = models.ForeignKey(Direccion, on_delete=models.PROTECT)
    estado_orden = models.ForeignKey(EstadoOrden, on_delete=models.PROTECT)
    despacho = models.ForeignKey(Despacho, null=True, blank=True, on_delete=models.SET_NULL)
    numero_oc = models.CharField(max_length=30, blank=True)
    oc_pendiente = models.BooleanField(default=False, db_default=False)       # B2B que compró sin su OC: numero_oc lleva una referencia WEB-aaaa-nnnn hasta que la agregue
    COMPROBANTES = [("boleta", "Boleta"), ("factura", "Factura")]
    comprobante = models.CharField(max_length=8, choices=COMPROBANTES, default="boleta", db_default="boleta")
    creada_en = models.DateTimeField(auto_now_add=True)
    puerta_en = models.DateTimeField(null=True, blank=True)                  # el camión llegó a la dirección: desde aquí corre la confirmación del cliente
    entrega_resuelta_en = models.DateTimeField(null=True, blank=True)        # cuando el cliente (o el tiempo) cerró la entrega
    entrega_motivo = models.TextField(blank=True)                            # por qué el cliente no pudo recibir
    entrega_automatica = models.BooleanField(default=False, db_default=False)    # se dio por entregada sola al vencer el plazo
    checkout_pago = models.ForeignKey("CheckoutPago", null=True, blank=True, on_delete=models.SET_NULL, related_name="ordenes")
    recibe_nombre = models.CharField(max_length=80, blank=True, default="", db_default="")      # quién recibe el pedido, elegido por el comprador; vacío = pedidos anteriores (recibe el titular)

    @property
    def quien_recibe(self):
        """Nombre de quien recibe: el elegido al comprar o, en pedidos anteriores a este campo, el titular de la cuenta."""
        return self.recibe_nombre or self.direccion.cliente.nombre

    class Meta:
        db_table = "orden"
        verbose_name_plural = "órdenes"
        indexes = [models.Index(fields=["creada_en"], name="idx_orden_creada")]
        constraints = [models.CheckConstraint(condition=Q(comprobante__in=["boleta", "factura"]), name="orden_comprobante_valido")]

    def __str__(self):
        return f"Orden {self.orden_id}"


class OrdenItem(models.Model):
    """Línea de la orden. `cantidad` es lo pedido y no cambia; lo aceptado se calcula (cantidad - cantidad_rechazada), no se guarda."""
    MOTIVOS_RECHAZO = [("temperatura", "Los productos llegaron tibios o descongelados"), ("faltante", "Faltan o sobran productos"),
                       ("danado", "Producto dañado o en mal estado"), ("otro", "Otro problema")]
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.IntegerField()
    precio_unitario_clp = models.IntegerField()
    cantidad_rechazada = models.IntegerField(default=0, db_default=0)                                # RN-23: unidades que el cliente no aceptó al recibir
    motivo_rechazo = models.CharField(max_length=12, choices=MOTIVOS_RECHAZO, blank=True, default="", db_default="")      # vacío si no rechazó nada

    @property
    def cantidad_aceptada(self):
        return self.cantidad - self.cantidad_rechazada

    class Meta:
        db_table = "orden_item"
        constraints = [
            models.UniqueConstraint(fields=["orden", "producto"], name="uq_orden_producto"),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="orden_cantidad_positiva"),
            models.CheckConstraint(condition=Q(precio_unitario_clp__gt=0), name="orden_precio_positivo"),
            models.CheckConstraint(condition=Q(cantidad_rechazada__gte=0, cantidad_rechazada__lte=F("cantidad")), name="orden_item_rechazo_en_rango"),
            models.CheckConstraint(condition=Q(cantidad_rechazada=0, motivo_rechazo="") | Q(cantidad_rechazada__gt=0, motivo_rechazo__in=["temperatura", "faltante", "danado", "otro"]),
                                   name="orden_item_rechazo_con_motivo"),
        ]


class Documento(models.Model):
    """Documento tributario simulado (no se conecta al SII). Boleta: venta al público; factura: venta a empresa;
    guía de despacho: ampara el traslado; nota de crédito: anula o rebaja un documento anterior.
    El monto se guarda porque el documento es una foto de lo vendido, igual que el precio congelado de la línea."""
    TIPOS = [("boleta", "Boleta"), ("factura", "Factura"), ("guia_despacho", "Guía de despacho"), ("nota_credito", "Nota de crédito")]
    documento_id = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=14, choices=TIPOS)
    folio = models.PositiveIntegerField()
    orden = models.ForeignKey(Orden, on_delete=models.PROTECT)
    referencia = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)    # la nota de crédito apunta al documento que rebaja
    monto_clp = models.IntegerField(null=True, blank=True)       # total con IVA; la guía no cobra
    vence_en = models.DateField(null=True, blank=True)           # solo facturas a crédito
    motivo = models.CharField(max_length=200, blank=True)        # solo notas de crédito
    emitido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "documento"
        indexes = [models.Index(fields=["vence_en"], name="idx_documento_vence")]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "folio"], name="uq_documento_folio"),
            models.UniqueConstraint(fields=["orden", "tipo"], condition=Q(tipo__in=["boleta", "factura", "guia_despacho"]), name="uq_documento_orden_tipo"),
            models.CheckConstraint(condition=~Q(tipo="nota_credito") | (Q(referencia__isnull=False) & ~Q(motivo="")), name="nota_credito_con_referencia_y_motivo"),
            models.CheckConstraint(condition=Q(tipo="guia_despacho") | Q(monto_clp__gt=0), name="documento_monto_positivo"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} N.º {self.folio}"


class CheckoutPago(models.Model):
    """Intento de pago B2C vía Mercado Pago antes de materializar órdenes en la BD."""
    ESTADOS = [("pendiente", "Esperando pago"), ("completado", "Completado"), ("fallido", "Fallido")]
    checkout_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    direccion = models.ForeignKey(Direccion, on_delete=models.PROTECT)
    numero_oc = models.CharField(max_length=30, blank=True)
    recibe_nombre = models.CharField(max_length=80, blank=True, default="", db_default="")      # lo elegido en el carrito; se copia a las órdenes cuando el pago se aprueba
    comprobante = models.CharField(max_length=8, choices=Orden.COMPROBANTES, default="boleta", db_default="boleta")
    monto_clp = models.IntegerField()
    preference_id = models.CharField(max_length=64, blank=True)
    external_reference = models.CharField(max_length=64, unique=True)
    payment_id = models.CharField(max_length=64, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default="pendiente")
    primera_orden_id = models.IntegerField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checkout_pago"


class Pago(models.Model):
    """Pago recibido contra una boleta o factura. Un monto negativo es una devolución al cliente."""
    MEDIOS = [("webpay", "Webpay (simulado)"), ("mercadopago", "Mercado Pago"), ("transferencia", "Transferencia"),
              ("cheque", "Cheque"), ("efectivo", "Efectivo"), ("devolucion", "Devolución")]
    pago_id = models.AutoField(primary_key=True)
    documento = models.ForeignKey(Documento, on_delete=models.PROTECT)
    monto_clp = models.IntegerField()
    medio = models.CharField(max_length=14, choices=MEDIOS)
    referencia = models.CharField(max_length=60, blank=True)     # n.º de transferencia o de autorización
    pagado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pago"
        constraints = [models.CheckConstraint(condition=~Q(monto_clp=0), name="pago_monto_distinto_de_cero")]

    def __str__(self):
        return f"Pago {self.pago_id} de {self.monto_clp}"
