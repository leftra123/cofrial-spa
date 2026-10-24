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
        for usuario in ("ana@correo.test", "vendedora@cofrial.cl"):
            self.entrar(usuario)
            self.assertEqual(self.client.get("/api/flota/").status_code, 403, usuario)

    def test_despachador_ve_flota_con_ultima_lectura_y_resumen(self):
        self.entrar("despacho@cofrial.cl")
        r = self.client.get("/api/flota/")
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        cam = {c["camion_id"]: c for c in datos["camiones"]}["CAM-01"]
        self.assertTrue(cam["alerta"] and cam["combustible_bajo"] and cam["en_ruta"])
        self.assertEqual(cam["ultima_lectura"]["combustible_pct"], 15)
        self.assertEqual(datos["resumen"]["con_alerta"], 1)
        self.assertIsNone({c["camion_id"]: c for c in datos["camiones"]}["CAM-03"]["ultima_lectura"])

    def test_la_api_es_de_solo_lectura(self):
        self.entrar("despacho@cofrial.cl")
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


class ArmarDespachoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def _pedido(self, usuario, sku, cantidad=2):
        from pedidos import servicios as ps
        cliente = ps.cliente_de(__import__("django.contrib.auth", fromlist=["x"]).get_user_model().objects.get(username=usuario))
        ps.agregar(cliente, __import__("catalogo.models", fromlist=["x"]).Producto.objects.get(sku=sku).pk, cantidad)
        return ps.generar_orden(cliente, cliente.direccion_set.first().pk, "OC-T" if cliente.tipo_cliente.codigo == "B2B" else "")

    def _entrar(self, usuario="despacho@cofrial.cl"):
        self.client.login(username=usuario, password="demo-cofrial-2026")

    def test_solo_el_personal_de_despacho_entra(self):
        self.client.login(username="ana@correo.test", password="demo-cofrial-2026")
        self.assertEqual(self.client.get("/flota/despachar/").status_code, 403)
        self.client.logout()
        self.client.login(username="vendedora@cofrial.cl", password="demo-cofrial-2026")
        self.assertEqual(self.client.get("/flota/despachar/").status_code, 403)

    def test_despacha_dos_pedidos_en_un_camion_y_quedan_despachados(self):
        from flota.models import Despacho
        a = self._pedido("ana@correo.test", "POL-PEC-10K")
        b = self._pedido("abastecimiento@hospital.test", "VAC-LOM-5K")
        self._entrar()
        self.assertContains(self.client.get("/flota/despachar/"), f"Orden N.º {a.orden_id}")
        r = self.client.post("/flota/despachar/", {"camion": "CAM-03", "ordenes": [a.orden_id, b.orden_id]})
        self.assertRedirects(r, "/flota/", fetch_redirect_response=False)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(a.estado_orden.nombre, "Despachada")
        self.assertEqual(a.despacho_id, b.despacho_id)
        self.assertEqual(a.despacho.camion_id, "CAM-03")
        self.assertIsNotNone(Despacho.objects.get(pk=a.despacho_id).salida_en)

    def test_no_mezcla_cadena_de_frio(self):
        congelado = self._pedido("abastecimiento@hospital.test", "PES-FIL-3K")
        self._entrar()
        self.client.post("/flota/despachar/", {"camion": "CAM-03", "ordenes": [congelado.orden_id]})     # CAM-03 es refrigerado
        congelado.refresh_from_db()
        self.assertIsNone(congelado.despacho_id)
        r = self.client.get("/flota/despachar/")
        self.assertContains(r, "CAM-03 es refrigerado")

    def test_camion_en_ruta_no_se_ofrece(self):
        r = self.client.post("/cuenta/entrar/", {"username": "despacho@cofrial.cl", "password": "demo-cofrial-2026"})
        pagina = self.client.get("/flota/despachar/")
        self.assertNotContains(pagina, 'value="CAM-01"')       # CAM-01 y CAM-02 tienen viaje en curso en la demostración
        self.assertContains(pagina, 'value="CAM-03"')


