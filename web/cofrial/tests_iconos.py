"""Íconos de la navegación (generados desde react-icons) y que ninguna pantalla mande al admin de Django."""
import json
from pathlib import Path

from django.core.management import call_command
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase

import catalogo

CLAVE = "demo-cofrial-2026"


class Icono(SimpleTestCase):
    def pintar(self, texto):
        return Template("{% load iconos %}" + texto).render(Context())

    def test_pinta_svg_oculto_al_lector(self):
        html = self.pintar('{% icono "camion" %}')
        self.assertIn("<svg", html)
        self.assertIn('aria-hidden="true"', html)
        self.assertIn('class="ico"', html)

    def test_acepta_una_clase_extra(self):
        self.assertIn('class="ico grande"', self.pintar('{% icono "camion" "grande" %}'))

    def test_nombre_desconocido_falla(self):
        with self.assertRaises(KeyError):
            self.pintar('{% icono "no-existe" %}')

    def test_todos_los_iconos_tienen_contenido(self):
        iconos = json.loads((Path(catalogo.__file__).parent / "iconos.json").read_text(encoding="utf-8"))
        self.assertGreater(len(iconos), 30)
        for nombre, trazos in iconos.items():
            self.assertIn("<", trazos, nombre)


class SinDjangoALaVista(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_ninguna_pantalla_enlaza_a_django(self):
        self.client.login(username="admin@cofrial.cl", password=CLAVE)
        for url in ("/crm/", "/flota/", "/operacion/", "/operacion/cuentas/"):
            self.assertNotContains(self.client.get(url), 'href="/admin/', msg_prefix=url)

    def test_la_ruta_sigue_de_respaldo(self):
        self.client.login(username="admin@cofrial.cl", password=CLAVE)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
