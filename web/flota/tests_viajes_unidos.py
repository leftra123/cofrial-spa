"""Pedidos que quedan en el mismo camino van en un solo camión; el viaje queda listo para enviar con un clic."""
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Comuna, Direccion
from flota import servicios, sugerencias
from flota.models import Camion, Telemetria

CLAVE = "demo-cofrial-2026"


class ViajesUnidos(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        for c in Camion.objects.select_related("rango_temperatura"):
            r = c.rango_temperatura
            Telemetria.objects.create(camion=c, temp_camara=(float(r.temp_min_c) + float(r.temp_max_c)) / 2, lat=-38.73, long=-72.6, combustible_pct=80, alerta_ruptura_frio=False)

    def test_los_pedidos_en_el_mismo_camino_comparten_camion_y_las_coordenadas_no_salen(self):
        viajes, _ = sugerencias.calcular()
        pedidos_en_viajes = sum(len(v["pedidos"]) for v in viajes)
        por_despachar = len(servicios.pedidos_por_despachar())
        self.assertGreaterEqual(por_despachar, pedidos_en_viajes)
        self.assertEqual(len({v["camion"] for v in viajes}), len(viajes))                 # cada viaje, su camión
        for v in viajes:
            self.assertTrue(v["comunas"])
            self.assertTrue(all("pos" not in p for p in v["pedidos"]))                    # sin coordenadas hacia la pantalla ni la IA
            self.assertLessEqual(len(v["pedidos"]), sugerencias.MAX_PARADAS)

    def test_agrupa_lo_cercano_y_separa_lo_lejano(self):
        base = lambda lat, long: {"orden": 0, "comuna": "x", "direccion": 0, "espera_min": 1, "pos": (lat, long)}
        a = {**base(-38.9, -72.3), "orden": 1}          # hacia el sur-este
        b = {**base(-38.89, -72.31), "orden": 2}        # a metros de a
        c = {**base(-37.4, -72.35), "orden": 3}         # el lado opuesto: otro camino
        grupos = sugerencias._agrupar_por_camino([a, b, c])
        self.assertEqual(sorted(sorted(p["orden"] for p in g) for g in grupos), [[1, 2], [3]])

    def test_un_grupo_no_pasa_del_maximo_de_paradas(self):
        pedidos = [{"orden": i, "comuna": "x", "direccion": i, "espera_min": 1, "pos": (-38.9 + i * 0.0001, -72.3)} for i in range(1, 10)]
        tamanos = sorted(len(g) for g in sugerencias._agrupar_por_camino(pedidos))
        self.assertEqual(tamanos, [3, sugerencias.MAX_PARADAS])

    def test_el_panel_trae_el_boton_de_enviar_solo_para_quien_despacha(self):
        for u, debe in (("despacho@cofrial.cl", True), ("gerencia@cofrial.cl", False)):
            self.client.logout()
            self.assertTrue(self.client.login(username=u, password=CLAVE))
            html = self.client.get("/flota/").content.decode()
            self.assertIn("var puedeEnviar = " + ("true" if debe else "false"), html, u)
