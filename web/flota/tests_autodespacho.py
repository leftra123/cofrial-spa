"""Panel sin los camiones guardados, camión propuesto y despacho sin personas."""
import re
import threading
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from catalogo.models import Producto
from clientes.models import Cliente
from crm import ia
from crm.tests import CLAVE
from flota import autodespacho, servicios, sugerencias
from flota.models import Camion, Despacho, Telemetria
from pedidos import servicios as pedidos
from pedidos.models import EstadoOrden, Orden
from pedidos.servicios import ErrorDeNegocio

REFRIGERADO, CONGELADO = "VAC-LOM-5K", "PES-FIL-3K"
HOSPITAL = "61.973.200-4"


def pedido(sku=REFRIGERADO, rut=HOSPITAL, minutos=0):
    cliente = Cliente.objects.get(rut=rut)
    pedidos.agregar(cliente, Producto.objects.get(sku=sku).pk, 1)
    orden = pedidos.generar_orden(cliente, cliente.direccion_set.first().pk, "OC-T")
    if minutos:
        Orden.objects.filter(pk=orden.pk).update(creada_en=timezone.now() - timedelta(minutes=minutos))
    return orden


def lectura(camion_id, combustible=80, alerta=False, temp=2.0, hace_seg=0):
    t = Telemetria.objects.create(camion_id=camion_id, temp_camara=temp, lat=-38.733, long=-72.604, combustible_pct=combustible, alerta_ruptura_frio=alerta)
    if hace_seg:
        Telemetria.objects.filter(pk=t.pk).update(registrado_en=timezone.now() - timedelta(seconds=hace_seg))
    return t


def limpiar_pedidos():
    for o in servicios.pedidos_por_despachar():
        o.delete()


def flota_al_dia():
    """Lecturas recientes y sanas para todos los camiones libres: lo que el simulador deja en operación normal."""
    for c in servicios.camiones_libres():
        lectura(c.camion_id, combustible=50)


class ConDemo(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario="despacho@cofrial.cl"):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))


class PanelSinGuardadosTests(ConDemo):
    def setUp(self):
        Telemetria.objects.all().delete()
        Despacho.objects.filter(regreso_en__isnull=True).update(llegada_en=timezone.now(), regreso_en=timezone.now())
        self.viaje = Despacho.objects.create(camion_id="CAM-04", programado_para=timezone.now(), salida_en=timezone.now())
        for c in ("CAM-03", "CAM-04", "CAM-05"):
            lectura(c)
        lectura("CAM-05", alerta=True, temp=9.0)
        self.entrar()

    def test_el_mapa_lleva_en_primer_plano_solo_a_los_que_importan(self):
        mapa = self.client.get("/flota/").context["mapa"]
        self.assertEqual({c["id"] for c in mapa["camiones"]}, {"CAM-04", "CAM-05"})         # en ruta y con alerta en la base
        self.assertIn("CAM-03", {c["id"] for c in mapa["en_base"]})
        self.assertNotIn("CAM-04", {c["id"] for c in mapa["en_base"]})

    def test_todas_las_fases_del_viaje_siguen_visibles(self):
        for fase in ("en_ruta", "en_la_puerta", "volviendo"):
            Despacho.objects.filter(pk=self.viaje.pk).update(fase=fase)
            self.assertIn("CAM-04", {c["id"] for c in self.client.get("/flota/").context["mapa"]["camiones"]}, fase)

    def test_los_50_camiones_siguen_en_la_pagina_y_el_contador_resume_los_guardados(self):
        r = self.client.get("/flota/")
        total = Camion.objects.count()
        self.assertEqual(total, 50)
        html = r.content.decode()
        self.assertEqual(len(re.findall(r"<article[^>]*data-camion=", html)), total)
        self.assertEqual(r.context["resumen"]["guardados"], total - 2)
        self.assertEqual(len(re.findall(r"<article[^>]*data-guardado", html)), total - 2)
        self.assertContains(r, f"Mostrar los {total - 2} en base")

    def test_la_api_sigue_entregando_toda_la_flota(self):
        self.assertEqual(len(self.client.get("/api/flota/").json()["camiones"]), 50)


