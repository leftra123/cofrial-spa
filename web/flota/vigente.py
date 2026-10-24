"""Última lectura «vigente» de cada camión.

Normalmente es la última fila de telemetría. Con el modo demostración activo (lecturas forzadas recientes con alerta), el camión se
considera en ruptura de frío: la posición, el combustible y la hora siguen siendo los de la última lectura real, pero la temperatura y la
alerta son las de la lectura forzada. Así la flota, la API y el seguimiento no parpadean entre «alerta» y «normal» aunque el simulador
siga insertando lecturas normales cada pocos segundos. Nada de esto se guarda: es solo cómo se lee."""
from datetime import timedelta

from django.utils import timezone

from .models import Telemetria

VIGENCIA_FORZADA_S = 20      # una lectura forzada cuenta mientras tenga menos segundos que esto y no haya una forzada más nueva que la apague


def _aplicar(real, forzada):
    if real is None or real.forzada:                       # sin lectura real, o la última ya es la forzada
        return real if real is not None else forzada
    real.temp_camara = forzada.temp_camara                 # solo en memoria
    real.alerta_ruptura_frio = True
    return real


def ultimas_vigentes():
    """{camion_id: Telemetria} con la última lectura vigente de cada camión (una consulta más cuando hay forzadas)."""
    reales = {t.camion_id: t for t in Telemetria.objects.order_by("camion_id", "-registrado_en").distinct("camion_id")}
    desde = timezone.now() - timedelta(seconds=VIGENCIA_FORZADA_S)
    for f in Telemetria.objects.filter(forzada=True).order_by("camion_id", "-registrado_en").distinct("camion_id"):
        if f.alerta_ruptura_frio and f.registrado_en >= desde:      # la más nueva de las forzadas debe ser de alerta (si es de «apagar», no cuenta)
            reales[f.camion_id] = _aplicar(reales.get(f.camion_id), f)
    return reales


def ultima_vigente(camion):
    return ultimas_vigentes().get(camion.pk if hasattr(camion, "pk") else camion)
