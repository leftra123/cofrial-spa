from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from django.utils import timezone

from . import chequeos, servicios
from .models import ChequeoServicio

HTML = {"HTTP_ACCEPT": "text/html,application/xhtml+xml"}


def fila(servicio, minutos_atras, estado="ok", detalle="", ahora=None):
    ahora = ahora or timezone.now()
    return ChequeoServicio.objects.create(servicio=servicio, momento=ahora - timedelta(minutes=minutos_atras), estado=estado, ms=12, detalle=detalle)


class RespuestaDeSaludTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_sin_navegador_sigue_siendo_json_para_el_balanceador(self):
        self.assertEqual(self.client.get("/salud/").json(), {"estado": "ok"})
        self.assertEqual(self.client.get("/salud/", HTTP_ACCEPT="*/*").json(), {"estado": "ok"})

    def test_formato_json_se_puede_pedir_desde_el_navegador(self):
        self.assertEqual(self.client.get("/salud/?formato=json", **HTML).json(), {"estado": "ok"})

    def test_el_navegador_ve_la_pagina_aunque_no_haya_registros(self):
        r = self.client.get("/salud/", **HTML)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Estado del sistema")
        self.assertContains(r, "Todavía no hay registros")

    def test_la_pagina_es_publica_y_no_muestra_texto_ajeno(self):
        fila("base", 1)
        fila("gemini", 1, "caido", "credencial rechazada")
        r = self.client.get("/salud/", **HTML)
        self.assertContains(r, "Gemini (principal)")
        self.assertContains(r, "credencial rechazada")
        self.assertNotContains(r, "GEMINI_API_KEY")

    def test_sin_base_la_pagina_avisa_con_503_y_el_json_sigue_vivo(self):
        with mock.patch("salud.vistas.servicios.panel", side_effect=DatabaseError):
            self.assertEqual(self.client.get("/salud/", **HTML).status_code, 503)
        with mock.patch("salud.servicios.ChequeoServicio.objects", side_effect=DatabaseError):
            self.assertEqual(self.client.get("/salud/").status_code, 200)


class LecturaDelHistorialTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ahora = timezone.now()

    def _grupo(self, id_):
        return next(g for g in servicios.panel(self.ahora)["grupos"] if g["id"] == id_)

    def test_todo_operativo(self):
        for s in ("web", "base", "iot", "grafana"):
            fila(s, 0, ahora=self.ahora)
        d = servicios.panel(self.ahora)
        self.assertTrue(d["monitor_activo"])
        self.assertEqual(d["problemas"], [])
        self.assertEqual(self._grupo("datos")["estado"], "ok")
        self.assertEqual(self._grupo("datos")["barras"][-1]["estado"], "ok")
        self.assertEqual(self._grupo("datos")["barras"][0]["estado"], "sin")       # hace 90 días no había monitor

    def test_componente_sin_credencial_no_aparece(self):
        fila("base", 0, ahora=self.ahora)
        self.assertEqual([g["id"] for g in servicios.panel(self.ahora)["grupos"]], ["datos"])

    def test_ia_con_gemini_caido_y_groq_vivo_es_degradado_y_con_ambos_caidos_es_caida(self):
        fila("gemini", 0, "caido", ahora=self.ahora)
        fila("groq", 0, ahora=self.ahora)
        self.assertEqual(self._grupo("ia")["estado"], "degradado")
        cache.clear()
        fila("groq", 0, "caido", ahora=self.ahora)
        self.assertEqual(self._grupo("ia")["estado"], "caido")

    def test_un_dia_con_pocas_fallas_es_amarillo_y_con_muchas_es_rojo(self):
        for i in range(100):
            fila("base", i / 100, "caido" if i < 2 else "ok", ahora=self.ahora)
        self.assertEqual(self._grupo("datos")["barras"][-1]["estado"], "degradado")
        ChequeoServicio.objects.all().delete()
        cache.clear()
        for i in range(100):
            fila("base", i / 100, "caido" if i < 10 else "ok", ahora=self.ahora)
        self.assertEqual(self._grupo("datos")["barras"][-1]["estado"], "caido")

    def test_la_disponibilidad_cuenta_solo_lo_observado(self):
        for i in range(4):
            fila("base", i, "caido" if i == 0 else "ok", ahora=self.ahora)
        self.assertEqual(self._grupo("datos")["disponibilidad"], 0.75)

    def test_monitor_detenido_se_ve_como_sin_registros_no_como_caida(self):
        fila("base", 120, ahora=self.ahora)
        d = servicios.panel(self.ahora)
        self.assertFalse(d["monitor_activo"])
        self.assertEqual(self._grupo("datos")["estado"], "sin")
        self.assertEqual(d["incidentes"][0]["servicio"], "_hueco")

    def test_incidente_agrupa_revisiones_seguidas_y_dice_cuanto_duro(self):
        for m in range(30, 20, -1):
            fila("base", m, ahora=self.ahora)
        for m in range(20, 15, -1):
            fila("base", m, "caido", "no responde", ahora=self.ahora)
        for m in range(15, -1, -1):
            fila("base", m, ahora=self.ahora)
        inc = [i for i in servicios.panel(self.ahora)["incidentes"] if i["servicio"] == "base"]
        self.assertEqual(len(inc), 1)
        self.assertEqual(inc[0]["estado"], "caido")
        self.assertEqual(inc[0]["minutos"], 5)
        self.assertFalse(inc[0]["en_curso"])

    def test_hueco_entre_dos_revisiones_distantes_se_informa(self):
        fila("base", 300, ahora=self.ahora)
        fila("base", 1, ahora=self.ahora)
        self.assertTrue(any(i["servicio"] == "_hueco" and i["minutos"] > 200 for i in servicios.panel(self.ahora)["incidentes"]))