class SinSenalTests(ConDemo):
    def setUp(self):
        Telemetria.objects.all().delete()
        lectura("CAM-03", hace_seg=servicios.SENAL_VIGENTE_SEG + 30)
        lectura("CAM-04")
        self.entrar()

    def test_el_panel_y_la_api_distinguen_al_camion_que_dejo_de_reportar(self):
        r = self.client.get("/flota/")
        self.assertEqual(r.context["resumen"]["sin_senal"], 1)
        tarjetas = {x["camion"].camion_id: x for x in r.context["tarjetas"]}
        self.assertTrue(tarjetas["CAM-03"]["sin_senal"])
        self.assertFalse(tarjetas["CAM-04"]["sin_senal"])
        self.assertFalse(tarjetas["CAM-05"]["sin_senal"])                  # nunca reportó: eso es «sin lecturas»
        camiones = {c["camion_id"]: c for c in self.client.get("/api/flota/").json()["camiones"]}
        self.assertTrue(camiones["CAM-03"]["sin_senal"])
        self.assertFalse(camiones["CAM-04"]["sin_senal"])


class CamionPropuestoTests(ConDemo):
    def setUp(self):
        Telemetria.objects.all().delete()

    def test_prefiere_el_de_mas_combustible_y_deja_al_final_el_que_tiene_poco(self):
        lectura("CAM-03", combustible=40)
        lectura("CAM-04", combustible=90)
        lectura("CAM-05", combustible=10)
        ids = [c["id"] for c in sugerencias.opciones_camion()]
        self.assertLess(ids.index("CAM-04"), ids.index("CAM-03"))
        self.assertLess(ids.index("CAM-03"), ids.index("CAM-05"))

    def test_no_propone_un_camion_con_ruptura_de_frio(self):
        lectura("CAM-04", combustible=99, alerta=True, temp=9.0)
        opcion = next(c for c in sugerencias.opciones_camion() if c["id"] == "CAM-04")
        self.assertFalse(opcion["apto"])
        orden = pedido()
        viajes, _ = sugerencias.calcular()
        self.assertNotEqual(next(v for v in viajes if orden.orden_id in [p["orden"] for p in v["pedidos"]])["camion"], "CAM-04")

    def test_la_pantalla_entrega_la_lista_ordenada_y_el_rango_de_cada_pedido(self):
        lectura("CAM-04", combustible=90)
        orden = pedido()
        self.entrar()
        r = self.client.get("/flota/despachar/")
        mapa = r.context["mapa"]
        self.assertEqual(mapa["camiones"][0]["id"], "CAM-04")
        self.assertEqual(mapa["rangos"][orden.orden_id], ["Refrigerado"])
        self.assertFalse(mapa["camion_fijado"])
        self.assertContains(r, 'id="aviso-camion"')

    def test_la_persona_puede_cambiar_el_camion_propuesto(self):
        lectura("CAM-04", combustible=90)
        orden = pedido()
        self.entrar()
        self.client.post("/flota/despachar/", {"camion": "CAM-03", "ordenes": [orden.orden_id]})
        orden.refresh_from_db()
        self.assertEqual(orden.despacho.camion_id, "CAM-03")
        self.assertIsNone(orden.despacho.decision_auto)                # lo armó una persona

    def test_una_preseleccion_queda_fijada(self):
        self.entrar()
        self.assertTrue(self.client.get("/flota/despachar/?camion=CAM-03").context["mapa"]["camion_fijado"])


