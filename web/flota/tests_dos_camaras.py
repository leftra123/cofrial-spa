"""Camiones de dos cámaras: un carrito con frío y congelado sale en un solo viaje, y una falla en una cámara afecta solo a los pedidos de esa cámara."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from catalogo.models import Producto, RangoTemperatura
from crm import servicios as crm
from flota import rutas, servicios as flota, sugerencias
from flota.models import Camion, Telemetria
from flota.vigente import ultima_vigente, ultimas_vigentes
from pedidos import servicios as s
from pedidos.models import Orden

CLAVE = "demo-cofrial-2026"
REFRIGERADO, CONGELADO = "VAC-LOM-5K", "PES-MER-5K"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        self.ana = s.cliente_de(get_user_model().objects.get(username="ana@correo.test"))

    def carrito_mixto(self):
        s.agregar(self.ana, Producto.objects.get(sku=REFRIGERADO).pk, 1)
        s.agregar(self.ana, Producto.objects.get(sku=CONGELADO).pk, 1)
        ordenes = s.generar_ordenes(self.ana, self.ana.direccion_set.first().pk)
        self.assertEqual(len(ordenes), 2)                # RN-09: una orden por rango, aunque viajen juntas
        return ordenes

    def por_rango(self, ordenes):
        return {flota.rangos_de(o)[0]: o for o in ordenes}

    def lectura(self, camion, camara, temp, alerta):
        return Telemetria.objects.create(camion=camion, camara=camara, temp_camara=temp, lat=-38.74, long=-72.60, combustible_pct=70, alerta_ruptura_frio=alerta)


class FlotaTests(Base):
    def test_solo_una_parte_de_la_flota_tiene_dos_camaras(self):
        dobles = Camion.objects.filter(rango_secundario__isnull=False)
        self.assertEqual(sorted(dobles.values_list("pk", flat=True)), ["CAM-05", "CAM-14", "CAM-23", "CAM-32", "CAM-41"])
        self.assertEqual(Camion.objects.count(), 50)
        c = dobles.first()
        self.assertEqual(c.rangos, ["Refrigerado", "Congelado"])
        self.assertEqual((c.camara_de("Refrigerado"), c.camara_de("Congelado")), (1, 2))

    def test_cargar_la_demo_otra_vez_no_cambia_nada(self):
        call_command("cargar_demo", verbosity=0)
        self.assertEqual(Camion.objects.filter(rango_secundario__isnull=False).count(), 5)

    def test_las_dos_camaras_no_pueden_tener_el_mismo_rango(self):
        c = Camion.objects.get(pk="CAM-01")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Camion.objects.filter(pk=c.pk).update(rango_secundario=c.rango_temperatura)

    def test_un_camion_simple_tiene_un_solo_rango(self):
        c = Camion.objects.get(pk="CAM-01")
        self.assertFalse(c.dos_camaras)
        self.assertEqual(c.rangos, ["Refrigerado"])
        self.assertEqual(c.camara_de("Congelado"), 1)
        self.assertEqual(c.rango_de_camara(2), c.rango_temperatura)


class DespachoTests(Base):
    def test_un_carrito_mixto_sale_en_un_solo_viaje_con_una_sola_parada(self):
        ordenes = self.carrito_mixto()
        d = flota.despachar("CAM-05", [o.pk for o in ordenes])
        por_rango = self.por_rango(Orden.objects.filter(despacho=d))
        self.assertEqual(por_rango["Refrigerado"].camara, 1)
        self.assertEqual(por_rango["Congelado"].camara, 2)
        self.assertEqual(len(d.ruta_geojson["paradas"]), 1)

    def test_un_camion_simple_no_lleva_el_otro_rango(self):
        ordenes = self.carrito_mixto()
        with self.assertRaises(s.ErrorDeNegocio):
            flota.despachar("CAM-01", [o.pk for o in ordenes])
        self.assertFalse(Orden.objects.filter(pk__in=[o.pk for o in ordenes], despacho__isnull=False).exists())

    def test_la_sugerencia_junta_el_carrito_mixto_en_un_camion_de_dos_camaras(self):
        ordenes = self.carrito_mixto()
        viajes, _ = sugerencias.calcular()
        viaje = next(v for v in viajes if {p["orden"] for p in v["pedidos"]} >= {o.pk for o in ordenes})
        self.assertTrue(Camion.objects.get(pk=viaje["camion"]).dos_camaras)
        self.assertEqual(viaje["rango"], "Refrigerado y Congelado")
        self.assertIn("de refrigerado y congelado", sugerencias.texto_base([viaje], {"sin_camion": [], "sin_ubicar": [], "mixtos": []}))

    def test_para_un_solo_rango_se_prefiere_un_camion_simple(self):
        s.agregar(self.ana, Producto.objects.get(sku=REFRIGERADO).pk, 1)
        orden = s.generar_ordenes(self.ana, self.ana.direccion_set.first().pk)[0]
        viaje = next(v for v in sugerencias.calcular()[0] if orden.pk in {p["orden"] for p in v["pedidos"]})
        self.assertFalse(Camion.objects.get(pk=viaje["camion"]).dos_camaras)

    def test_sin_camiones_simples_libres_sirve_uno_de_dos_camaras(self):
        Camion.objects.filter(rango_secundario__isnull=True).update(activo=False)
        s.agregar(self.ana, Producto.objects.get(sku=CONGELADO).pk, 1)
        orden = s.generar_ordenes(self.ana, self.ana.direccion_set.first().pk)[0]
        viaje = next(v for v in sugerencias.calcular()[0] if orden.pk in {p["orden"] for p in v["pedidos"]})
        self.assertTrue(Camion.objects.get(pk=viaje["camion"]).dos_camaras)
        flota.despachar(viaje["camion"], [orden.pk])
        orden.refresh_from_db()
        self.assertEqual(orden.camara, 2)

    def test_la_pantalla_de_armar_despacho_conoce_los_dos_rangos(self):
        self.assertTrue(self.client.login(username="despacho@cofrial.cl", password=CLAVE))
        r = self.client.get("/flota/despachar/")
        self.assertContains(r, 'data-rangos="Refrigerado,Congelado"')
        self.assertContains(r, "Refrigerado y Congelado")


class FallaPorCamaraTests(Base):
    def viaje(self):
        ordenes = self.carrito_mixto()
        d = flota.despachar("CAM-05", [o.pk for o in ordenes])
        return d, self.por_rango(Orden.objects.filter(despacho=d))

    def test_una_falla_en_la_camara_2_afecta_solo_al_pedido_congelado(self):
        d, o = self.viaje()
        self.lectura(d.camion, 1, 2.0, False)
        self.lectura(d.camion, 2, -5.0, True)
        ref, con = s.seguimiento(o["Refrigerado"]), s.seguimiento(o["Congelado"])
        self.assertFalse(ref["hubo_ruptura"])
        self.assertTrue(con["hubo_ruptura"])
        self.assertEqual(ref["ultima"]["temp_camara"], 2.0)
        self.assertEqual(con["ultima"]["temp_camara"], -5.0)
        self.assertEqual(ref["banda"]["nombre"], "Refrigerado")
        self.assertEqual(con["banda"]["nombre"], "Congelado")
        self.assertEqual(crm.telemetria_del_viaje(o["Refrigerado"])["alertas"], 0)
        self.assertEqual(crm.telemetria_del_viaje(o["Congelado"])["alertas"], 1)
        self.assertEqual(float(crm.telemetria_del_viaje(o["Congelado"])["limite"]), -18.0)

    def test_el_aviso_de_frio_llega_solo_al_pedido_de_esa_camara(self):
        d, o = self.viaje()
        self.lectura(d.camion, 2, -5.0, True)
        frio = {a["orden_id"] for a in s.avisos_de_llegada(self.ana) if a["tipo"] == "frio"}
        self.assertEqual(frio, {o["Congelado"].pk})

    def test_la_flota_ve_el_camion_en_alerta_si_cualquier_camara_lo_esta(self):
        c = Camion.objects.get(pk="CAM-05")
        self.lectura(c, 1, 2.0, False)
        self.lectura(c, 2, -5.0, True)
        t = ultimas_vigentes()["CAM-05"]
        self.assertTrue(t.alerta_ruptura_frio)
        self.assertEqual(t.camara, 2)
        self.assertEqual([x.camara for x in t.camaras], [1, 2])
        self.assertEqual(ultima_vigente(c, 1).temp_camara, 2.0)
        self.assertTrue(self.client.login(username="despacho@cofrial.cl", password=CLAVE))
        html = self.client.get("/flota/").content.decode()
        self.assertIn('data-campo="temp-2"', html)
        api = next(x for x in self.client.get("/api/flota/").json()["camiones"] if x["camion_id"] == "CAM-05")
        self.assertEqual(api["rangos"], ["Refrigerado", "Congelado"])
        self.assertEqual(len(api["ultima_lectura"]["camaras"]), 2)

    def test_dos_camaras_pueden_informar_en_el_mismo_instante(self):
        c = Camion.objects.get(pk="CAM-05")
        a, b = self.lectura(c, 1, 2.0, False), self.lectura(c, 2, -20.0, False)
        Telemetria.objects.filter(pk=b.pk).update(registrado_en=a.registrado_en)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Telemetria.objects.filter(pk=self.lectura(c, 1, 2.0, False).pk).update(registrado_en=a.registrado_en)

    def test_podar_conserva_la_ultima_de_cada_camara(self):
        from datetime import timedelta
        from django.utils import timezone
        c = Camion.objects.get(pk="CAM-05")
        viejas = [self.lectura(c, 1, 2.0, False), self.lectura(c, 2, -20.0, False)]
        hace_un_mes = timezone.now() - timedelta(days=30)
        Telemetria.objects.filter(pk__in=[x.pk for x in viejas]).update(registrado_en=hace_un_mes)
        self.assertFalse(flota.lecturas_prescindibles(timezone.now()).filter(pk__in=[x.pk for x in viejas]).exists())

    def test_la_demostracion_fuerza_la_falla_en_la_camara_elegida(self):
        self.assertTrue(self.client.login(username="admin@cofrial.cl", password=CLAVE))
        r = self.client.post("/demo/pulso/", {"camion": "CAM-05", "camara": "2", "confirmar": "1"})
        self.assertEqual(r.status_code, 200)
        t = Telemetria.objects.filter(camion_id="CAM-05", forzada=True).latest("registrado_en")
        self.assertEqual(t.camara, 2)
        self.assertGreater(t.temp_camara, -18.0)
        self.assertLess(t.temp_camara, 0)
        self.client.post("/demo/pulso/", {"camion": "CAM-01", "camara": "2", "confirmar": "1"})
        self.assertEqual(Telemetria.objects.filter(camion_id="CAM-01", forzada=True).latest("registrado_en").camara, 1)