class RondaTests(TestCase):
    def setUp(self):
        cache.clear()

    def _con(self, **resultados):
        falsas = {k: (lambda r=r: r) for k, r in resultados.items()}
        return mock.patch.dict(chequeos.REVISIONES, falsas, clear=True)

    def test_guarda_lo_que_revisa_y_omite_lo_no_configurado(self):
        with self._con(base=("ok", 5, ""), gemini=None):
            n = servicios.ejecutar_ronda([])
        self.assertEqual(n, 1)
        self.assertEqual(list(ChequeoServicio.objects.values_list("servicio", flat=True)), ["base"])

    def test_no_repite_una_revision_externa_antes_de_tiempo(self):
        with self._con(groq=("ok", 5, "")):
            servicios.ejecutar_ronda([])
            self.assertEqual(servicios.ejecutar_ronda([]), 0)
        self.assertEqual(ChequeoServicio.objects.count(), 1)

    def test_una_revision_que_explota_queda_como_caida_y_no_tumba_a_las_demas(self):
        def mala():
            raise RuntimeError("x")
        with mock.patch.dict(chequeos.REVISIONES, {"web": mala, "base": lambda: ("ok", 1, "")}, clear=True):
            servicios.ejecutar_ronda([])
        self.assertEqual(ChequeoServicio.objects.get(servicio="web").estado, "caido")
        self.assertEqual(ChequeoServicio.objects.get(servicio="base").estado, "ok")

    def test_si_la_base_no_guarda_las_filas_quedan_pendientes_con_su_hora(self):
        pendientes = []
        with self._con(base=("caido", 5, "no responde")), mock.patch("salud.servicios.ChequeoServicio.objects.bulk_create", side_effect=DatabaseError):
            servicios.ejecutar_ronda(pendientes)
        self.assertEqual(len(pendientes), 1)
        servicios.guardar(pendientes)
        self.assertEqual(pendientes, [])
        self.assertEqual(ChequeoServicio.objects.get().detalle, "no responde")

    def test_poda_lo_muy_antiguo(self):
        ahora = timezone.now()
        fila("base", 60 * 24 * 101, ahora=ahora)
        fila("base", 1, ahora=ahora)
        self.assertEqual(servicios.podar(ahora), 1)
        self.assertEqual(ChequeoServicio.objects.count(), 1)

    def test_el_comando_hace_una_ronda(self):
        with self._con(base=("ok", 5, "")):
            call_command("vigilar")
        self.assertEqual(ChequeoServicio.objects.count(), 1)


class ChequeosTests(TestCase):
    def test_codigos_http(self):
        self.assertEqual(chequeos._por_codigo(200, 50, "")[0], "ok")
        self.assertEqual(chequeos._por_codigo(200, 9000, "")[0], "degradado")
        self.assertEqual(chequeos._por_codigo(429, 50, "")[0], "degradado")
        self.assertEqual(chequeos._por_codigo(401, 50, ""), ("caido", 50, "credencial rechazada"))
        self.assertEqual(chequeos._por_codigo(503, 50, "")[2], "HTTP 503")
        self.assertEqual(chequeos._por_codigo(None, 50, "sin conexión")[0], "caido")

    def test_sin_credencial_no_se_revisa(self):
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "", "GROQ_API_KEY": ""}), self.settings(MERCADOPAGO_ACCESS_TOKEN=""):
            self.assertIsNone(chequeos.gemini())
            self.assertIsNone(chequeos.groq())
            self.assertIsNone(chequeos.mercadopago())

    def test_la_base_responde(self):
        self.assertEqual(chequeos.base()[0], "ok")

    def test_iot_sin_lecturas_es_caida_y_con_lectura_reciente_es_ok(self):
        self.assertEqual(chequeos.iot()[:3:2], ("caido", "sin lecturas"))
        from flota.models import Camion, Telemetria
        from catalogo.models import RangoTemperatura
        rango = RangoTemperatura.objects.first() or RangoTemperatura.objects.create(nombre="x", temp_min_c=0, temp_max_c=4)
        cam = Camion.objects.create(camion_id="T-1", patente="TT0001", capacidad_kg=1, rango_temperatura=rango)
        Telemetria.objects.create(camion=cam, temp_camara=2, lat=0, long=0, combustible_pct=50, alerta_ruptura_frio=False)
        self.assertEqual(chequeos.iot()[0], "ok")

    def test_una_falla_de_red_es_caida_con_frase_fija(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("secreto-del-proxy")):
            codigo, ms, falla = chequeos._http("http://x.test/")
        self.assertEqual((codigo, falla), (None, "sin conexión"))


