from django.conf import settings
from django.db import models
from django.db.models import F, Q

from catalogo.models import RangoTemperatura


class Camion(models.Model):
    """La clave es el código que usa la telemetría (texto, según la pauta)."""
    camion_id = models.CharField(max_length=20, primary_key=True)
    patente = models.CharField(max_length=8, unique=True)
    capacidad_kg = models.IntegerField()
    rango_temperatura = models.ForeignKey(RangoTemperatura, on_delete=models.PROTECT)           # cámara 1, la única en la mayoría de la flota
    rango_secundario = models.ForeignKey(RangoTemperatura, null=True, blank=True, on_delete=models.PROTECT, related_name="+")   # cámara 2: lleva dos rangos en un viaje
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "camion"
        verbose_name_plural = "camiones"
        constraints = [models.CheckConstraint(condition=Q(capacidad_kg__gt=0), name="capacidad_positiva"),
                       models.CheckConstraint(condition=~Q(rango_secundario=F("rango_temperatura")), name="camaras_de_rango_distinto")]

    def __str__(self):
        return self.camion_id

    @property
    def dos_camaras(self):
        return self.rango_secundario_id is not None

    @property
    def rangos(self):
        """Nombres de los rangos que puede llevar este camión."""
        return [self.rango_temperatura.nombre] + ([self.rango_secundario.nombre] if self.dos_camaras else [])

    @property
    def rangos_texto(self):
        return " y ".join(self.rangos)

    def camara_de(self, rango):
        """Número de la cámara que lleva ese rango: 2 si es el secundario; en cualquier otro caso, 1."""
        return 2 if self.dos_camaras and rango == self.rango_secundario.nombre else 1

    def rango_de_camara(self, camara):
        return self.rango_secundario if camara == 2 and self.dos_camaras else self.rango_temperatura