class ReglasAutomaticasTests(ConDemo):
    def setUp(self):
        Telemetria.objects.all().delete()
        limpiar_pedidos()
        flota_al_dia()

    def _salen(self, **k):
        return autodespacho.planificar(**k)[0]

    def test_un_pedido_nuevo_espera_a_que_se_le_sumen_otros(self):
        pedido()
        salen, agrupando, _ = autodespacho.planificar()
        self.assertEqual(salen, [])
        self.assertEqual(agrupando[0]["sale_en_min"], autodespacho.ESPERA_MIN)

    def test_sale_cuando_el_mas_antiguo_llega_al_tope(self):
        pedido(minutos=6)
        pedido()
        (viaje,) = self._salen()
        self.assertEqual(len(viaje["pedidos"]), 2)                      # el nuevo se suma al mismo viaje
        self.assertIn("6 min", viaje["motivo"])

    def test_el_tope_se_configura(self):
        pedido(minutos=2)
        with patch.dict("os.environ", {"DESPACHO_AUTO_ESPERA_MIN": "2"}):
            self.assertEqual(len(self._salen()), 1)
        with patch.dict("os.environ", {"DESPACHO_AUTO_ESPERA_MIN": "no-es-numero"}):
            self.assertEqual(self._salen(), [])

    def test_sale_al_completar_seis_paradas_y_el_septimo_va_aparte(self):
        for _ in range(7):
            pedido()
        salen, agrupando, _ = autodespacho.planificar()
        self.assertEqual([len(v["pedidos"]) for v in salen], [6])
        self.assertEqual([len(v["pedidos"]) for v in agrupando], [1])

    def test_una_direccion_con_dos_rangos_sale_en_un_camion_de_dos_camaras(self):
        a, b = pedido(REFRIGERADO, minutos=9), pedido(CONGELADO, minutos=9)
        salen = self._salen()
        self.assertEqual(len(salen), 1)
        self.assertEqual({p["orden"] for p in salen[0]["pedidos"]}, {a.pk, b.pk})
        self.assertTrue(Camion.objects.get(pk=salen[0]["camion"]).dos_camaras)

    def test_un_viaje_lleva_un_solo_rango_y_un_camion_de_ese_rango(self):
        Camion.objects.filter(rango_secundario__isnull=False).update(activo=False)          # sin camiones de dos cámaras libres, cada rango va en el suyo
        pedido(REFRIGERADO, minutos=9)
        pedido(CONGELADO, minutos=9)
        salen = self._salen()
        self.assertEqual({v["rango"] for v in salen}, {"Refrigerado", "Congelado"})
        for v in salen:
            self.assertEqual(Camion.objects.get(pk=v["camion"]).rango_temperatura.nombre, v["rango"])

    def test_no_usa_camiones_con_alerta_sin_lecturas_recientes_o_con_poco_combustible(self):
        Telemetria.objects.all().delete()
        libres = [c for c in servicios.camiones_libres() if c.rango_temperatura.nombre == "Refrigerado"]
        lectura(libres[0].camion_id, alerta=True, temp=9.0)
        lectura(libres[1].camion_id, hace_seg=servicios.SENAL_VIGENTE_SEG + 30)
        lectura(libres[2].camion_id, combustible=servicios.COMBUSTIBLE_BAJO - 1)
        pedido(minutos=9)
        salen, _, resto = autodespacho.planificar()
        self.assertEqual(salen, [])
        self.assertEqual(resto["sin_camion"], [{"rango": "Refrigerado", "pedidos": 1}])
        lectura(libres[3].camion_id)
        self.assertEqual(self._salen()[0]["camion"], libres[3].camion_id)

    def test_no_saca_pedidos_sin_ubicar_y_dice_cuales(self):
        orden = pedido(minutos=9)
        orden.direccion.__class__.objects.filter(pk=orden.direccion_id).update(lat=None, long=None)
        salen, _, resto = autodespacho.planificar()
        self.assertEqual(salen, [])
        self.assertEqual(resto["sin_ubicar"], [orden.orden_id])

    def test_una_entrega_no_concretada_no_se_repite_sola(self):
        orden = pedido(minutos=9)
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entrega no concretada"))
        salen, _, resto = autodespacho.planificar()
        self.assertEqual(salen, [])
        self.assertEqual(resto["reprogramar"], [orden.orden_id])
        self.assertTrue(sugerencias.calcular()[0])                      # la sugerencia a una persona la sigue ofreciendo

    def test_agrupa_por_comuna_sin_sumar_camiones(self):
        COORDENADAS = {"Angol": (-37.80, -72.71), "Temuco": (-38.74, -72.59)}        # Temuco queda en el camino a Angol: va en el mismo camión
        comunas = ["Angol", "Temuco", "Angol", "Temuco", "Angol", "Temuco", "Angol", "Temuco"]
        filas = [type("O", (), {"orden_id": i, "direccion_id": i, "creada_en": timezone.now() - timedelta(minutes=20 - i), "estado_orden": type("E", (), {"nombre": "Recibida"}),
                                "direccion": type("D", (), {"lat": COORDENADAS[c][0], "long": COORDENADAS[c][1], "comuna": type("C", (), {"nombre": c})})}) for i, c in enumerate(comunas)]
        with patch("flota.sugerencias.servicios.pedidos_por_despachar", return_value=filas), patch("flota.sugerencias.servicios.rangos_de", return_value=["Refrigerado"]):
            viajes, _ = sugerencias.calcular()
        self.assertEqual([[p["comuna"] for p in v["pedidos"]] for v in viajes], [["Angol"] * 4 + ["Temuco"] * 2, ["Temuco"] * 2])