class PeriodosTests(TestCase):
    """El historial se puede mirar por período: hasta 3 días con una barra por hora, desde 7 con una por día."""

    def setUp(self):
        cache.clear()
        self.ahora = timezone.now()

    def _datos(self, ventana):
        return next(g for g in servicios.panel(self.ahora, ventana)["grupos"] if g["id"] == "datos")

    def test_cuantas_barras_trae_cada_periodo(self):
        fila("base", 0, ahora=self.ahora)
        self.assertEqual({v: len(self._datos(v)["barras"]) for v in servicios.VENTANAS}, {"24h": 24, "3d": 72, "7d": 7, "30d": 30, "90d": 90})
        self.assertEqual(self._datos("3d")["barras"][-1]["estado"], "ok")          # la última barra es la hora en curso

    def test_el_porcentaje_es_del_periodo_elegido(self):
        fila("base", 0, ahora=self.ahora)
        fila("base", 30 * 60, "caido", ahora=self.ahora)                               # hace 30 horas: fuera de 24 h, dentro de 3 días
        self.assertEqual(self._datos("24h")["disponibilidad"], 1)
        self.assertEqual(self._datos("3d")["disponibilidad"], 0.5)
        self.assertEqual(self._datos("90d")["disponibilidad"], 0.5)

    def test_una_caida_antigua_no_ensucia_las_barras_de_un_periodo_corto(self):
        fila("base", 0, ahora=self.ahora)
        fila("base", 5 * 24 * 60, "caido", ahora=self.ahora)                           # hace 5 días
        self.assertNotIn("caido", [b["estado"] for b in self._datos("3d")["barras"]])
        self.assertIn("caido", [b["estado"] for b in self._datos("7d")["barras"]])

    def test_un_componente_sin_filas_en_el_periodo_sigue_a_la_vista(self):
        fila("base", 10 * 24 * 60, ahora=self.ahora)                                   # el laboratorio lleva 10 días apagado
        g = self._datos("3d")
        self.assertEqual({b["estado"] for b in g["barras"]}, {"sin"})
        self.assertIsNone(g["disponibilidad"])                                         # ni caída ni éxito: no hay nada que promediar

    def test_los_incidentes_siguen_al_periodo_con_tope_de_siete_dias(self):
        fila("base", 0, ahora=self.ahora)
        fila("base", 5 * 24 * 60, "caido", "HTTP 503", ahora=self.ahora)
        caidas = lambda v: [i for i in servicios.panel(self.ahora, v)["incidentes"] if i["estado"] == "caido"]
        self.assertEqual(len(caidas("3d")), 0)
        self.assertEqual(len(caidas("7d")), 1)
        self.assertEqual(servicios.panel(self.ahora, "90d")["dias_incidentes"], 7)
        self.assertEqual(servicios.panel(self.ahora, "24h")["dias_incidentes"], 1)

    def test_un_periodo_desconocido_cae_en_el_inicial(self):
        fila("base", 0, ahora=self.ahora)
        self.assertEqual(servicios.panel(self.ahora, "<script>")["ventana"], servicios.VENTANA_INICIAL)

    def test_la_pagina_abre_en_tres_dias_y_ofrece_los_demas(self):
        fila("base", 0)
        r = self.client.get("/salud/", **HTML)
        self.assertContains(r, 'href="?ventana=3d" class="activa" aria-current="true"')
        for clave in servicios.VENTANAS:
            self.assertContains(r, f'href="?ventana={clave}"')
        self.assertContains(r, "Últimos 3 días · cada barra es una hora")
        self.assertContains(r, 'id="s-actualizar" href="?ventana=3d"')
        self.assertContains(r, "js/salud.js")

    def test_la_pagina_respeta_el_periodo_pedido(self):
        fila("base", 0)
        r = self.client.get("/salud/?ventana=90d", **HTML)
        self.assertContains(r, 'href="?ventana=90d" class="activa" aria-current="true"')
        self.assertContains(r, "Últimos 90 días · cada barra es un día")
        self.assertContains(r, "Últimas 24 horas · cada barra es una hora")          # el detalle por hora solo acompaña a los períodos por día
        r = self.client.get("/salud/?ventana=24h", **HTML)
        self.assertContains(r, "Últimas 24 horas · cada barra es una hora", count=1)
        self.assertContains(self.client.get("/salud/?ventana=no-existe", **HTML), 'href="?ventana=3d" class="activa"')

    def test_el_balanceador_sigue_recibiendo_json_con_cualquier_periodo(self):
        self.assertEqual(self.client.get("/salud/?ventana=7d").json(), {"estado": "ok"})
