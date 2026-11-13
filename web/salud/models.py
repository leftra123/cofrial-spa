from django.db import models


class ChequeoServicio(models.Model):
    """Una revisión real de un componente (la hace `manage.py vigilar`). La página /salud/ no inventa nada: solo lee estas filas.
    Si el laboratorio está apagado no hay filas, y esa ausencia se muestra como «sin registros», no como caída ni como éxito."""
    OK, DEGRADADO, CAIDO = "ok", "degradado", "caido"
    ESTADOS = [(OK, "Operativo"), (DEGRADADO, "Degradado"), (CAIDO, "Caído")]

    chequeo_id = models.BigAutoField(primary_key=True)
    servicio = models.CharField(max_length=20)                    # clave del catálogo (salud/catalogo.py)
    momento = models.DateTimeField()                              # cuándo se hizo la revisión (no cuándo se guardó: si la base estaba caída se guarda después)
    estado = models.CharField(max_length=10, choices=ESTADOS)
    ms = models.IntegerField(null=True, blank=True)               # lo que tardó la respuesta
    detalle = models.CharField(max_length=80, blank=True)         # frase corta fija («HTTP 503», «tiempo agotado»); nunca texto de la respuesta ni claves

    class Meta:
        db_table = "chequeo_servicio"
        indexes = [models.Index(fields=["servicio", "-momento"], name="idx_chequeo_servicio_momento"),
                   models.Index(fields=["-momento"], name="idx_chequeo_momento")]
