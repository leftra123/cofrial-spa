from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from catalogo.models import RangoTemperatura
from flota.models import Camion, Despacho, Telemetria


class PodarTelemetriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rango = RangoTemperatura.objects.create(nombre="Refrigerado", temp_min_c=Decimal("0"), temp_max_c=Decimal("4"))
        cls.camion = Camion.objects.create(camion_id="CAM-R1", patente="RRRR-11", capacidad_kg=5000, rango_temperatura=cls.rango)
        cls.ahora = timezone.now()

    def _lectura(self, dias, camion=None, **extra):
        datos = dict(camion=camion or self.camion, temp_camara=3.0, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=False)
        datos.update(extra)
        lectura = Telemetria.objects.create(**datos)
        Telemetria.objects.filter(pk=lectura.pk).update(registrado_en=self.ahora - timedelta(days=dias))   # auto_now_add ignora el valor al crear
        return lectura.pk

    def _queda(self, pk):
        return Telemetria.objects.filter(pk=pk).exists()

    def _podar(self, *args):
        salida = StringIO()
        call_command("podar_telemetria", *args, stdout=salida)
        return salida.getvalue()

    def test_borra_solo_las_lecturas_normales_antiguas(self):
        antigua, reciente = self._lectura(8), self._lectura(1)
        self._podar()
        self.assertFalse(self._queda(antigua))
        self.assertTrue(self._queda(reciente))

    def test_conserva_alertas_y_lecturas_forzadas(self):
        alerta, forzada = self._lectura(30, alerta_ruptura_frio=True), self._lectura(29, forzada=True)
        self._lectura(1)
        self._podar()
        self.assertTrue(self._queda(alerta))
        self.assertTrue(self._queda(forzada))

    def test_conserva_la_ultima_lectura_de_cada_camion(self):
        vieja, ultima = self._lectura(40), self._lectura(30)
        self._podar()
        self.assertFalse(self._queda(vieja))
        self.assertTrue(self._queda(ultima))

    def test_conserva_las_lecturas_de_un_viaje_terminado(self):
        Despacho.objects.create(camion=self.camion, programado_para=self.ahora - timedelta(days=21),
                                salida_en=self.ahora - timedelta(days=20), llegada_en=self.ahora - timedelta(days=19))
        antes, durante, despues = self._lectura(21), self._lectura(19.5), self._lectura(18)
        self._lectura(1)
        self._podar()
        self.assertFalse(self._queda(antes))
        self.assertTrue(self._queda(durante))
        self.assertFalse(self._queda(despues))

    def test_conserva_las_lecturas_de_un_viaje_en_curso(self):
        Despacho.objects.create(camion=self.camion, programado_para=self.ahora - timedelta(days=11), salida_en=self.ahora - timedelta(days=10))
        durante = self._lectura(9)
        self._lectura(1)
        self._podar()
        self.assertTrue(self._queda(durante))

    def test_un_viaje_de_otro_camion_no_protege_la_lectura(self):
        otro = Camion.objects.create(camion_id="CAM-R2", patente="RRRR-22", capacidad_kg=5000, rango_temperatura=self.rango)
        Despacho.objects.create(camion=otro, programado_para=self.ahora - timedelta(days=11), salida_en=self.ahora - timedelta(days=10))
        antigua = self._lectura(9)
        self._lectura(1)
        self._podar()
        self.assertFalse(self._queda(antigua))

    def test_simular_no_borra(self):
        antigua = self._lectura(8)
        self._lectura(1)
        self.assertIn("Se borrarían 1 lecturas", self._podar("--simular"))
        self.assertTrue(self._queda(antigua))

    def test_borra_en_varios_lotes(self):
        antiguas = [self._lectura(10 + n) for n in range(5)]
        self._lectura(1)
        with patch("flota.management.commands.podar_telemetria.time.sleep") as pausa:
            salida = self._podar("--lote", "2")
        self.assertIn("5 lecturas", salida)
        self.assertFalse(Telemetria.objects.filter(pk__in=antiguas).exists())
        self.assertEqual(pausa.call_count, 2)

    def test_los_dias_vienen_del_entorno(self):
        antigua = self._lectura(4)
        self._lectura(1)
        with patch.dict("os.environ", {"RETENCION_TELEMETRIA_DIAS": "3"}):
            self._podar()
        self.assertFalse(self._queda(antigua))

    def test_rechaza_dias_invalidos_sin_borrar(self):
        antigua = self._lectura(8)
        self._lectura(1)
        with self.assertRaises(CommandError):
            self._podar("--dias", "0")
        with patch.dict("os.environ", {"RETENCION_TELEMETRIA_DIAS": "siete"}), self.assertRaises(CommandError):
            self._podar()
        self.assertTrue(self._queda(antigua))
