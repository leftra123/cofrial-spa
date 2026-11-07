"""Reparto por toda La Araucanía y tiempo acelerado: la siembra regional, las rutas de ida y vuelta por la misma carretera, y que la hora de
llegada y los avisos sigan diciendo la verdad a cualquier velocidad."""
import json
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from catalogo.models import Producto
from clientes import cuentas_demo, regionales, rut as rutlib
from clientes.models import Cliente, Direccion
from flota import rutas, servicios, tiempo
from flota.models import AjusteSimulador, Telemetria
from pedidos import servicios as pedidos
from pedidos.models import Orden

CLAVE = "demo-cofrial-2026"
BASE = (-38.7330, -72.6040)
ANGOL_RUT = "70.300.104-1"
ANGOL_USUARIO = "abastecimiento@hospitalangol.test"


def respuesta_osrm(lon_lat):
    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, *a):
            return json.dumps({"code": "Ok", "routes": [{"geometry": {"coordinates": lon_lat}}]}).encode()
    return R()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario="admin@cofrial.cl"):
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def viaje_a_angol(self):
        """Despacha el pedido sembrado para Angol en un camión refrigerado libre. Devuelve la orden ya «Despachada», con una lectura del camión en la base."""
        orden = Orden.objects.get(numero_oc="OC-REG-001")
        despacho = servicios.despachar("CAM-05", [orden.pk])
        Telemetria.objects.create(camion_id="CAM-05", temp_camara=2.0, lat=BASE[0], long=BASE[1], combustible_pct=90, alerta_ruptura_frio=False)
        orden.refresh_from_db()
        return orden, despacho


