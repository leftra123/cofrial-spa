"""`ultimas_vigentes` sirve a /flota/, la API y el seguimiento: la consulta por camión debe dar exactamente lo mismo que el DISTINCT ON anterior."""
from datetime import timedelta

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from flota import vigente
from flota.models import Camion, Telemetria


def referencia():
    """La implementación anterior, sin índices ni ventana: define la salida esperada."""
    reales = {t.camion_id: t for t in Telemetria.objects.order_by("camion_id", "-registrado_en").distinct("camion_id")}
    desde = timezone.now() - timedelta(seconds=vigente.VIGENCIA_FORZADA_S)
    for f in Telemetria.objects.filter(forzada=True).order_by("camion_id", "-registrado_en").distinct("camion_id"):
        if f.alerta_ruptura_frio and f.registrado_en >= desde:
            reales[f.camion_id] = vigente._aplicar(reales.get(f.camion_id), f)
    return reales


def resumen(lecturas):
    return [(cid, t.pk, t.temp_camara, t.lat, t.long, t.combustible_pct, t.alerta_ruptura_frio, t.forzada, t.registrado_en) for cid, t in lecturas.items()]


class UltimasVigentes(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.camiones = list(Camion.objects.order_by("camion_id").values_list("camion_id", flat=True))[:8]

    def setUp(self):
        Telemetria.objects.all().delete()

    def lectura(self, camion, hace_s, temp=3.0, alerta=False, forzada=False):
        t = Telemetria.objects.create(camion_id=camion, temp_camara=temp, lat=-38.7, long=-72.6, combustible_pct=60, alerta_ruptura_frio=alerta, forzada=forzada)
        Telemetria.objects.filter(pk=t.pk).update(registrado_en=timezone.now() - timedelta(seconds=hace_s))

    def escenario(self):
        solo_real, forzada_viva, apagada, forzada_vieja, solo_forzada, solo_forzada_vieja, real_mas_nueva, _sin_lecturas = self.camiones
        self.lectura(solo_real, 30)
        self.lectura(solo_real, 5, temp=4.0)
        self.lectura(forzada_viva, 2, temp=4.5)                                  # real más nueva que la forzada viva: conserva posición, toma temperatura y alerta
        self.lectura(forzada_viva, 5, temp=11.0, alerta=True, forzada=True)
        self.lectura(apagada, 2)
        self.lectura(apagada, 6, temp=3.5, forzada=True)                         # la forzada más nueva apaga la alerta
        self.lectura(apagada, 8, temp=12.0, alerta=True, forzada=True)
        self.lectura(forzada_vieja, 3)
        self.lectura(forzada_vieja, 60, temp=12.0, alerta=True, forzada=True)    # fuera de la vigencia
        self.lectura(solo_forzada, 4, temp=10.0, alerta=True, forzada=True)
        self.lectura(solo_forzada_vieja, 90, temp=10.0, alerta=True, forzada=True)
        self.lectura(real_mas_nueva, 40, temp=9.0, alerta=True)                  # alerta real antigua, lectura normal posterior
        self.lectura(real_mas_nueva, 1)

    def test_misma_salida_que_antes(self):
        self.escenario()
        nueva, esperada = vigente.ultimas_vigentes(), referencia()
        self.assertEqual(resumen(nueva), resumen(esperada))
        self.assertTrue(nueva[self.camiones[1]].alerta_ruptura_frio)
        self.assertEqual(nueva[self.camiones[1]].temp_camara, 11.0)
        self.assertFalse(nueva[self.camiones[2]].alerta_ruptura_frio)
        self.assertNotIn(self.camiones[7], nueva)

    def test_base_vacia(self):
        self.assertEqual(vigente.ultimas_vigentes(), {})

    def test_una_consulta_por_camion_no_una_por_fila(self):
        self.escenario()
        with CaptureQueriesContext(connection) as q:
            vigente.ultimas_vigentes()
        self.assertLessEqual(len(q), 2)
        self.assertIn("LATERAL", q[0]["sql"])
        self.assertIn('"telemetria"."registrado_en" >=', q[1]["sql"])       # las forzadas se buscan solo en la ventana de vigencia

    def test_indice_por_fecha_para_el_sondeo(self):
        with connection.cursor() as cursor:
            indices = connection.introspection.get_constraints(cursor, "telemetria")
        self.assertEqual(indices["idx_telemetria_fecha"]["columns"], ["registrado_en"])
