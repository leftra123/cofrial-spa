from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

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
    dias_credito = models.PositiveSmallIntegerField(default=0, db_default=0)       # plazo de pago de la factura; 0 = paga al comprar

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


class SegmentoCliente(models.Model):
    """Tipo de comprador (hospital, supermercado, feria, institucional); alimenta la Torre de control."""
    segmento_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=40, unique=True)

    class Meta:
        db_table = "segmento_cliente"

    def __str__(self):
        return self.nombre


class Cliente(models.Model):
    cliente_id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    tipo_cliente = models.ForeignKey(TipoCliente, on_delete=models.PROTECT)
    vendedor = models.ForeignKey(Vendedor, null=True, blank=True, on_delete=models.SET_NULL)
    segmento = models.ForeignKey(SegmentoCliente, null=True, blank=True, on_delete=models.SET_NULL)
    rut = models.CharField(max_length=12, unique=True)
    nombre = models.CharField(max_length=120)
    email = models.EmailField(max_length=120)
    telefono = models.CharField(max_length=20, blank=True)
    giro = models.CharField(max_length=80, blank=True)           # actividad económica que exige la factura (B2B)
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
    lat = models.FloatField(null=True, blank=True)       # ubicación para trazar la ruta; se obtiene de OpenStreetMap
    long = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "direccion"
        verbose_name_plural = "direcciones"
        constraints = [models.UniqueConstraint(fields=["cliente"], condition=models.Q(es_principal=True), name="uq_direccion_principal")]

    def __str__(self):
        return f"{self.calle_numero}, {self.comuna}"


class AceptacionLegal(models.Model):
    """Prueba de que una cuenta aceptó los términos y condiciones y la política de privacidad: quién, cuándo, qué versión y desde qué IP.
    Eliminar la cuenta desde «Mis datos» no borra el usuario (lo desactiva), así que la constancia queda. Solo desaparece con el
    usuario cuando este se borra de verdad, como al rechazar una solicitud de empresa que nunca operó. Versiones: cofrial/legal.py."""
    aceptacion_id = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    version = models.CharField(max_length=20)
    aceptado_en = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "aceptacion_legal"
        verbose_name = "aceptación de términos"
        verbose_name_plural = "aceptaciones de términos"

    def __str__(self):
        return f"{self.usuario} aceptó la versión {self.version} el {self.aceptado_en:%d/%m/%Y %H:%M}"


def _sumar_dias_habiles(fecha, n):
    """Lunes a viernes; no descuenta feriados (el prototipo no tiene un calendario de feriados)."""
    while n > 0:
        fecha += timedelta(days=1)
        if fecha.weekday() < 5:
            n -= 1
    return fecha


class SolicitudDerecho(models.Model):
    """Una solicitud del titular para ejercer sus derechos sobre sus datos personales (Ley 21.719): rectificación, oposición,
    bloqueo y los demás que no se resuelven solos en «Mis datos». Deja constancia de qué pidió, cuándo, el plazo legal y la respuesta.
    El plazo no se guarda: se calcula de la fecha de recepción, el tipo y la prórroga (así no queda un dato derivado en la tabla, 3FN)."""
    TIPOS = [("acceso", "Acceso"), ("rectificacion", "Rectificación"), ("supresion", "Supresión"), ("oposicion", "Oposición"),
             ("portabilidad", "Portabilidad"), ("bloqueo", "Bloqueo temporal")]
    ESTADOS = [("recibida", "Recibida"), ("respondida", "Respondida")]
    DIAS_CORRIDOS = 30          # plazo general de respuesta, prorrogable una vez por otros 30
    DIAS_HABILES_BLOQUEO = 2    # el bloqueo temporal se resuelve antes

    solicitud_id = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes_derecho")
    tipo = models.CharField(max_length=15, choices=TIPOS)
    detalle = models.TextField(max_length=2000)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="recibida")
    prorrogada = models.BooleanField(default=False)
    creada_en = models.DateTimeField(auto_now_add=True)
    respuesta = models.TextField(max_length=2000, blank=True)
    respondida_en = models.DateTimeField(null=True, blank=True)
    atendida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        db_table = "solicitud_derecho"
        ordering = ["-creada_en"]
        verbose_name = "solicitud de derechos sobre datos"
        verbose_name_plural = "solicitudes de derechos sobre datos"

    def __str__(self):
        return f"Solicitud N.º {self.solicitud_id} ({self.get_tipo_display()})"

    @property
    def vence_el(self):
        recibida = timezone.localtime(self.creada_en).date()
        if self.tipo == "bloqueo":
            return _sumar_dias_habiles(recibida, self.DIAS_HABILES_BLOQUEO)
        return recibida + timedelta(days=self.DIAS_CORRIDOS * (2 if self.prorrogada else 1))

    @property
    def vencida(self):
        return self.estado == "recibida" and timezone.localdate() > self.vence_el

    @property
    def puede_prorrogarse(self):
        return self.estado == "recibida" and not self.prorrogada and self.tipo != "bloqueo"