class SiembraRegionalTests(Base):
    def test_hay_clientes_con_direccion_y_coordenadas_fijas_en_diez_comunas(self):
        direcciones = Direccion.objects.filter(cliente__rut__in=[h[2] for h in regionales.HOSPITALES])
        self.assertEqual(direcciones.count(), len(regionales.HOSPITALES))
        for d in direcciones:
            self.assertTrue(-39.7 < d.lat < -37.5 and -73.6 < d.long < -71.3, d)          # dentro de La Araucanía
            self.assertTrue(d.es_principal)
        comunas = set(Direccion.objects.filter(lat__isnull=False).values_list("comuna__nombre", flat=True))
        self.assertLessEqual({"Temuco", "Padre Las Casas", "Villarrica", "Pucón", "Angol", "Victoria", "Lautaro", "Nueva Imperial", "Carahue", "Loncoche"}, comunas)

    def test_las_mas_lejanas_estan_a_mas_de_cien_km_por_la_carretera(self):
        angol = Direccion.objects.get(cliente__rut=ANGOL_RUT)
        self.assertGreater(rutas.km_entre(BASE, (angol.lat, angol.long)) * settings.FACTOR_CALLES, 100)

    def test_los_ruts_son_validos_y_no_hay_personas(self):
        for _, nombre, rut, *_ in regionales.HOSPITALES:
            self.assertTrue(rutlib.es_valido(rut), rut)
            self.assertRegex(nombre, r"Hospital|Complejo Asistencial")

    def test_no_depende_de_nominatim(self):
        Direccion.objects.filter(cliente__rut="70.300.101-7").delete()          # el de Padre Las Casas no tiene pedidos sembrados
        with patch("clientes.geo.ubicar") as ubicar:
            call_command("cargar_demo", verbosity=0)
        ubicar.assert_not_called()
        self.assertIsNotNone(Direccion.objects.get(cliente__rut="70.300.101-7").lat)

    def test_correr_de_nuevo_no_duplica_ni_cambia_nada(self):
        def foto():
            return (Cliente.objects.count(), Direccion.objects.count(), Orden.objects.count(), get_user_model().objects.count(),
                    list(Producto.objects.order_by("pk").values_list("stock_disponible", flat=True)))
        antes = foto()
        call_command("cargar_demo", verbosity=0)
        call_command("cargar_demo", verbosity=0)
        self.assertEqual(foto(), antes)

    def test_un_pedido_ya_despachado_no_vuelve_a_aparecer(self):
        orden, _ = self.viaje_a_angol()
        call_command("cargar_demo", verbosity=0)
        self.assertEqual(Orden.objects.filter(numero_oc="OC-REG-001").count(), 1)
        orden.refresh_from_db()
        self.assertEqual(orden.estado_orden.nombre, "Despachada")

    def test_no_pisa_una_clave_ni_una_direccion_cambiadas(self):
        u = get_user_model().objects.get(username=ANGOL_USUARIO)
        u.set_password("mi-clave-propia")
        u.save()
        Direccion.objects.filter(cliente__rut=ANGOL_RUT).update(calle_numero="Otra calle 1", lat=-37.9)
        call_command("cargar_demo", verbosity=0)
        u.refresh_from_db()
        self.assertTrue(u.check_password("mi-clave-propia"))
        d = Direccion.objects.get(cliente__rut=ANGOL_RUT)
        self.assertEqual((d.calle_numero, d.lat), ("Otra calle 1", -37.9))

    def test_sin_stock_arranca_igual_y_crea_el_resto(self):
        Orden.objects.filter(numero_oc__startswith="OC-REG-").update(numero_oc="OC-VIEJA")
        Producto.objects.filter(sku="POL-ENT-10K").update(stock_disponible=0)
        call_command("cargar_demo", verbosity=0)
        self.assertFalse(Orden.objects.filter(numero_oc="OC-REG-001").exists())
        self.assertTrue(Orden.objects.filter(numero_oc="OC-REG-002").exists())

    def test_un_error_en_la_siembra_regional_no_impide_arrancar(self):
        with patch("clientes.regionales.sembrar", side_effect=RuntimeError("base rara")):
            call_command("cargar_demo", verbosity=0)

    def test_los_pedidos_quedan_listos_para_despachar_y_respetan_la_cadena_de_frio(self):
        por_despachar = {o.numero_oc: o for o in servicios.pedidos_por_despachar().filter(numero_oc__startswith="OC-REG-")}
        self.assertEqual(len(por_despachar), len(regionales.PEDIDOS))
        self.assertEqual(servicios.rangos_de(por_despachar["OC-REG-008"]), ["Congelado"])
        with self.assertRaises(pedidos.ErrorDeNegocio):
            servicios.despachar("CAM-05", [por_despachar["OC-REG-008"].pk])                # CAM-05 es refrigerado: la regla no cambia

    def test_las_cuentas_regionales_entran_y_estan_en_la_hoja(self):
        for usuario in (ANGOL_USUARIO, "abastecimiento@hospitalvillarrica.test", "abastecimiento@hospitalpucon.test"):
            self.assertIn(usuario, cuentas_demo.USUARIOS)
            self.assertTrue(self.client.login(username=usuario, password=CLAVE))
        self.client.logout()

    def test_un_cliente_regional_compra_para_su_comuna(self):
        cliente = Cliente.objects.get(rut=ANGOL_RUT)
        pedidos.agregar(cliente, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
        orden = pedidos.generar_orden(cliente, cliente.direccion_set.first().pk, "OC-PRUEBA")
        self.assertEqual(orden.direccion.comuna.nombre, "Angol")


class RutaDeIdaYVueltaTests(TestCase):
    """Ida y vuelta por la misma carretera, como un viaje real a Angol: los vértices de las dos pasadas están a metros."""
    IDA = [[-38.733, -72.604], [-38.50, -72.45], [-38.20, -72.35], [-37.80, -72.69]]
    VUELTA = [[-38.19995, -72.35005], [-38.49995, -72.45005], [-38.733, -72.604]]

    def test_una_parada_junto_a_la_carretera_queda_en_la_ida_y_no_en_el_regreso(self):
        linea = self.IDA + self.VUELTA
        victoria = (-38.1999, -72.3501)                     # el vértice de la vuelta está unos metros más cerca que el de la ida
        self.assertLess(rutas.km_entre(linea[4], victoria), rutas.km_entre(linea[2], victoria))
        self.assertEqual(rutas._indice_cercano(linea, victoria, 1), 2)

    def test_lo_que_falta_se_mide_por_la_ida_aunque_la_vuelta_pase_mas_cerca(self):
        ruta = {"puntos": self.IDA + self.VUELTA}
        camion = (-38.4999, -72.4501)                       # va hacia Angol, junto al vértice de regreso
        esperado = rutas.km_entre(camion, self.IDA[1]) + rutas.largo_km(self.IDA[1:])
        self.assertAlmostEqual(rutas.km_hasta(ruta, camion, 3), esperado, delta=0.5)
        self.assertGreater(rutas.km_hasta(ruta, camion, 3), rutas.km_entre(camion, self.IDA[3]))

    def test_al_salir_de_un_pueblo_por_donde_entro_lo_que_falta_no_crece(self):
        entrada, pueblo, salida, destino = [-38.50, -72.45], [-38.53, -72.42], [-38.5001, -72.4501], [-38.20, -72.35]
        ruta = {"puntos": [[-38.733, -72.604], entrada, pueblo, salida, destino]}
        camion = (-38.50001, -72.45001)                     # ya salió del pueblo, y el vértice por donde entró es el más cercano
        sin_limite = rutas.km_hasta(ruta, camion, 4)
        con_limite = rutas.km_hasta(ruta, camion, 4, desde=2)
        self.assertAlmostEqual(con_limite, rutas.km_entre(camion, salida) + rutas.km_entre(salida, destino), delta=0.1)
        self.assertLess(con_limite, sin_limite)

    @override_settings(OSRM_URL="http://osrm.prueba")
    def test_dos_paradas_en_la_misma_carretera_quedan_en_orden(self):
        lautaro, angol = (-38.5400, -72.4200), (-37.80, -72.69)
        ida = [[-72.604, -38.733], [-72.42, -38.54], [-72.35, -38.20], [-72.69, -37.80]]
        vuelta = [[-72.35005, -38.20005], [-72.42005, -38.54005], [-72.604, -38.733]]
        with patch("flota.rutas.urllib.request.urlopen", return_value=respuesta_osrm(ida + vuelta)):
            ruta = rutas.armar_ruta([(2, *angol), (1, *lautaro)])
        self.assertEqual([(p["direccion_id"], p["indice"]) for p in ruta["paradas"]], [(1, 1), (2, 3)])


class OsrmEnLaDemostracionTests(Base):
    @override_settings(OSRM_URL="http://osrm.prueba")
    def test_precalcula_una_vez_por_recorrido_y_lo_que_ya_esta_no_sale_a_la_red(self):
        with patch("flota.rutas.urllib.request.urlopen", return_value=respuesta_osrm([[-72.6, -38.7], [-72.5, -38.6]])) as pedido, patch("flota.rutas.time.sleep"):
            rutas.precalcular_demo()
            hechas = pedido.call_count
            self.assertGreaterEqual(hechas, len(regionales.HOSPITALES) + len(regionales.CORREDORES) - 1)
            rutas.precalcular_demo()
        self.assertEqual(pedido.call_count, hechas)

    @override_settings(OSRM_URL="http://osrm.prueba", OSRM_TIMEOUT_SEG=1)
    def test_si_osrm_esta_caido_no_espera_por_cada_direccion(self):
        import urllib.error
        with patch("flota.rutas.urllib.request.urlopen", side_effect=urllib.error.URLError("sin red")) as pedido:
            rutas.precalcular_demo()
        self.assertEqual(pedido.call_count, 2)                 # un recorrido con su reintento; el arranque no se queda esperando

    def test_sin_osrm_el_viaje_regional_sale_igual_con_rectas(self):
        orden, despacho = self.viaje_a_angol()
        self.assertTrue(despacho.ruta_aproximada)
        self.assertEqual(despacho.ruta_geojson["paradas"][0]["direccion_id"], orden.direccion_id)
        self.entrar()
        self.assertEqual(self.client.get("/flota/").status_code, 200)


class ControlDelTiempoTests(Base):
    def test_por_defecto_es_tiempo_normal_aunque_no_haya_fila(self):
        self.assertFalse(AjusteSimulador.objects.exists())
        self.assertEqual(tiempo.multiplicador(), 1)

    def test_un_administrador_lo_cambia_y_queda_en_la_base(self):
        self.entrar()
        r = self.client.post("/demo/tiempo/", {"multiplicador": "60"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["multiplicador"], 60)
        fila = AjusteSimulador.objects.get()
        self.assertEqual((fila.pk, fila.multiplicador_tiempo, fila.actualizado_por.username), (1, 60, "admin@cofrial.cl"))

    def test_solo_el_administrador(self):
        for usuario in ("despacho@cofrial.cl", "gerencia@cofrial.cl", "vendedora@cofrial.cl", ANGOL_USUARIO):
            self.entrar(usuario)
            self.assertEqual(self.client.post("/demo/tiempo/", {"multiplicador": "60"}).status_code, 403, usuario)
        self.assertEqual(tiempo.multiplicador(), 1)
        self.client.logout()
        self.assertNotEqual(self.client.post("/demo/tiempo/", {"multiplicador": "60"}).status_code, 200)
        self.assertEqual(tiempo.multiplicador(), 1)

    def test_rechaza_lo_que_no_esta_en_la_lista(self):
        self.entrar()
        for malo in ("0", "2", "61", "-5", "60.0", "abc", "", "1; DROP TABLE orden"):
            self.assertEqual(self.client.post("/demo/tiempo/", {"multiplicador": malo}).status_code, 400, malo)
        self.assertEqual(self.client.get("/demo/tiempo/").status_code, 405)
        self.assertEqual(tiempo.multiplicador(), 1)

    def test_la_base_tampoco_acepta_otro_valor_ni_otra_fila(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AjusteSimulador.objects.create(multiplicador_tiempo=7)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AjusteSimulador.objects.create(pk=2, multiplicador_tiempo=5)

    def test_limpiar_vuelve_a_1x(self):
        self.entrar()
        self.client.post("/demo/tiempo/", {"multiplicador": "20"})
        r = self.client.post("/demo/limpiar/", {"confirmar": "1"})
        self.assertEqual(r.json()["tiempo"]["multiplicador"], 1)
        self.assertEqual(tiempo.multiplicador(), 1)

    def test_la_pantalla_de_demo_muestra_el_control_y_su_estado_periodico(self):
        self.entrar()
        tiempo.cambiar(5)
        html = self.client.get("/demo/").content.decode()
        for m in tiempo.MULTIPLICADORES:
            self.assertIn(f'data-x="{m}"', html)
        self.assertEqual(self.client.get("/flota/escenarios/estado/").json()["tiempo"]["multiplicador"], 5)

    def test_el_aviso_se_ve_en_todas_las_pantallas_solo_si_esta_acelerado(self):
        self.entrar()
        self.assertRegex(self.client.get("/flota/").content.decode(), r'id="tiempo-acelerado"[^>]* hidden')
        tiempo.cambiar(60)
        for url in ("/flota/", "/demo/", "/crm/"):
            html = self.client.get(url).content.decode()
            self.assertNotRegex(html, r'id="tiempo-acelerado"[^>]* hidden', url)
            self.assertIn("60×", html)
        self.entrar(ANGOL_USUARIO)
        self.assertIn("Tiempo acelerado", self.client.get("/pedidos/").content.decode())
        self.assertEqual(self.client.get("/api/pedidos/").status_code, 200)

    def test_la_api_de_flota_informa_el_multiplicador_para_el_aviso_en_vivo(self):
        self.entrar()
        tiempo.cambiar(20)
        self.assertEqual(self.client.get("/api/flota/").json()["tiempo_x"], 20)

    def test_un_visitante_no_ve_el_aviso(self):
        tiempo.cambiar(60)
        self.assertNotIn("tiempo-acelerado", self.client.get("/").content.decode())


class LlegadaYAvisosAceleradosTests(Base):
    def posicion_a(self, despacho, km_antes):
        """Lectura del camión a `km_antes` de la parada, sobre la ruta guardada."""
        ruta = despacho.ruta_geojson
        p = ruta["puntos"][ruta["paradas"][0]["indice"]]
        lat = p[0] + km_antes / 111
        return Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=lat, long=p[1], combustible_pct=90, alerta_ruptura_frio=False)

    def test_la_hora_de_llegada_se_acorta_con_el_multiplicador(self):
        orden, _ = self.viaje_a_angol()
        normal = pedidos.seguimiento(orden)
        self.assertGreater(normal["km_restantes"], 100)
        self.assertGreater(normal["minutos"], 120)                 # más de dos horas a 50 km/h: una ETA que tiene sentido
        tiempo.cambiar(60)
        rapido = pedidos.seguimiento(orden)
        self.assertEqual(rapido["km_restantes"], normal["km_restantes"])
        self.assertAlmostEqual(rapido["minutos"], normal["minutos"] / 60, delta=1)
        self.assertEqual(rapido["tiempo_x"], 60)

    def test_lo_que_falta_se_mide_desde_la_ultima_parada_atendida(self):
        lautaro = Orden.objects.get(numero_oc="OC-REG-003")
        angol = Orden.objects.get(numero_oc="OC-REG-001")
        despacho = servicios.despachar("CAM-05", [lautaro.pk, angol.pk])
        ruta = despacho.ruta_geojson
        primera, segunda = (p["indice"] for p in ruta["paradas"])
        angol.refresh_from_db()
        self.assertEqual(pedidos._ultima_parada_atendida(angol, ruta, ruta["paradas"][1]), 0)
        pedidos.llegar_a_la_puerta([lautaro])
        self.assertEqual(pedidos._ultima_parada_atendida(angol, ruta, ruta["paradas"][1]), primera)
        self.assertLess(primera, segunda)

    def test_la_ventana_acelerada_es_de_minutos_y_contiene_la_hora_estimada(self):
        orden, _ = self.viaje_a_angol()
        tiempo.cambiar(60)
        s = pedidos.seguimiento(orden)
        desde, hasta = (timezone.datetime.fromisoformat(s["eta"][k]) for k in ("desde", "hasta"))
        self.assertEqual(hasta - desde, timedelta(minutes=2))
        centro = timezone.now() + timedelta(minutes=tiempo.minutos_de_viaje(s["km_restantes"], 60))
        self.assertLessEqual(desde, centro)
        self.assertGreaterEqual(hasta, centro)

    def test_a_velocidad_normal_la_ventana_sigue_igual(self):
        orden, _ = self.viaje_a_angol()
        s = pedidos.seguimiento(orden)
        desde, hasta = (timezone.datetime.fromisoformat(s["eta"][k]) for k in ("desde", "hasta"))
        self.assertGreaterEqual(hasta - desde, timedelta(minutes=15))
        self.assertEqual(s["cerca_km"], 2)

    def test_a_60x_el_aviso_de_que_esta_por_llegar_alcanza_a_verse(self):
        orden, despacho = self.viaje_a_angol()
        por_lectura = settings.VELOCIDAD_MEDIA_KMH * 60 * 5 / 3600
        self.assertGreater(tiempo.umbral_cerca_km(60), 3 * por_lectura)        # al menos tres lecturas dentro del radio
        self.assertEqual(tiempo.umbral_cerca_km(1), 2)
        self.assertEqual(tiempo.umbral_cerca_km(5), 2)
        self.posicion_a(despacho, 10)
        self.assertFalse(pedidos.seguimiento(orden)["cerca"])
        tiempo.cambiar(60)
        s = pedidos.seguimiento(orden)
        self.assertTrue(s["cerca"])
        cerca = [a for a in pedidos.avisos_de_llegada(orden.direccion.cliente) if a["tipo"] == "cerca"]
        self.assertEqual(len(cerca), 1)
        self.assertIn(f"a menos de {s['cerca_km']} km", cerca[0]["texto"])

    def test_el_plazo_del_cliente_no_se_acelera(self):
        orden, _ = self.viaje_a_angol()
        tiempo.cambiar(60)
        ahora = timezone.now()
        pedidos.llegar_a_la_puerta([orden], ahora)
        orden.refresh_from_db()
        self.assertGreater(pedidos.entrega_de(orden)["se_confirma_sola_en_seg"], settings.CONFIRMACION_AUTO_SEG - 5)
        self.assertEqual(pedidos.confirmar_vencidas(ahora + timedelta(seconds=settings.CONFIRMACION_AUTO_SEG - 1)), 0)
        self.assertEqual(pedidos.confirmar_vencidas(ahora + timedelta(seconds=settings.CONFIRMACION_AUTO_SEG + 1)), 1)

    def test_el_panel_informa_la_duracion_a_la_velocidad_actual(self):
        self.viaje_a_angol()
        self.entrar()
        normal = self.client.get("/flota/").context["mapa"]["viajes"]
        tiempo.cambiar(60)
        rapido = self.client.get("/flota/").context["mapa"]["viajes"]
        minutos = {v["camion"]: v["ruta"]["minutos"] for v in normal}
        self.assertLess(next(v["ruta"]["minutos"] for v in rapido if v["camion"] == "CAM-05"), minutos["CAM-05"] / 30)

    def test_el_seguimiento_del_cliente_entrega_el_tramo_a_su_comuna(self):
        orden, _ = self.viaje_a_angol()
        self.entrar(ANGOL_USUARIO)
        s = self.client.get(f"/api/pedidos/{orden.pk}/seguimiento/").json()
        self.assertTrue(s["mapa_en_vivo"])
        self.assertGreater(s["seguimiento"]["km_restantes"], 100)
        r = self.client.get(f"/api/pedidos/{orden.pk}/ruta/").json()
        self.assertEqual(r["puntos"][-1], [r["parada"]["lat"], r["parada"]["long"]])
