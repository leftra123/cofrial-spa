from unittest.mock import patch

from decimal import Decimal

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from catalogo.models import RangoTemperatura
from flota.models import Camion, Telemetria


class TelemetriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rango = RangoTemperatura.objects.create(nombre="Refrigerado", temp_min_c=Decimal("0"), temp_max_c=Decimal("4"))
        cls.camion = Camion.objects.create(camion_id="CAM-T1", patente="AAAA-11", capacidad_kg=5000, rango_temperatura=rango)

    def test_campos_exigidos_por_la_pauta(self):
        columnas = {f.column: f.get_internal_type() for f in Telemetria._meta.get_fields() if hasattr(f, "column")}
        for nombre, tipo in {"camion_id": "ForeignKey", "temp_camara": "FloatField", "lat": "FloatField", "long": "FloatField",
                             "combustible_pct": "IntegerField", "alerta_ruptura_frio": "BooleanField"}.items():
            self.assertEqual(columnas.get(nombre), tipo, nombre)
        self.assertEqual(Camion._meta.pk.get_internal_type(), "CharField")   # camion_id es texto

    def _lectura(self, **extra):
        datos = dict(camion=self.camion, temp_camara=3.0, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=False)
        datos.update(extra)
        return Telemetria.objects.create(**datos)

    def test_inserta_una_lectura_valida(self):
        self.assertIsNotNone(self._lectura().pk)

    def test_rechaza_valores_fuera_de_rango(self):
        for malo in ({"combustible_pct": 101}, {"lat": 91}, {"long": -181}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                self._lectura(**malo)


class ApiFlotaTests(TestCase):
    """API JSON de solo lectura: permisos por rol y forma de la respuesta."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command("cargar_demo", verbosity=0)
        Telemetria.objects.create(camion_id="CAM-01", temp_camara=7.5, lat=-38.7, long=-72.6, combustible_pct=15, alerta_ruptura_frio=True)

    def entrar(self, usuario):
        from crm.tests import CLAVE
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def test_exige_sesion(self):
        self.assertEqual(self.client.get("/api/flota/").status_code, 403)
        self.assertEqual(self.client.get("/api/pedidos/").status_code, 403)

    def test_cliente_y_vendedor_no_ven_la_flota(self):
        for usuario in ("ana@correo.test", "vendedora@cofrial.test"):
            self.entrar(usuario)
            self.assertEqual(self.client.get("/api/flota/").status_code, 403, usuario)

    def test_despachador_ve_flota_con_ultima_lectura_y_resumen(self):
        self.entrar("despachador@cofrial.test")
        r = self.client.get("/api/flota/")
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        cam = {c["camion_id"]: c for c in datos["camiones"]}["CAM-01"]
        self.assertTrue(cam["alerta"] and cam["combustible_bajo"] and cam["en_ruta"])
        self.assertEqual(cam["ultima_lectura"]["combustible_pct"], 15)
        self.assertEqual(datos["resumen"]["con_alerta"], 1)
        self.assertIsNone({c["camion_id"]: c for c in datos["camiones"]}["CAM-03"]["ultima_lectura"])

    def test_la_api_es_de_solo_lectura(self):
        self.entrar("despachador@cofrial.test")
        self.assertEqual(self.client.post("/api/flota/", {}).status_code, 405)

    def test_pedidos_devuelve_solo_las_ordenes_del_cliente(self):
        self.entrar("abastecimiento@hospital.test")
        r = self.client.get("/api/pedidos/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["cliente"], "Hospital Regional de Temuco")
        self.assertEqual(len(r.json()["ordenes"]), 1)
        self.entrar("ana@correo.test")
        self.assertEqual(self.client.get("/api/pedidos/").json()["ordenes"], [])


class SeguimientoPedidoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def _orden(self, oc):
        from pedidos.models import Orden
        return Orden.objects.get(numero_oc=oc)

    def test_cliente_ve_temperatura_y_posicion_de_su_camion(self):
        from flota.models import Camion, Telemetria
        o = self._orden("OC-2026-0457")
        Telemetria.objects.create(camion=o.despacho.camion, temp_camara=2.5, lat=-38.73, long=-72.59, combustible_pct=70, alerta_ruptura_frio=False)
        self.client.login(username="abastecimiento@hospital.test", password="demo-cofrial-2026")
        d = self.client.get(f"/api/pedidos/{o.orden_id}/seguimiento/").json()["seguimiento"]
        self.assertEqual(d["camion_id"], o.despacho.camion_id)
        self.assertEqual(d["ultima"]["temp_camara"], 2.5)
        self.assertFalse(d["hubo_ruptura"])
        self.assertAlmostEqual(d["destino"]["lat"], -38.73616, places=3)      # dirección ubicada para trazar la ruta
        self.assertEqual(len(d["serie"]), 1)
        r = self.client.get(f"/pedidos/{o.orden_id}/")
        self.assertContains(r, "Dónde va su pedido")

    def test_ruptura_de_frio_se_avisa(self):
        from flota.models import Telemetria
        o = self._orden("OC-2026-0457")
        Telemetria.objects.create(camion=o.despacho.camion, temp_camara=9.0, lat=-38.7, long=-72.5, combustible_pct=60, alerta_ruptura_frio=True)
        self.client.login(username="abastecimiento@hospital.test", password="demo-cofrial-2026")
        self.assertTrue(self.client.get(f"/api/pedidos/{o.orden_id}/seguimiento/").json()["seguimiento"]["hubo_ruptura"])

    def test_orden_ajena_no_se_ve(self):
        o = self._orden("OC-SUR-118")
        self.client.login(username="abastecimiento@hospital.test", password="demo-cofrial-2026")
        self.assertEqual(self.client.get(f"/api/pedidos/{o.orden_id}/seguimiento/").status_code, 404)
        self.client.logout()
        self.assertIn(self.client.get(f"/api/pedidos/{o.orden_id}/seguimiento/").status_code, (401, 403))

    def test_reportar_problema_liga_el_requerimiento_a_la_orden(self):
        from crm.models import Requerimiento
        o = self._orden("OC-2026-0457")
        self.client.login(username="abastecimiento@hospital.test", password="demo-cofrial-2026")
        self.assertContains(self.client.get(f"/soporte/?orden={o.orden_id}"), f"orden N.º {o.orden_id}")
        with patch("crm.ia.clasificar", side_effect=__import__("crm.ia", fromlist=["x"]).ErrorIA("sin red")):
            self.client.post("/soporte/", {"orden": o.orden_id, "asunto": "Llegó tibio", "descripcion": "La caja venía caliente."})
        self.assertEqual(Requerimiento.objects.get(asunto="Llegó tibio").orden_id, o.orden_id)

    def test_reporte_con_orden_ajena_se_ignora(self):
        from crm.models import Requerimiento
        o = self._orden("OC-SUR-118")
        self.client.login(username="abastecimiento@hospital.test", password="demo-cofrial-2026")
        with patch("crm.ia.clasificar", side_effect=__import__("crm.ia", fromlist=["x"]).ErrorIA("sin red")):
            self.client.post("/soporte/", {"orden": o.orden_id, "asunto": "Otro", "descripcion": "Texto."})
        self.assertIsNone(Requerimiento.objects.get(asunto="Otro").orden_id)
