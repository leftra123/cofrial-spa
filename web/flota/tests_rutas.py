"""Rutas por calles guardadas, caché, respaldo, estado de los camiones y siembra de comunas."""
import json
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from clientes.models import Comuna
from flota import rutas, servicios
from flota.models import Despacho, RutaCache

CASA = (-38.7400, -72.6000)
OTRA = (-38.7500, -72.6200)


def respuesta_osrm(coordenadas):
    cuerpo = json.dumps({"code": "Ok", "routes": [{"geometry": {"coordinates": coordenadas}}]}).encode()
    r = MagicMock()
    r.__enter__.return_value.read.return_value = cuerpo
    r.__enter__.return_value.__iter__ = lambda self: iter([cuerpo])
    return r


class RutasPorCallesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_sin_osrm_la_ruta_son_rectas_marcadas_como_aproximadas_y_nunca_falla(self):
        ruta = rutas.armar_ruta([(1, *CASA), (2, *OTRA)])
        self.assertTrue(ruta["aproximada"])
        self.assertEqual(len(ruta["puntos"]), 4)                          # base, dos paradas y base
        self.assertEqual([p["direccion_id"] for p in ruta["paradas"]], [1, 2])      # la más cercana a la base primero
        self.assertEqual(ruta["puntos"][0], ruta["puntos"][-1])           # vuelve a la base
        self.assertEqual(RutaCache.objects.count(), 0)                    # una ruta aproximada no se guarda en la caché

    def test_sin_paradas_ubicadas_no_hay_ruta(self):
        self.assertIsNone(rutas.armar_ruta([(1, None, None)]))

    @override_settings(OSRM_URL="http://osrm.prueba")
    def test_con_osrm_usa_la_ruta_por_calles_y_la_cachea(self):
        calles = [[-72.604, -38.733], [-72.602, -38.737], [-72.600, -38.740], [-72.602, -38.737], [-72.604, -38.733]]
        with patch("flota.rutas.urllib.request.urlopen", return_value=respuesta_osrm(calles)) as pedido:
            primera = rutas.armar_ruta([(1, *CASA)])
            segunda = rutas.armar_ruta([(1, *CASA)])
        self.assertEqual(pedido.call_count, 1)                            # la misma secuencia no vuelve a pedirse
        self.assertFalse(primera["aproximada"])
        self.assertEqual(primera["puntos"][2], [-38.740, -72.600])        # OSRM entrega lon,lat; se guarda lat,long
        self.assertEqual(primera, segunda)
        self.assertEqual(RutaCache.objects.count(), 1)
        self.assertEqual(primera["paradas"][0]["indice"], 2)

    @override_settings(OSRM_URL="http://osrm.prueba", OSRM_TIMEOUT_SEG=1)
    def test_si_osrm_falla_reintenta_una_vez_y_cae_a_la_recta(self):
        import urllib.error
        with patch("flota.rutas.urllib.request.urlopen", side_effect=urllib.error.URLError("sin red")) as pedido:
            ruta = rutas.armar_ruta([(1, *CASA)])
        self.assertEqual(pedido.call_count, 2)                            # un reintento
        self.assertTrue(ruta["aproximada"])

    def test_km_hasta_cuenta_el_camino_por_la_polilinea(self):
        ruta = {"puntos": [[-38.73, -72.60], [-38.74, -72.60], [-38.74, -72.59]]}
        directo = rutas.km_entre((-38.73, -72.60), (-38.74, -72.59))
        por_calles = rutas.km_hasta(ruta, (-38.73, -72.60), 2)
        self.assertGreater(por_calles, directo)                           # el camino con esquina es más largo que la recta


class DespachoGuardaSuRutaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def _orden(self):
        from catalogo.models import Producto
        from django.contrib.auth import get_user_model
        from pedidos import servicios as p
        cliente = p.cliente_de(get_user_model().objects.get(username="ana@correo.test"))
        p.agregar(cliente, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
        return p.generar_ordenes(cliente, cliente.direccion_set.first().pk)[0]

    def test_al_despachar_se_guarda_la_polilinea_con_la_parada(self):
        orden = self._orden()
        camion = next(c for c in servicios.camiones_libres() if c.rango_temperatura.nombre == "Refrigerado")
        d = servicios.despachar(camion.camion_id, [orden.pk])
        d.refresh_from_db()
        self.assertTrue(d.ruta_geojson["puntos"])
        self.assertEqual(d.ruta_geojson["paradas"][0]["direccion_id"], orden.direccion_id)
        self.assertEqual(d.ruta_aproximada, d.ruta_geojson["aproximada"])

    def test_el_camion_no_queda_libre_hasta_volver_a_la_base(self):
        orden = self._orden()
        camion = next(c for c in servicios.camiones_libres() if c.rango_temperatura.nombre == "Refrigerado")
        d = servicios.despachar(camion.camion_id, [orden.pk])
        from django.utils import timezone
        Despacho.objects.filter(pk=d.pk).update(llegada_en=timezone.now(), fase="volviendo")          # llegó a la última parada, vuelve
        self.assertNotIn(camion.camion_id, {c.camion_id for c in servicios.camiones_libres()})
        Despacho.objects.filter(pk=d.pk).update(regreso_en=timezone.now())                            # de vuelta en la base
        self.assertIn(camion.camion_id, {c.camion_id for c in servicios.camiones_libres()})

    def test_un_despacho_viejo_sin_ruta_la_calcula_una_vez_y_la_guarda(self):
        d = Despacho.objects.filter(salida_en__isnull=False, regreso_en__isnull=True).first()
        Despacho.objects.filter(pk=d.pk).update(ruta_geojson=None)         # como un viaje anterior a las rutas guardadas
        d.refresh_from_db()
        ruta = rutas.asegurar_ruta(d)
        d.refresh_from_db()
        self.assertEqual(d.ruta_geojson["puntos"], ruta["puntos"])

    def test_la_vista_previa_y_la_ruta_guardada_son_la_misma(self):
        orden = self._orden()
        self.client.login(username="despacho@cofrial.cl", password="demo-cofrial-2026")
        previa = self.client.get(f"/flota/despachar/ruta/?ordenes={orden.pk}").json()["ruta"]
        camion = next(c for c in servicios.camiones_libres() if c.rango_temperatura.nombre == "Refrigerado")
        d = servicios.despachar(camion.camion_id, [orden.pk])
        d.refresh_from_db()
        self.assertEqual(previa["puntos"], d.ruta_geojson["puntos"])
        self.assertEqual(previa["paradas"][0]["ordenes"], [orden.pk])

    def test_la_vista_previa_exige_rol(self):
        self.client.login(username="ana@correo.test", password="demo-cofrial-2026")
        self.assertEqual(self.client.get("/flota/despachar/ruta/?ordenes=1").status_code, 403)


class SituacionDeLosCamionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_sin_despacho_esta_en_base_y_con_despacho_segun_su_fase(self):
        tarjetas, resumen = servicios.estado_flota()
        por_camion = {t["camion"].camion_id: t["situacion"] for t in tarjetas}
        self.assertEqual(por_camion["CAM-10"], "en_base")
        con_viaje = [t for t in tarjetas if t["viaje"]]
        self.assertTrue(con_viaje)
        for t in con_viaje:
            self.assertEqual(t["situacion"], "en_ruta")
        self.assertEqual(resumen["en_ruta"], len(con_viaje))
        self.assertEqual(resumen["en_base"], resumen["total"] - len(con_viaje))
        Despacho.objects.filter(pk=con_viaje[0]["viaje"].pk).update(fase="en_la_puerta")
        _, resumen = servicios.estado_flota()
        self.assertEqual((resumen["en_la_puerta"], resumen["en_ruta"]), (1, len(con_viaje) - 1))

    def test_la_api_y_el_panel_muestran_la_situacion(self):
        self.client.login(username="despacho@cofrial.cl", password="demo-cofrial-2026")
        d = self.client.get("/api/flota/").json()
        self.assertEqual({"en_base", "en_ruta", "en_la_puerta", "volviendo"} <= set(d["resumen"]), True)
        self.assertIn("situacion_texto", d["camiones"][0])
        self.assertContains(self.client.get("/flota/"), "En base")


class ComunasTests(TestCase):
    def test_la_siembra_trae_las_comunas_de_la_araucania_ordenadas_y_es_idempotente(self):
        call_command("cargar_demo", verbosity=0)
        n = Comuna.objects.count()
        self.assertGreaterEqual(n, 20)
        call_command("cargar_demo", verbosity=0)
        self.assertEqual(Comuna.objects.count(), n)
        nombres = list(Comuna.objects.order_by("nombre").values_list("nombre", flat=True))
        self.assertIn("Temuco", nombres)
        self.assertIn("Pucón", nombres)
        r = self.client.get("/cuenta/registro/")
        html = r.content.decode()
        orden = [html.index(f">{c}<") for c in nombres]
        self.assertEqual(orden, sorted(orden))                           # el formulario las lista ordenadas
