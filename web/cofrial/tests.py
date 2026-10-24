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
