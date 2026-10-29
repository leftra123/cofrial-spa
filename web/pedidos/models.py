from django.db import models
from django.db.models import Q

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
    creada_en = models.DateTimeField(auto_now_add=True)
    puerta_en = models.DateTimeField(null=True, blank=True)                  # el camión llegó a la dirección: desde aquí corre la confirmación del cliente
    entrega_resuelta_en = models.DateTimeField(null=True, blank=True)        # cuando el cliente (o el tiempo) cerró la entrega
    entrega_motivo = models.TextField(blank=True)                            # por qué el cliente no pudo recibir
    entrega_automatica = models.BooleanField(default=False, db_default=False)    # se dio por entregada sola al vencer el plazo

    class Meta:
        db_table = "orden"
        verbose_name_plural = "órdenes"
        indexes = [models.Index(fields=["creada_en"], name="idx_orden_creada")]

    def __str__(self):
        return f"Orden {self.orden_id}"


class OrdenItem(models.Model):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.IntegerField()
    precio_unitario_clp = models.IntegerField()

    class Meta:
        db_table = "orden_item"
        constraints = [
            models.UniqueConstraint(fields=["orden", "producto"], name="uq_orden_producto"),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="orden_cantidad_positiva"),
            models.CheckConstraint(condition=Q(precio_unitario_clp__gt=0), name="orden_precio_positivo"),
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


class Pago(models.Model):
    """Pago recibido contra una boleta o factura. Un monto negativo es una devolución al cliente."""
    MEDIOS = [("webpay", "Webpay (simulado)"), ("transferencia", "Transferencia"), ("cheque", "Cheque"), ("efectivo", "Efectivo"), ("devolucion", "Devolución")]
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
