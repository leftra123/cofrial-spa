"""«¿Qué camión uso?»: sugerencia por solicitud, con reglas del código y la IA solo para redactar."""
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from crm import ia
from flota import servicios, sugerencias
from flota.models import Camion, RevisionCamion, Telemetria

CLAVE = "demo-cofrial-2026"


class Sugerir(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        cache.clear()
        for c in Camion.objects.select_related("rango_temperatura"):
            r = c.rango_temperatura
            Telemetria.objects.create(camion=c, temp_camara=(float(r.temp_min_c) + float(r.temp_max_c)) / 2, lat=-38.73, long=-72.6, combustible_pct=60, alerta_ruptura_frio=False)
        self.angol = next(o for o in servicios.pedidos_por_despachar() if o.direccion.comuna.nombre == "Angol")
        self.rango = servicios.rangos_de(self.angol)[0]

    def test_elige_un_camion_del_rango_libre_sano_y_explica(self):
        s = sugerencias.sugerir_para([self.angol.orden_id])
        self.assertEqual(s["destinos"], ["Angol"])
        self.assertIn(self.rango, Camion.objects.get(pk=s["camion"]["id"]).rangos)
        self.assertGreater(s["km"], 100)
        self.assertIn(s["camion"]["id"], sugerencias.texto_para(s))
        self.assertIn("Angol", sugerencias.texto_para(s))

    def test_el_mas_combustible_gana_y_el_que_esta_en_revision_se_descarta(self):
        s = sugerencias.sugerir_para([self.angol.orden_id])
        otro = next(c for c in sugerencias.opciones_camion() if self.rango in c["rangos"] and c["id"] != s["camion"]["id"] and len(c["rangos"]) == 1)
        Telemetria.objects.create(camion_id=otro["id"], temp_camara=2.0, lat=-38.73, long=-72.6, combustible_pct=95, alerta_ruptura_frio=False)
        self.assertEqual(sugerencias.sugerir_para([self.angol.orden_id])["camion"]["id"], otro["id"])
        RevisionCamion.objects.create(camion_id=otro["id"], motivo="otro")                  # en revisión no se sugiere
        self.assertNotEqual(sugerencias.sugerir_para([self.angol.orden_id])["camion"]["id"], otro["id"])

    def test_un_viaje_largo_pide_mas_combustible(self):
        for c in Camion.objects.all():
            Telemetria.objects.create(camion=c, temp_camara=2.0, lat=-38.73, long=-72.6, combustible_pct=40, alerta_ruptura_frio=False)
        s = sugerencias.sugerir_para([self.angol.orden_id])
        self.assertTrue(s["viaje_largo"])
        self.assertIsNone(s["camion"])                                                       # 40 % no alcanza para ~270 km de ida y vuelta
        self.assertIn("pide al menos 50 %", s["descartados"][0]["motivo"])
        self.assertIn("no hay un camión libre", sugerencias.texto_para(s))

    def test_la_ia_solo_redacta_y_se_descarta_si_inventa_un_camion(self):
        s = sugerencias.sugerir_para([self.angol.orden_id])
        with patch.object(ia, "redactar", return_value="Usa CAM-999, es el mejor."):
            texto, por_ia = sugerencias.redactar_para(s)
        self.assertFalse(por_ia)
        self.assertEqual(texto, sugerencias.texto_para(s))
        cache.clear()
        buena = f"{s['camion']['id']} sirve para Angol y tiene combustible de sobra."
        with patch.object(ia, "redactar", return_value=buena):
            texto, por_ia = sugerencias.redactar_para(s)
        self.assertTrue(por_ia)
        self.assertEqual(texto, buena)
        with patch.object(ia, "redactar", return_value=buena) as llamada:
            sugerencias.redactar_para(s)
            enviado = llamada.call_args[0][0] if llamada.called else ""
        for c in ("Hospital", "@", self.angol.direccion.cliente.nombre):
            self.assertNotIn(c, enviado)                                                     # a la IA no le llegan clientes

    def test_la_vista_la_ven_admin_gerencia_y_despacho_y_nadie_mas(self):
        url = f"/flota/despachar/sugerir-camion/?ordenes={self.angol.orden_id}"
        for u in ("admin@cofrial.cl", "despacho@cofrial.cl", "gerencia@cofrial.cl"):
            self.client.logout()
            self.assertTrue(self.client.login(username=u, password=CLAVE))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, u)
            self.assertIn("texto", r.json())
        for u in ("vendedora@cofrial.cl", "ana@correo.test"):
            self.client.logout()
            self.assertTrue(self.client.login(username=u, password=CLAVE))
            self.assertIn(self.client.get(url).status_code, (302, 403), u)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertTrue(self.client.login(username="admin@cofrial.cl", password=CLAVE))
        self.assertTrue(self.client.get("/flota/despachar/sugerir-camion/?ordenes=abc,²,99999").json()["vacio"])
