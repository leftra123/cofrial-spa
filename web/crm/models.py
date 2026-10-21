from django.db import models
from django.db.models import Q

from clientes.models import Cliente, Vendedor
from pedidos.models import Orden


class EtapaPipeline(models.Model):
    etapa_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30, unique=True)
    orden_etapa = models.SmallIntegerField(unique=True)
    es_final = models.BooleanField(default=False)
    es_ganada = models.BooleanField(default=False)

    class Meta:
        db_table = "etapa_pipeline"
        verbose_name = "etapa del pipeline"
        verbose_name_plural = "etapas del pipeline"
        ordering = ["orden_etapa"]
        constraints = [models.CheckConstraint(condition=Q(es_ganada=False) | Q(es_final=True), name="ganada_es_final")]

    def __str__(self):
        return self.nombre


class Prospecto(models.Model):
    ORIGENES = [(o, o) for o in ("web", "referido", "llamada", "feria", "otro")]
    prospecto_id = models.AutoField(primary_key=True)
    vendedor = models.ForeignKey(Vendedor, on_delete=models.PROTECT)
    etapa = models.ForeignKey(EtapaPipeline, on_delete=models.PROTECT)
    cliente = models.ForeignKey(Cliente, null=True, blank=True, on_delete=models.SET_NULL)
    nombre_contacto = models.CharField(max_length=120)
    empresa = models.CharField(max_length=120, blank=True)
    email = models.EmailField(max_length=120, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    origen = models.CharField(max_length=20, choices=ORIGENES)
    monto_estimado_clp = models.IntegerField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    motivo_perdida = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "prospecto"
        indexes = [models.Index(fields=["vendedor", "etapa"], name="idx_prospecto_vendedor_etapa")]
        constraints = [
            models.CheckConstraint(condition=Q(monto_estimado_clp__isnull=True) | Q(monto_estimado_clp__gte=0), name="monto_no_negativo"),
            models.CheckConstraint(condition=~Q(email="") | ~Q(telefono=""), name="prospecto_con_contacto"),
            models.CheckConstraint(condition=Q(cerrado_en__isnull=False) | Q(motivo_perdida=""), name="motivo_requiere_cierre"),
        ]

    def __str__(self):
        return f"{self.nombre_contacto} ({self.etapa})"


class Interaccion(models.Model):
    TIPOS = [(t, t) for t in ("llamada", "correo", "reunion", "nota")]
    interaccion_id = models.AutoField(primary_key=True)
    vendedor = models.ForeignKey(Vendedor, on_delete=models.PROTECT)
    prospecto = models.ForeignKey(Prospecto, null=True, blank=True, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, null=True, blank=True, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    detalle = models.TextField()
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "interaccion"
        verbose_name = "interacción"
        verbose_name_plural = "interacciones"
        constraints = [models.CheckConstraint(condition=Q(prospecto__isnull=False) | Q(cliente__isnull=False), name="interaccion_tiene_destino")]


class CategoriaRequerimiento(models.Model):
    categoria_requerimiento_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=40, unique=True)

    class Meta:
        db_table = "categoria_requerimiento"
        verbose_name = "categoría de requerimiento"
        verbose_name_plural = "categorías de requerimiento"

    def __str__(self):
        return self.nombre


class Requerimiento(models.Model):
    ESTADOS = [("sin_clasificar", "sin clasificar"), ("clasificado", "clasificado"), ("resuelto", "resuelto")]
    requerimiento_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, null=True, blank=True, on_delete=models.SET_NULL)
    orden = models.ForeignKey(Orden, null=True, blank=True, on_delete=models.SET_NULL)
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField()
    categoria_requerimiento = models.ForeignKey(CategoriaRequerimiento, null=True, blank=True, on_delete=models.SET_NULL)
    confianza_ia = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=14, choices=ESTADOS, default="sin_clasificar")
    creado_en = models.DateTimeField(auto_now_add=True)
    respondido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "requerimiento"
        constraints = [models.CheckConstraint(condition=Q(confianza_ia__isnull=True) | Q(confianza_ia__gte=0, confianza_ia__lte=1), name="confianza_entre_0_y_1")]