class EjecutarTests(ConDemo):
    def setUp(self):
        Telemetria.objects.all().delete()
        limpiar_pedidos()
        flota_al_dia()

    def test_despacha_con_la_misma_cadena_que_una_persona_y_guarda_el_porque(self):
        a, b = pedido(minutos=9), pedido()
        with patch("flota.autodespacho.ia.redactar", side_effect=ia.ErrorIA("sin clave")):
            r = autodespacho.ejecutar()
        (d,) = r["despachos"]
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual({a.despacho_id, b.despacho_id}, {d.despacho_id})
        self.assertEqual(a.estado_orden.nombre, "Despachada")
        self.assertTrue(a.documento_set.filter(tipo="guia_despacho").exists())          # RN-17: sale con su guía
        d.refresh_from_db()
        self.assertIn("9 min", d.decision_auto)
        self.assertIn(d.camion_id, d.decision_auto)
        self.assertIn(str(a.orden_id), d.decision_auto)
        self.assertIsNone(d.decision_ia)

    def test_la_ia_solo_redacta_y_no_ve_datos_personales(self):
        pedido(minutos=9)
        with patch("flota.autodespacho.ia.redactar", return_value="Salió por la espera del pedido.") as falso:
            (d,) = autodespacho.ejecutar()["despachos"]
        d.refresh_from_db()
        self.assertEqual(d.decision_ia, "Salió por la espera del pedido.")
        self.assertTrue(d.decision_auto)
        enviado = falso.call_args[0][0]
        self.assertNotIn("Hospital", enviado)
        self.assertNotIn("Manuel Montt", enviado)

    def test_si_la_ia_inventa_un_camion_queda_el_texto_del_sistema(self):
        pedido(minutos=9)
        with patch("flota.autodespacho.ia.redactar", return_value="Usé el CAM-99."):
            (d,) = autodespacho.ejecutar()["despachos"]
        d.refresh_from_db()
        self.assertIsNone(d.decision_ia)

    def test_la_ia_no_cambia_lo_que_se_decide(self):
        pedido(minutos=9)
        with patch("flota.autodespacho.ia.redactar", side_effect=ia.ErrorIA("caída")):
            esperado = autodespacho.planificar()[0][0]["camion"]
            self.assertEqual(autodespacho.ejecutar()["despachos"][0].camion_id, esperado)

    def test_tope_de_llamadas_a_la_ia_por_pasada(self):
        for _ in range(3):
            pedido(REFRIGERADO, minutos=9)
            pedido(CONGELADO, minutos=9)
        for _ in range(9):
            pedido(REFRIGERADO, minutos=9)
        with patch("flota.autodespacho.ia.redactar", return_value="Texto.") as falso:
            r = autodespacho.ejecutar()
        self.assertGreater(len(r["despachos"]), autodespacho.MAX_IA_POR_PASADA)
        self.assertEqual(falso.call_count, autodespacho.MAX_IA_POR_PASADA)

    def test_un_viaje_que_ya_no_se_puede_no_detiene_a_los_demas(self):
        Camion.objects.filter(rango_secundario__isnull=False).update(activo=False)
        pedido(REFRIGERADO, minutos=9)
        pedido(CONGELADO, minutos=9)
        real = servicios.despachar

        def falla_la_primera(camion, ordenes, decision=None):
            if not falla_la_primera.ya:
                falla_la_primera.ya = True
                raise ErrorDeNegocio("Ese camión no está disponible.")
            return real(camion, ordenes, decision=decision)
        falla_la_primera.ya = False
        with patch("flota.autodespacho.servicios.despachar", falla_la_primera), patch("flota.autodespacho.ia.redactar", side_effect=ia.ErrorIA("x")):
            r = autodespacho.ejecutar()
        self.assertEqual((len(r["despachos"]), len(r["omitidos"])), (1, 1))

    def test_repetir_la_pasada_no_duplica(self):
        pedido(minutos=9)
        with patch("flota.autodespacho.ia.redactar", side_effect=ia.ErrorIA("x")):
            self.assertEqual(len(autodespacho.ejecutar()["despachos"]), 1)
            self.assertEqual(autodespacho.ejecutar()["despachos"], [])

    def test_el_comando_de_una_pasada_informa(self):
        pedido(minutos=9)
        salida = StringIO()
        with patch("flota.autodespacho.ia.redactar", side_effect=ia.ErrorIA("x")):
            call_command("despachar_auto", stdout=salida)
        self.assertIn("1 despachos", salida.getvalue())

    def test_el_bucle_no_arranca_apagado(self):
        with patch.dict("os.environ", {"DESPACHO_AUTO": "0"}), self.assertRaises(CommandError):
            call_command("despachar_auto", "--bucle")


