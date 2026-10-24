from django.db import models
from django.db.models import Q

from catalogo.models import RangoTemperatura


class Camion(models.Model):
    """La clave es el código que usa la telemetría (texto, según la pauta)."""
    camion_id = models.CharField(max_length=20, primary_key=True)
    patente = models.CharField(max_length=8, unique=True)
    capacidad_kg = models.IntegerField()
    rango_temperatura = models.ForeignKey(RangoTemperatura, on_delete=models.PROTECT)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "camion"
        verbose_name_plural = "camiones"
        constraints = [models.CheckConstraint(condition=Q(capacidad_kg__gt=0), name="capacidad_positiva")]

    def __str__(self):
        return self.camion_id


class Despacho(models.Model):
    despacho_id = models.AutoField(primary_key=True)
    camion = models.ForeignKey(Camion, on_delete=models.PROTECT)
    programado_para = models.DateTimeField()
    salida_en = models.DateTimeField(null=True, blank=True)
    llegada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "despacho"
        constraints = [
            models.CheckConstraint(condition=Q(llegada_en__isnull=True) | Q(salida_en__isnull=False), name="llegada_requiere_salida"),
            models.CheckConstraint(condition=Q(llegada_en__isnull=True) | Q(llegada_en__gte=models.F("salida_en")), name="llegada_despues_de_salida"),
        ]

    def __str__(self):
        return f"Despacho {self.despacho_id} ({self.camion_id})"


class Telemetria(models.Model):
    """Lecturas que insertan los contenedores del simulador. Los nombres de campo son los que exige la pauta."""
    telemetria_id = models.BigAutoField(primary_key=True)
    camion = models.ForeignKey(Camion, on_delete=models.PROTECT)          # columna camion_id (string)
    temp_camara = models.FloatField()
    lat = models.FloatField()
    long = models.FloatField()
    combustible_pct = models.IntegerField()
    alerta_ruptura_frio = models.BooleanField()
    registrado_en = models.DateTimeField(auto_now_add=True)
    forzada = models.BooleanField(default=False, db_default=False)    # lectura creada desde el modo demostración (el simulador no la envía)

    class Meta:
        db_table = "telemetria"
        verbose_name_plural = "telemetría"
        constraints = [
            models.UniqueConstraint(fields=["camion", "registrado_en"], name="uq_telemetria_camion_instante"),
            models.CheckConstraint(condition=Q(lat__gte=-90, lat__lte=90), name="lat_valida"),
            models.CheckConstraint(condition=Q(long__gte=-180, long__lte=180), name="long_valida"),
            models.CheckConstraint(condition=Q(combustible_pct__gte=0, combustible_pct__lte=100), name="combustible_valido"),
        ]
        indexes = [
            models.Index(fields=["camion", "-registrado_en"], name="idx_telemetria_camion_fecha"),
            models.Index(fields=["registrado_en"], condition=Q(alerta_ruptura_frio=True), name="idx_telemetria_alerta"),
        ]
