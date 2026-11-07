"""Sistema: probar la IA y podar la telemetría desde la pantalla, sin comandos ni SSH."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone

from crm import ia
from flota.models import Camion, Telemetria
from operacion import servicios as s

from .tests_datos import Base


class Sistema(Base):
    def lectura(self, dias=30, **extra):
        datos = dict(camion=self.camion, temp_camara=3.0, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=False) | extra
        lectura = Telemetria.objects.create(**datos)
        Telemetria.objects.filter(pk=lectura.pk).update(registrado_en=timezone.now() - timedelta(days=dias))
        return lectura.pk

    def setUp(self):
        super().setUp()
        self.camion = Camion.objects.get(pk="CAM-01")
        Telemetria.objects.create(camion=self.camion, temp_camara=3.0, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=False)    # la última: siempre queda

    def test_permisos(self):
        for u in ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl", "ana@correo.test"):
            c = self.entrar(u)
            self.assertEqual(c.get("/operacion/sistema/").status_code, 403, u)
            self.assertEqual(c.post("/operacion/sistema/ia/").status_code, 403, u)
            self.assertEqual(c.post("/operacion/sistema/podar/").status_code, 403, u)

    def test_probar_ia_muestra_categoria_y_modelo(self):
        ia.ultimo_modelo = "Gemini de prueba"
        with patch("crm.ia.clasificar", return_value=("Reclamo por temperatura", 0.93)):
            r = self.admin.post("/operacion/sistema/ia/", follow=True)
        texto = self.mensajes(r)
        self.assertIn("Reclamo por temperatura", texto)
        self.assertIn("Gemini de prueba", texto)

    def test_ia_caida_muestra_la_causa(self):
        with patch("crm.ia.clasificar", side_effect=ia.ErrorIA("GEMINI_API_KEY no está definida")):
            r = self.admin.post("/operacion/sistema/ia/", follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("GEMINI_API_KEY no está definida", self.mensajes(r))

    def test_contar_no_borra(self):
        pk = self.lectura()
        self.assertContains(self.admin.get("/operacion/sistema/?contar=1"), "Se borrarían 1 lectura")
        self.assertTrue(Telemetria.objects.filter(pk=pk).exists())

    def test_la_pantalla_no_cuenta_sola(self):
        self.lectura()
        self.assertNotContains(self.admin.get("/operacion/sistema/"), "Se borrarían")

    def test_podar_por_get_no_se_permite(self):
        self.assertEqual(self.admin.get("/operacion/sistema/podar/").status_code, 405)

    def test_podar_respeta_alertas_y_forzadas(self):
        normal = self.lectura()
        alerta = self.lectura(alerta_ruptura_frio=True)
        forzada = self.lectura(forzada=True)
        reciente = self.lectura(dias=1)
        r = self.admin.post("/operacion/sistema/podar/", follow=True)
        self.assertIn("1 lectura", self.mensajes(r))
        self.assertFalse(Telemetria.objects.filter(pk=normal).exists())
        self.assertEqual(Telemetria.objects.filter(pk__in=[alerta, forzada, reciente]).count(), 3)

    def test_podar_con_tope_dice_cuanto_falta(self):
        for _ in range(3):
            self.lectura()
        self.assertEqual(s.podar(7, tope=2), (2, 1))
        self.assertEqual(s.podar(7, tope=2), (1, 0))

    def test_retencion_invalida_usa_siete_dias(self):
        with patch.dict("os.environ", {"RETENCION_TELEMETRIA_DIAS": "mucho"}):
            self.assertEqual(s.dias_de_retencion(), 7)
        with patch.dict("os.environ", {"RETENCION_TELEMETRIA_DIAS": "30"}):
            self.assertEqual(s.dias_de_retencion(), 30)

    def test_comando_sigue_funcionando(self):
        self.lectura()
        salida = StringIO()
        call_command("podar_telemetria", "--simular", stdout=salida)
        self.assertIn("Se borrarían 1 lecturas", salida.getvalue())