class PanelDespachoAutomaticoTests(ConDemo):
    def setUp(self):
        Telemetria.objects.all().delete()
        limpiar_pedidos()
        flota_al_dia()

    def test_viene_apagado_y_nada_sale_solo_por_abrir_las_pantallas(self):
        with patch.dict("os.environ"):
            __import__("os").environ.pop("DESPACHO_AUTO", None)
            self.assertFalse(autodespacho.activo())
            orden = pedido(minutos=99)
            self.entrar()
            r = self.client.get("/flota/")
            self.assertContains(r, "Apagado")
            self.assertContains(r, "DESPACHO_AUTO=1")
            self.client.get("/flota/despacho-auto/")
            self.client.get("/flota/despachar/")
        orden.refresh_from_db()
        self.assertIsNone(orden.despacho_id)

    def test_encendido_se_ve_y_explica_lo_que_espera(self):
        pedido()
        self.entrar()
        with patch.dict("os.environ", {"DESPACHO_AUTO": "1"}):
            r = self.client.get("/flota/")
        self.assertContains(r, "Encendido")
        self.assertContains(r, "se agrupa")
        self.assertContains(r, 'data-activo="1"')

    def test_muestra_la_decision_y_quien_la_redacto(self):
        pedido(minutos=9)
        with patch("flota.autodespacho.ia.redactar", return_value="Salió por la espera."):
            (d,) = autodespacho.ejecutar()["despachos"]
        self.entrar("gerencia@cofrial.cl")
        r = self.client.get("/flota/despacho-auto/")
        self.assertContains(r, f"Despacho N.º {d.despacho_id}")
        self.assertContains(r, "Salió por la espera.")
        self.assertContains(r, "Redactado por IA")

    def test_gerencia_ve_pero_no_corre_la_pasada(self):
        orden = pedido()
        self.entrar("gerencia@cofrial.cl")
        self.assertNotContains(self.client.get("/flota/"), "Correr una pasada ahora")
        self.assertEqual(self.client.post("/flota/despacho-auto/correr/", {"confirmar": "1"}).status_code, 403)
        self.entrar("ana@correo.test")
        self.assertEqual(self.client.get("/flota/despacho-auto/").status_code, 403)
        orden.refresh_from_db()
        self.assertIsNone(orden.despacho_id)

    def test_la_pasada_a_mano_exige_post_y_confirmacion(self):
        orden = pedido()
        self.entrar()
        self.assertEqual(self.client.get("/flota/despacho-auto/correr/").status_code, 405)
        self.client.post("/flota/despacho-auto/correr/", {})
        orden.refresh_from_db()
        self.assertIsNone(orden.despacho_id)

    def test_la_pasada_a_mano_no_espera_la_agrupacion_y_tiene_tope(self):
        for _ in range(autodespacho.MAX_VIAJES_A_MANO * sugerencias.MAX_PARADAS + 1):
            pedido()
        self.entrar()
        with patch("flota.autodespacho.ia.redactar", side_effect=ia.ErrorIA("x")):
            r = self.client.post("/flota/despacho-auto/correr/", {"confirmar": "1"})
        self.assertRedirects(r, "/flota/", fetch_redirect_response=False)
        self.assertEqual(Despacho.objects.filter(decision_auto__isnull=False).count(), autodespacho.MAX_VIAJES_A_MANO)
        self.assertEqual(servicios.pedidos_por_despachar().count(), 1)      # deja pedidos para el armado manual


