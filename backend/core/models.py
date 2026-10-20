"""Modelos sin migración (managed=False) sobre el esquema de informe/modelo/esquema.sql."""
from django.db import models


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
