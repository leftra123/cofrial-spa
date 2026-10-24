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