class SinUbicarTests(ConDemo):
    def test_un_pedido_sin_ubicar_no_sale_ni_a_mano(self):
        orden = pedido()
        orden.direccion.__class__.objects.filter(pk=orden.direccion_id).update(lat=None, long=None)
        with self.assertRaises(ErrorDeNegocio) as e:
            servicios.despachar("CAM-03", [orden.orden_id])
        self.assertIn("no está ubicada", e.exception.mensajes[0])
        orden.refresh_from_db()
        self.assertIsNone(orden.despacho_id)


class DespachoSimultaneoTests(TransactionTestCase):
    """Una persona y el modo automático piden lo mismo a la vez: el segundo recibe el error de siempre."""

    def setUp(self):
        call_command("cargar_demo", verbosity=0)
        limpiar_pedidos()

    def _a_la_vez(self, pedidos_de):
        barrera, resultados = threading.Barrier(len(pedidos_de)), []

        def correr(camion, ordenes):
            try:
                barrera.wait()
                resultados.append(servicios.despachar(camion, ordenes))
            except ErrorDeNegocio:
                resultados.append(None)
            finally:
                connection.close()
        hilos = [threading.Thread(target=correr, args=p) for p in pedidos_de]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        return resultados

    def test_un_camion_no_toma_dos_viajes(self):
        a, b = pedido(), pedido()
        r = self._a_la_vez([("CAM-03", [a.orden_id]), ("CAM-03", [b.orden_id])])
        self.assertEqual(sum(1 for x in r if x), 1)
        self.assertEqual(Despacho.objects.filter(camion_id="CAM-03", regreso_en__isnull=True).count(), 1)

    def test_un_pedido_no_sale_en_dos_camiones(self):
        a = pedido()
        libres = [c.camion_id for c in servicios.camiones_libres() if c.rango_temperatura.nombre == "Refrigerado"][:2]
        r = self._a_la_vez([(libres[0], [a.orden_id]), (libres[1], [a.orden_id])])
        self.assertEqual(sum(1 for x in r if x), 1)
        self.assertEqual(Despacho.objects.filter(camion_id__in=libres, regreso_en__isnull=True).count(), 1)