class Despacho(models.Model):
    despacho_id = models.AutoField(primary_key=True)
    camion = models.ForeignKey(Camion, on_delete=models.PROTECT)
    programado_para = models.DateTimeField()
    salida_en = models.DateTimeField(null=True, blank=True)
    llegada_en = models.DateTimeField(null=True, blank=True)      # el camión llegó a la última entrega (la registra el simulador)
    regreso_en = models.DateTimeField(null=True, blank=True)      # el camión volvió a la base: recién entonces queda libre
    FASES = [("en_ruta", "en ruta"), ("en_la_puerta", "en la puerta del cliente"), ("volviendo", "volviendo a la base")]
    fase = models.CharField(max_length=12, choices=FASES, default="en_ruta", db_default="en_ruta")     # la actualiza el simulador mientras dura el viaje
    ruta_geojson = models.JSONField(null=True, blank=True)        # recorrido por calles base -> paradas -> base: {"puntos": [[lat, long]...], "paradas": [{"direccion_id", "indice"}]}
    ruta_aproximada = models.BooleanField(default=False, db_default=False)     # true si OSRM no respondió y la ruta son rectas entre los puntos
    decision_auto = models.TextField(null=True, blank=True)       # por qué salió este viaje, escrito por el código; vacío si lo armó una persona
    decision_ia = models.TextField(null=True, blank=True)         # la misma decisión redactada por la IA; vacío si no hubo IA utilizable

    class Meta:
        db_table = "despacho"
        constraints = [
            models.CheckConstraint(condition=Q(regreso_en__isnull=True) | Q(llegada_en__isnull=False), name="regreso_requiere_llegada"),
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
    camara = models.PositiveSmallIntegerField(default=1, db_default=1)    # 1 en todo camión; 2 solo en los de dos cámaras, que envían una lectura por cada una
    registrado_en = models.DateTimeField(auto_now_add=True)
    forzada = models.BooleanField(default=False, db_default=False)    # lectura de demostración: la crea /demo/ o la envía el simulador durante una falla de un escenario; se puede borrar sin tocar la telemetría normal

    class Meta:
        db_table = "telemetria"
        verbose_name_plural = "telemetría"
        constraints = [
            models.UniqueConstraint(fields=["camion", "camara", "registrado_en"], name="uq_telemetria_camion_camara_instante"),
            models.CheckConstraint(condition=Q(camara__in=[1, 2]), name="telemetria_camara_valida"),
            models.CheckConstraint(condition=Q(lat__gte=-90, lat__lte=90), name="lat_valida"),
            models.CheckConstraint(condition=Q(long__gte=-180, long__lte=180), name="long_valida"),
            models.CheckConstraint(condition=Q(combustible_pct__gte=0, combustible_pct__lte=100), name="combustible_valido"),
        ]
        indexes = [
            models.Index(fields=["camion", "-registrado_en"], name="idx_telemetria_camion_fecha"),
            models.Index(fields=["registrado_en"], condition=Q(alerta_ruptura_frio=True), name="idx_telemetria_alerta"),
            models.Index(fields=["-registrado_en"], name="idx_telemetria_fecha"),      # el sondeo de la Torre: última lectura, camiones reportando, forzadas recientes
        ]


class RutaCache(models.Model):
    """Recorridos ya calculados con OSRM: la misma secuencia de puntos devuelve siempre la misma ruta y no se vuelve a pedir al servicio."""
    clave = models.CharField(max_length=64, primary_key=True)        # SHA-256 de la secuencia de coordenadas redondeadas
    ruta_geojson = models.JSONField()
    km = models.FloatField()
    aproximada = models.BooleanField(default=False)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ruta_cache"


class EscenarioSimulador(models.Model):
    """Comportamiento pedido para un viaje en curso. Lo escribe la web (botón o propuesta de la IA ya validada) y lo leen los contenedores
    del simulador en cada ciclo. El camión no se guarda: se obtiene del despacho. Las restricciones repiten en la base los límites de
    `flota/escenarios.py`, así ni un error del código deja pasar un parámetro fuera de rango."""
    TIPOS = [("falla_frio", "falla de frío"), ("entrega_perfecta", "entrega perfecta"), ("cliente_no_recibe", "cliente no recibe"),
             ("sensor_falla", "falsa alarma por sensor"), ("sensor_pegado", "sensor pegado en normal")]
    CON_MOMENTO = ("falla_frio", "sensor_falla", "sensor_pegado")       # los que empiezan a cierto avance de la ruta y duran cierto número de lecturas
    ESTADOS = [("pendiente", "pendiente"), ("en_curso", "en curso"), ("terminado", "terminado"), ("cancelado", "cancelado")]
    ORIGENES = [("boton", "botón predefinido"), ("ia", "propuesta de la IA")]
    VIGENTES = ("pendiente", "en_curso")

    escenario_id = models.AutoField(primary_key=True)
    despacho = models.ForeignKey(Despacho, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="pendiente", db_default="pendiente")
    momento_pct = models.SmallIntegerField(null=True, blank=True)        # falla de frío: avance del camión hacia la última parada al que parte
    duracion_lecturas = models.SmallIntegerField(null=True, blank=True)  # falla de frío: lecturas que dura
    subida_c = models.FloatField(null=True, blank=True)                  # falla de frío: grados que sube por lectura
    direccion = models.ForeignKey("clientes.Direccion", null=True, blank=True, on_delete=models.CASCADE)    # cliente no recibe: la parada afectada
    motivo_no_recibe = models.CharField(max_length=120, blank=True)      # cliente no recibe: texto de la lista cerrada, nunca de la IA
    origen = models.CharField(max_length=5, choices=ORIGENES)
    pedido_texto = models.CharField(max_length=300, blank=True)          # lo que escribió el administrador, ya anonimizado (solo registro: nadie lo ejecuta)
    modelo_ia = models.CharField(max_length=80, blank=True)              # qué modelo propuso el escenario
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    creado_en = models.DateTimeField(auto_now_add=True)
    iniciado_en = models.DateTimeField(null=True, blank=True)            # lo registra el simulador cuando el escenario empieza a actuar
    terminado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "escenario_simulador"
        verbose_name_plural = "escenarios del simulador"
        constraints = [
            models.UniqueConstraint(fields=["despacho"], condition=Q(estado__in=("pendiente", "en_curso")), name="uq_escenario_vigente_por_despacho"),
            models.CheckConstraint(condition=Q(tipo__in=("falla_frio", "entrega_perfecta", "cliente_no_recibe", "sensor_falla", "sensor_pegado")), name="escenario_tipo_conocido"),
            models.CheckConstraint(condition=Q(estado__in=("pendiente", "en_curso", "terminado", "cancelado")), name="escenario_estado_conocido"),
            models.CheckConstraint(condition=~Q(tipo="falla_frio") | Q(momento_pct__gte=5, momento_pct__lte=95, duracion_lecturas__gte=6, duracion_lecturas__lte=36,
                                                                       subida_c__gte=1.0, subida_c__lte=2.0), name="escenario_falla_acotada"),
            models.CheckConstraint(condition=~Q(tipo__in=("sensor_falla", "sensor_pegado")) | Q(momento_pct__gte=5, momento_pct__lte=95, duracion_lecturas__gte=6, duracion_lecturas__lte=36),
                                   name="escenario_sensor_acotado"),
            models.CheckConstraint(condition=~Q(tipo="cliente_no_recibe") | (Q(direccion__isnull=False) & ~Q(motivo_no_recibe="")), name="escenario_no_recibe_completo"),
        ]

    def __str__(self):
        return f"Escenario {self.escenario_id} ({self.tipo}, despacho {self.despacho_id})"


class AjusteSimulador(models.Model):
    """Ajustes de la demostración que el simulador lee en cada ciclo. Es una sola fila (ajuste_id = 1): si no existe, el tiempo corre a 1×.
    La restricción repite los valores de `flota/tiempo.py`, así ni un error del código deja un multiplicador fuera de la lista."""
    UNICO = 1

    ajuste_id = models.SmallIntegerField(primary_key=True, default=UNICO)
    multiplicador_tiempo = models.SmallIntegerField(default=1, db_default=1)    # cuántas veces más rápido avanzan los camiones; no cambia la frecuencia de la telemetría
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ajuste_simulador"
        verbose_name_plural = "ajustes del simulador"
        constraints = [
            models.CheckConstraint(condition=Q(ajuste_id=1), name="ajuste_fila_unica"),
            models.CheckConstraint(condition=Q(multiplicador_tiempo__in=(1, 5, 20, 60)), name="ajuste_multiplicador_conocido"),
        ]

    def __str__(self):
        return f"Tiempo a {self.multiplicador_tiempo}×"


class RevisionCamion(models.Model):
    """Un camión enviado a revisión técnica: mientras haya una abierta no se sugiere ni se despacha. La abre una persona (administrador o
    despachador) desde la alerta de frío de la flota, con el diagnóstico a la vista; se cierra con «Volver a servicio». Un camión no puede
    tener dos revisiones abiertas a la vez. La situación del camión (en ruta, en base...) no cambia: sigue su viaje hasta volver a la base."""
    MOTIVOS = [("equipo_frio", "equipo de frío"), ("sensor", "sensor de temperatura"), ("otro", "otro motivo")]

    revision_id = models.AutoField(primary_key=True)
    camion = models.ForeignKey(Camion, on_delete=models.PROTECT)
    motivo = models.CharField(max_length=12, choices=MOTIVOS)
    nota = models.CharField(max_length=300, blank=True, default="", db_default="")      # lo que sugirió el diagnóstico o escribió la persona
    abierta_en = models.DateTimeField(auto_now_add=True)
    abierta_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cerrada_en = models.DateTimeField(null=True, blank=True)
    cerrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        db_table = "revision_camion"
        verbose_name_plural = "revisiones de camión"
        constraints = [
            models.UniqueConstraint(fields=["camion"], condition=Q(cerrada_en__isnull=True), name="uq_revision_abierta_por_camion"),
            models.CheckConstraint(condition=Q(motivo__in=("equipo_frio", "sensor", "otro")), name="revision_motivo_conocido"),
            models.CheckConstraint(condition=Q(cerrada_en__isnull=True) | Q(cerrada_en__gte=models.F("abierta_en")), name="revision_cierre_despues_de_apertura"),
        ]

    def __str__(self):
        return f"Revisión {self.revision_id} ({self.camion_id}, {self.motivo})"