class ModoDemostracion(TestCase):
    """La ruptura forzada es solo para administradores, pide confirmación, se marca como forzada y se puede apagar y borrar."""
    CLAVE = "demo-cofrial-2026"

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def _admin(self):
        self.assertTrue(self.client.login(username="admin@cofrial.cl", password=self.CLAVE))

    def test_solo_el_administrador_entra(self):
        self.assertEqual(self.client.get("/demo/").status_code, 302)                       # sin sesión
        self.client.login(username="ana@correo.test", password=self.CLAVE)
        self.assertEqual(self.client.get("/demo/").status_code, 403)                        # cliente
        self.assertEqual(self.client.post("/demo/pulso/", {"camion": "CAM-01", "confirmar": "1"}).status_code, 403)
        self.assertEqual(Telemetria.objects.filter(forzada=True).count(), 0)

    def test_exige_confirmacion_y_marca_las_lecturas(self):
        self._admin()
        self.assertEqual(self.client.post("/demo/pulso/", {"camion": "CAM-01"}).status_code, 400)
        self.assertEqual(Telemetria.objects.filter(forzada=True).count(), 0)
        r = self.client.post("/demo/pulso/", {"camion": "CAM-01", "confirmar": "1"}).json()
        self.assertTrue(r["activa"])
        lectura = Telemetria.objects.get(forzada=True)
        tmax = float(Camion.objects.get(pk="CAM-01").rango_temperatura.temp_max_c)
        self.assertTrue(lectura.alerta_ruptura_frio)
        self.assertGreater(lectura.temp_camara, tmax)
        # el siguiente pulso sigue sin pedir confirmación; apagar deja una lectura normal
        self.assertEqual(self.client.post("/demo/pulso/", {"camion": "CAM-01"}).status_code, 200)
        self.client.post("/demo/apagar/", {"camion": "CAM-01"})
        ultima = Telemetria.objects.filter(camion_id="CAM-01").latest("registrado_en")
        self.assertFalse(ultima.alerta_ruptura_frio)
        self.assertTrue(ultima.forzada)

    def test_limpiar_borra_solo_lo_forzado(self):
        self._admin()
        real = Telemetria.objects.create(camion_id="CAM-01", temp_camara=2.0, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=False)
        self.client.post("/demo/pulso/", {"camion": "CAM-01", "confirmar": "1"})
        self.assertEqual(self.client.post("/demo/limpiar/", {}).status_code, 400)           # sin confirmar no borra
        self.assertEqual(self.client.post("/demo/limpiar/", {"confirmar": "1"}).json()["borradas"], 1)
        self.assertTrue(Telemetria.objects.filter(pk=real.pk).exists())

    def test_se_corta_al_pasar_el_tiempo_maximo(self):
        from flota import demo
        self._admin()
        self.client.post("/demo/pulso/", {"camion": "CAM-01", "confirmar": "1"})
        sesion = self.client.session
        t = sesion["demo_CAM-01"]; t["inicio"] -= demo.DURACION_MAX_S + 5; t["ultimo"] = timezone.now().timestamp()
        sesion["demo_CAM-01"] = t; sesion.save()
        n = Telemetria.objects.filter(forzada=True).count()
        r = self.client.post("/demo/pulso/", {"camion": "CAM-01"})
        self.assertEqual(r.status_code, 400)                                                  # ya no hay ruptura activa: pide confirmar de nuevo
        self.assertEqual(Telemetria.objects.filter(forzada=True).count(), n)

    def test_el_cliente_del_camion_recibe_el_aviso_en_la_campanita(self):
        from datetime import timedelta
        from pedidos.models import Orden
        orden = Orden.objects.exclude(despacho=None).first()
        if orden is None:
            self.skipTest("la demostración no trae órdenes despachadas")
        d = orden.despacho
        type(d).objects.filter(pk=d.pk).update(salida_en=timezone.now() - timedelta(minutes=5), llegada_en=None)
        self._admin()
        self.client.post("/demo/pulso/", {"camion": d.camion_id, "confirmar": "1"})
        self.client.logout()
        self.client.force_login(orden.direccion.cliente.usuario)
        tipos = {a["tipo"] for a in self.client.get("/api/avisos/").json()["avisos"] if a["orden_id"] == orden.orden_id}
        self.assertIn("frio", tipos)

    def test_la_flota_sigue_en_alerta_aunque_el_simulador_inserte_una_lectura_normal(self):
        from datetime import timedelta
        from flota.servicios import estado_flota
        self._admin()
        self.client.post("/demo/pulso/", {"camion": "CAM-01", "confirmar": "1"})
        # el simulador inserta una lectura normal después de la forzada: antes la flota alternaba entre alerta y normal
        Telemetria.objects.create(camion_id="CAM-01", temp_camara=2.0, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=False)
        tarjetas, resumen = estado_flota()
        t = next(x for x in tarjetas if x["camion"].pk == "CAM-01")
        self.assertTrue(t["alerta"])
        self.assertGreater(t["lectura"].temp_camara, 4)
        self.assertEqual(t["lectura"].combustible_pct, 50)                                   # posición y combustible: los de la lectura real
        self.assertEqual(self.client.get("/api/flota/").json()["camiones"][0]["camion_id"], "CAM-01")
        # al apagar vuelve a la normalidad
        self.client.post("/demo/apagar/", {"camion": "CAM-01"})
        self.assertFalse(next(x for x in estado_flota()[0] if x["camion"].pk == "CAM-01")["alerta"])

    def test_una_forzada_vieja_ya_no_cuenta(self):
        from datetime import timedelta
        from flota.servicios import estado_flota
        self._admin()
        self.client.post("/demo/pulso/", {"camion": "CAM-01", "confirmar": "1"})
        Telemetria.objects.filter(forzada=True).update(registrado_en=timezone.now() - timedelta(seconds=60))
        Telemetria.objects.create(camion_id="CAM-01", temp_camara=2.0, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=False)
        self.assertFalse(next(x for x in estado_flota()[0] if x["camion"].pk == "CAM-01")["alerta"])


class AccesibilidadMapaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_mapas_son_regiones_y_los_marcadores_tienen_nombre(self):
        self.client.login(username="despacho@cofrial.cl", password="demo-cofrial-2026")
        for ruta, contenedor in (("/flota/", 'id="mapa-flota"'), ("/flota/despachar/", 'id="mapa-despacho"')):
            html = self.client.get(ruta).content.decode()
            etiqueta = html[html.index(contenedor):].split(">")[0]
            self.assertIn('role="region"', etiqueta)               # un contenedor con controles dentro no puede ser role="img"
            self.assertNotIn('role="img"', etiqueta)
            self.assertIn("title:", html)                          # los marcadores se crean con título (nombre accesible)


class EncuadreFlotaTests(TestCase):
    def test_el_encuadre_del_mapa_incluye_a_los_camiones(self):
        call_command("cargar_demo", verbosity=0)
        self.client.login(username="despacho@cofrial.cl", password="demo-cofrial-2026")
        html = self.client.get("/flota/").content.decode()
        self.assertIn("d.camiones.forEach(function (c) { todos.push([c.lat, c.long]); });", html)
        self.assertIn("maxZoom: 15", html)
