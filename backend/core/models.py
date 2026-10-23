"""Modelos sin migración (managed=False) sobre el esquema de informe/modelo/esquema.sql."""
from django.db import models
from django.db.models.functions import Now


class RangoTemperatura(models.Model):
    rango_temperatura_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=40)
    temp_min_c = models.DecimalField(max_digits=5, decimal_places=1)
    temp_max_c = models.DecimalField(max_digits=5, decimal_places=1)

    class Meta:
        managed = False
        db_table = "rango_temperatura"


class Categoria(models.Model):
    categoria_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60)
    rango_temperatura = models.ForeignKey(RangoTemperatura, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = "categoria"


class Producto(models.Model):
    producto_id = models.AutoField(primary_key=True)
    sku = models.CharField(max_length=30)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(null=True)
    categoria = models.ForeignKey(Categoria, models.DO_NOTHING)
    unidad_medida = models.CharField(max_length=10)
    stock_disponible = models.IntegerField()
    activo = models.BooleanField()

    class Meta:
        managed = False
        db_table = "producto"


class ListaPrecio(models.Model):
    lista_precio_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60)

    class Meta:
        managed = False
        db_table = "lista_precio"


class PrecioProducto(models.Model):
    pk = models.CompositePrimaryKey("lista_precio_id", "producto_id")
    lista_precio = models.ForeignKey(ListaPrecio, models.DO_NOTHING)
    producto = models.ForeignKey(Producto, models.DO_NOTHING)
    precio_clp = models.IntegerField()

    class Meta:
        managed = False
        db_table = "precio_producto"


class Comuna(models.Model):
    comuna_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60)

    class Meta:
        managed = False
        db_table = "comuna"


class TipoCliente(models.Model):
    tipo_cliente_id = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=3)
    nombre = models.CharField(max_length=40)
    lista_precio = models.ForeignKey(ListaPrecio, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = "tipo_cliente"


class Usuario(models.Model):
    usuario_id = models.AutoField(primary_key=True)
    email = models.CharField(max_length=120)
    password_hash = models.CharField(max_length=255)
    rol = models.CharField(max_length=20)
    activo = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "usuario"


class Cliente(models.Model):
    cliente_id = models.AutoField(primary_key=True)
    usuario_id = models.IntegerField(null=True)
    tipo_cliente = models.ForeignKey(TipoCliente, models.DO_NOTHING)
    rut = models.CharField(max_length=12)
    nombre = models.CharField(max_length=120)
    email = models.CharField(max_length=120)

    class Meta:
        managed = False
        db_table = "cliente"


class Direccion(models.Model):
    direccion_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, models.DO_NOTHING)
    calle_numero = models.CharField(max_length=150)
    comuna = models.ForeignKey(Comuna, models.DO_NOTHING)
    es_principal = models.BooleanField()

    class Meta:
        managed = False
        db_table = "direccion"


class Carrito(models.Model):
    carrito_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, models.DO_NOTHING)
    estado = models.CharField(max_length=12, default="abierto")
    creado_en = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "carrito"


class CarritoItem(models.Model):
    pk = models.CompositePrimaryKey("carrito_id", "producto_id")
    carrito = models.ForeignKey(Carrito, models.DO_NOTHING)
    producto = models.ForeignKey(Producto, models.DO_NOTHING)
    cantidad = models.IntegerField()

    class Meta:
        managed = False
        db_table = "carrito_item"


class EstadoOrden(models.Model):
    estado_orden_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30)
    orden_flujo = models.SmallIntegerField()

    class Meta:
        managed = False
        db_table = "estado_orden"


class Orden(models.Model):
    orden_id = models.AutoField(primary_key=True)
    direccion = models.ForeignKey(Direccion, models.DO_NOTHING)
    estado_orden = models.ForeignKey(EstadoOrden, models.DO_NOTHING)
    despacho_id = models.IntegerField(null=True)
    numero_oc = models.CharField(max_length=30, null=True)
    creada_en = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "orden"


class OrdenItem(models.Model):
    pk = models.CompositePrimaryKey("orden_id", "producto_id")
    orden = models.ForeignKey(Orden, models.DO_NOTHING)
    producto = models.ForeignKey(Producto, models.DO_NOTHING)
    cantidad = models.IntegerField()
    precio_unitario_clp = models.IntegerField()

    class Meta:
        managed = False
        db_table = "orden_item"
