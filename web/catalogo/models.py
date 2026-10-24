from django.db import models
from django.db.models import Q


class RangoTemperatura(models.Model):
    """Define cuándo una lectura de temperatura es crítica."""
    rango_temperatura_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=40, unique=True)
    temp_min_c = models.DecimalField(max_digits=5, decimal_places=1)
    temp_max_c = models.DecimalField(max_digits=5, decimal_places=1)

    class Meta:
        db_table = "rango_temperatura"
        constraints = [models.CheckConstraint(condition=Q(temp_min_c__lt=models.F("temp_max_c")), name="rango_min_menor_max")]

    def __str__(self):
        return f"{self.nombre} ({self.temp_min_c} a {self.temp_max_c} °C)"


class Categoria(models.Model):
    categoria_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60, unique=True)
    rango_temperatura = models.ForeignKey(RangoTemperatura, on_delete=models.PROTECT)

    class Meta:
        db_table = "categoria"

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    UNIDADES = [("kg", "kg"), ("un", "un"), ("caja", "caja")]
    producto_id = models.AutoField(primary_key=True)
    sku = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    unidad_medida = models.CharField(max_length=10, choices=UNIDADES)
    stock_disponible = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "producto"
        constraints = [models.CheckConstraint(condition=Q(stock_disponible__gte=0), name="stock_no_negativo")]

    def __str__(self):
        return f"{self.sku} {self.nombre}"


class ListaPrecio(models.Model):
    lista_precio_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        db_table = "lista_precio"

    def __str__(self):
        return self.nombre


class PrecioProducto(models.Model):
    """Precio de un producto en una lista. Par (lista, producto) único: reemplaza la clave compuesta (decisión D-03)."""
    lista_precio = models.ForeignKey(ListaPrecio, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    precio_clp = models.IntegerField()

    class Meta:
        db_table = "precio_producto"
        constraints = [
            models.UniqueConstraint(fields=["lista_precio", "producto"], name="uq_precio_lista_producto"),
            models.CheckConstraint(condition=Q(precio_clp__gt=0), name="precio_positivo"),
        ]


class AvisoStock(models.Model):
    """Un cliente pide que se le avise cuando haya al menos cierta cantidad de un producto sin stock suficiente.

    No hay envío de correo: el aviso aparece en «Mis avisos» y en la barra de la tienda en cuanto el stock alcanza la cantidad
    pedida, y el CRM lo ve como demanda en espera. Se da por atendido cuando el cliente agrega el producto al carrito."""
    aviso_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad_minima = models.PositiveIntegerField()
    creado_en = models.DateTimeField(auto_now_add=True)
    atendido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "aviso_stock"
        constraints = [
            models.CheckConstraint(condition=Q(cantidad_minima__gte=1), name="aviso_cantidad_positiva"),
            models.UniqueConstraint(fields=["cliente", "producto"], condition=Q(atendido_en__isnull=True), name="uq_aviso_pendiente"),
        ]
