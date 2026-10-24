import logging
from io import StringIO

from django.conf import settings
from django.template.loader import render_to_string
from django.test import TestCase


class EstabilidadTests(TestCase):
    def test_conexiones_persistentes_se_comprueban_antes_de_reutilizarse(self):
        bd = settings.DATABASES["default"]
        self.assertEqual(bd["CONN_MAX_AGE"], 60)
        self.assertTrue(bd["CONN_HEALTH_CHECKS"])

    def test_los_errores_500_llegan_a_la_salida_estandar(self):
        """Con DEBUG apagado Django no imprimía los 500 y `docker logs` no mostraba el traceback."""
        self.assertEqual(settings.LOGGING["loggers"]["django.request"]["handlers"], ["consola"])
        flujo = StringIO()
        manejador = logging.getLogger("django.request").handlers[0]
        original, manejador.stream = manejador.stream, flujo
        try:
            logging.getLogger("django.request").error("Internal Server Error: /prueba/")
        finally:
            manejador.stream = original
        self.assertIn("Internal Server Error: /prueba/", flujo.getvalue())

    def test_pagina_500_no_toca_la_base_ni_extiende_plantillas(self):
        """Si la causa del 500 es la base de datos, la página de error no debe volver a fallar por consultarla."""
        with self.assertNumQueries(0):
            html = render_to_string("500.html")
        self.assertIn("Tuvimos un problema", html)
        self.assertNotIn("{%", html)

    def test_un_error_real_muestra_la_pagina_propia_y_queda_en_el_registro(self):
        from unittest.mock import patch
        self.client.raise_request_exception = False
        with patch("catalogo.views._precios", side_effect=RuntimeError("falla simulada")), self.assertLogs("django.request", level="ERROR") as registro:
            r = self.client.get("/catalogo/")
        self.assertEqual(r.status_code, 500)
        self.assertContains(r, "Tuvimos un problema", status_code=500)
        self.assertTrue(any("falla simulada" in linea or "Internal Server Error" in linea for linea in registro.output))


class MarcaTests(TestCase):
    """La marca oficial (logo horizontal, icono de la aplicación, favicons y camiones) y nada del logo anterior."""

    def test_la_tienda_usa_los_archivos_de_marca(self):
        html = self.client.get("/").content.decode()
        self.assertIn("img/marca/logo-horizontal-900", html)
        self.assertIn("img/marca/favicon-32", html)
        self.assertIn("img/marca/favicon-180", html)
        self.assertNotIn("cofrial-logo", html)

    def test_el_panel_usa_el_icono_de_la_aplicacion(self):
        from django.core.management import call_command
        call_command("cargar_demo", verbosity=0)
        self.client.login(username="despacho@cofrial.cl", password="demo-cofrial-2026")
        self.assertIn("img/marca/icono-app", self.client.get("/flota/").content.decode())

    def test_los_archivos_existen_y_la_insignia_no_trae_el_texto_de_inacap(self):
        from pathlib import Path

        import struct
        base = Path(__file__).resolve().parent.parent / "static" / "img" / "marca"
        for nombre in ("logo-horizontal-900.png", "icono-app.png", "favicon-32.png", "favicon-180.png", "camion-mapa.png", "camion-alerta.png", "insignia-vertical.png"):
            self.assertTrue((base / nombre).exists(), nombre)
        ancho, alto = struct.unpack(">II", (base / "insignia-vertical.png").read_bytes()[16:24])      # tamaño leído del encabezado PNG
        self.assertAlmostEqual(alto / ancho, 1300 / 1600, places=2)          # recortada: sin la línea «INACAP Temuco - EVA2_3...»


class VelocidadCompartidaWebTests(TestCase):
    """La hora de llegada de la tienda usa las mismas variables que el simulador IoT (VELOCIDAD_MEDIA_KMH y FACTOR_CALLES)."""

    def test_valores_por_defecto(self):
        self.assertEqual(settings.VELOCIDAD_MEDIA_KMH, 50)
        self.assertEqual(settings.FACTOR_CALLES, 1.3)

    def test_la_llegada_estimada_depende_de_la_velocidad_configurada(self):
        from types import SimpleNamespace

        from django.core.management import call_command
        from django.test import override_settings
        from django.utils import timezone

        from pedidos import servicios
        from pedidos.models import Orden
        call_command("cargar_demo", verbosity=0)
        orden = Orden.objects.select_related("despacho", "direccion").get(numero_oc="OC-2026-0457")
        # un camión a ~4 km de la dirección, con lectura de este mismo instante
        ultima = SimpleNamespace(lat=orden.direccion.lat - 0.036, long=orden.direccion.long, registrado_en=timezone.now())
        with override_settings(VELOCIDAD_MEDIA_KMH=10):
            lento = servicios._llegada(orden, ultima)
        with override_settings(VELOCIDAD_MEDIA_KMH=100):
            rapido = servicios._llegada(orden, ultima)
        self.assertEqual(lento["km_restantes"], rapido["km_restantes"])       # la distancia no cambia, solo la hora
        self.assertGreater(lento["eta"]["hasta"], rapido["eta"]["hasta"])
