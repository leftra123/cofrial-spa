"""Última lectura «vigente» de cada camión.

Normalmente es la última fila de telemetría. Con el modo demostración activo (lecturas forzadas recientes con alerta), el camión se
considera en ruptura de frío: la posición, el combustible y la hora siguen siendo los de la última lectura real, pero la temperatura y la
alerta son las de la lectura forzada. Así la flota, la API y el seguimiento no parpadean entre «alerta» y «normal» aunque el simulador
siga insertando lecturas normales cada pocos segundos. Nada de esto se guarda: es solo cómo se lee.

Un camión de dos cámaras envía una lectura por cámara. La flota lo ve en alerta si cualquiera lo está; a un pedido solo le importa la suya."""
from datetime import timedelta

from django.utils import timezone

from .models import Telemetria

VIGENCIA_FORZADA_S = 20      # una lectura forzada cuenta mientras tenga menos segundos que esto y no haya una forzada más nueva que la apague
_ULTIMA_POR_CAMARA = """SELECT t.* FROM camion c
  CROSS JOIN generate_series(1, CASE WHEN c.rango_secundario_id IS NULL THEN 1 ELSE 2 END) AS n(camara)
  CROSS JOIN LATERAL (SELECT * FROM telemetria m WHERE m.camion_id = c.camion_id AND m.camara = n.camara ORDER BY m.registrado_en DESC LIMIT 1) t
  ORDER BY c.camion_id, n.camara"""


def _aplicar(real, forzada):
    if real is None or real.forzada:                       # sin lectura real, o la última ya es la forzada
        return real if real is not None else forzada
    real.temp_camara = forzada.temp_camara                 # solo en memoria
    real.alerta_ruptura_frio = True
    return real


def _por_camara():
    """{(camion_id, camara): Telemetria} con la última lectura vigente de cada cámara, en dos consultas que no recorren la tabla: una por cámara con
    uq_telemetria_camion_camara_instante (un DISTINCT ON leería el millón de filas) y las forzadas solo dentro de su ventana de vigencia con idx_telemetria_fecha."""
    reales = {(t.camion_id, t.camara): t for t in Telemetria.objects.raw(_ULTIMA_POR_CAMARA)}
    desde = timezone.now() - timedelta(seconds=VIGENCIA_FORZADA_S)
    for f in Telemetria.objects.filter(forzada=True, registrado_en__gte=desde).order_by("camion_id", "camara", "-registrado_en").distinct("camion_id", "camara"):
        if f.alerta_ruptura_frio:      # la más nueva de las forzadas debe ser de alerta (si es de «apagar», no cuenta)
            reales[(f.camion_id, f.camara)] = _aplicar(reales.get((f.camion_id, f.camara)), f)
    return reales


def ultimas_vigentes():
    """{camion_id: Telemetria}: la cámara en alerta si hay una; si no, la cámara 1. La lectura trae en `camaras` todas las de ese camión."""
    camaras, resultado = {}, {}
    for (camion_id, camara), t in sorted(_por_camara().items()):
        camaras.setdefault(camion_id, []).append(t)
    for camion_id, lecturas in camaras.items():
        elegida = next((t for t in lecturas if t.alerta_ruptura_frio), lecturas[0])
        elegida.camaras = lecturas
        resultado[camion_id] = elegida
    return resultado


def ultima_vigente(camion, camara=None):
    """La última lectura vigente del camión o, si se indica, de esa cámara."""
    pk = camion.pk if hasattr(camion, "pk") else camion
    if camara is None:
        return ultimas_vigentes().get(pk)
    return _por_camara().get((pk, camara))
