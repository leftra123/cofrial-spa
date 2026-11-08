"""Un pedido entregado cuyo viaje no tiene lecturas de temperatura no deja un bloque gris de «cargando» para siempre
(revisión de usuarios del 8-nov-2026: pedidos 12 y 13 del Hospital Regional)."""
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase

from flota.models import Telemetria
from pedidos.models import Orden

CLAVE = "demo-cofrial-2026"


class TemperaturaSinLecturasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        cache.clear()

    def test_la_temperatura_sin_lecturas_no_queda_como_bloque_gris(self):
        orden = Orden.objects.filter(estado_orden__nombre="Entregada", despacho__isnull=False, direccion__cliente__usuario__username="abastecimiento@hospital.test").first()
        self.assertIsNotNone(orden, "los datos de demostración traen pedidos entregados del Hospital Regional")
        self.assertFalse(Telemetria.objects.filter(camion=orden.despacho.camion).exists())
        c = Client()
        self.assertTrue(c.login(username="abastecimiento@hospital.test", password=CLAVE))
        html = c.get(f"/pedidos/{orden.orden_id}/").content.decode()
        self.assertIn("Sin lecturas", html)
        self.assertNotIn('id="seg-temp" class="skeleton"', html)       # el JS solo quita el gris cuando llega una lectura, y aquí no llega
        self.assertNotIn(">00,0<", html)                                # y tampoco se inventa una temperatura de cero grados
        self.assertIn('<b id="seg-temp">–</b>', html)
