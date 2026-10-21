from django.conf import settings
from django.db import models

from catalogo.models import ListaPrecio


class Region(models.Model):
    region_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        db_table = "region"

    def __str__(self):
        return self.nombre


class Comuna(models.Model):
    comuna_id = models.AutoField(primary_key=True)
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=60)

    class Meta:
        db_table = "comuna"
        constraints = [models.UniqueConstraint(fields=["region", "nombre"], name="uq_comuna_region")]

    def __str__(self):
        return self.nombre


class TipoCliente(models.Model):
    CODIGOS = [("B2B", "B2B"), ("B2C", "B2C")]
    tipo_cliente_id = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=3, unique=True, choices=CODIGOS)
    nombre = models.CharField(max_length=40)
    lista_precio = models.ForeignKey(ListaPrecio, on_delete=models.PROTECT)

    class Meta:
        db_table = "tipo_cliente"

    def __str__(self):
        return self.codigo


class Vendedor(models.Model):
    """La cuenta de acceso es el usuario de Django (reemplaza la tabla usuario del diseño, decisión D-03)."""
    vendedor_id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=120)
    telefono = models.CharField(max_length=20, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "vendedor"
        verbose_name_plural = "vendedores"

    def __str__(self):
        return self.nombre


class Cliente(models.Model):
    cliente_id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    tipo_cliente = models.ForeignKey(TipoCliente, on_delete=models.PROTECT)
    vendedor = models.ForeignKey(Vendedor, null=True, blank=True, on_delete=models.SET_NULL)
    rut = models.CharField(max_length=12, unique=True)
    nombre = models.CharField(max_length=120)
    email = models.EmailField(max_length=120)
    telefono = models.CharField(max_length=20, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cliente"

    def __str__(self):
        return f"{self.nombre} ({self.tipo_cliente.codigo})"


class Direccion(models.Model):
    direccion_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    calle_numero = models.CharField(max_length=150)
    comuna = models.ForeignKey(Comuna, on_delete=models.PROTECT)
    referencia = models.CharField(max_length=150, blank=True)
    es_principal = models.BooleanField(default=False)

    class Meta:
        db_table = "direccion"
        verbose_name_plural = "direcciones"
        constraints = [models.UniqueConstraint(fields=["cliente"], condition=models.Q(es_principal=True), name="uq_direccion_principal")]

    def __str__(self):
        return f"{self.calle_numero}, {self.comuna}"
