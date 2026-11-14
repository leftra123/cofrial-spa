"""Limpiar alertas antiguas: solo el administrador, con confirmación, sin tocar demostración, lecturas normales ni lecturas recientes."""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from flota.models import Camion, Telemetria

CLAVE = "demo-cofrial-2026"


class BorrarAlertas(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.camion = Camion.objects.first()

    def lectura(self, minutos, alerta=True, forzada=False, camara=1):
        t = Telemetria.objects.create(camion=self.camion, camara=camara, temp_camara=-5 if alerta else -20, lat=-38.7, long=-72.6,
                                      combustible_pct=80, alerta_ruptura_frio=alerta, forzada=forzada)
        Telemetria.objects.filter(pk=t.pk).update(registrado_en=timezone.now() - timedelta(minutes=minutos, seconds=camara))
        return t.pk

    def entrar(self, usuario="admin@cofrial.cl"):
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def test_borra_solo_las_alertas_antiguas_reales(self):
        vieja = self.lectura(60)
        reciente = self.lectura(2)
        demo = self.lectura(60, forzada=True)
        normal = self.lectura(60, alerta=False)
        self.entrar()
        self.assertContains(self.client.get("/crm/alertas/"), "Limpiar alertas antiguas")
        r = self.client.post("/crm/alertas/borrar/", {"confirmar": "1"}, follow=True)
        self.assertContains(r, "Se borraron")
        self.assertFalse(Telemetria.objects.filter(pk=vieja).exists())
        for pk in (reciente, demo, normal):
            self.assertTrue(Telemetria.objects.filter(pk=pk).exists())

    def test_sin_confirmar_no_borra(self):
        vieja = self.lectura(60)
        self.entrar()
        r = self.client.post("/crm/alertas/borrar/", {}, follow=True)
        self.assertContains(r, "casilla de confirmación")
        self.assertTrue(Telemetria.objects.filter(pk=vieja).exists())

    def test_otros_roles_no_pueden(self):
        vieja = self.lectura(60)
        for usuario in ("vendedora@cofrial.cl", "gerencia@cofrial.cl"):
            self.entrar(usuario)
            self.assertEqual(self.client.post("/crm/alertas/borrar/", {"confirmar": "1"}).status_code, 403, usuario)
            self.assertNotContains(self.client.get("/crm/alertas/"), "Limpiar alertas antiguas", msg_prefix=usuario)
        self.assertTrue(Telemetria.objects.filter(pk=vieja).exists())
