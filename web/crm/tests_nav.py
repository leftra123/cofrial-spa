"""Navegación del CRM: cinco entradas con ícono, y las subpestañas solo dentro de cada grupo."""
import re

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

from clientes.models import Cliente, TipoCliente
from crm.models import Prospecto

CLAVE = "demo-cofrial-2026"


def _nav(html, etiqueta):
    m = re.search(r'<nav class="subnav[^"]*" aria-label="' + etiqueta + r'[^"]*">(.*?)</nav>', html, re.S)
    return m.group(1) if m else ""


def _hrefs(nav):
    return re.findall(r'<a [^>]*href="(/[^"]*)"', nav)


class NavegacionCrm(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def html(self, url, usuario="vendedora@cofrial.cl"):
        c = Client()
        self.assertTrue(c.login(username=usuario, password=CLAVE))
        return c.get(url).content.decode()

    def test_comercial_ve_cinco_entradas(self):
        nav = _nav(self.html("/crm/"), "Secciones del CRM")
        self.assertEqual([h for h in _hrefs(nav) if h.startswith("/crm/")],
                         ["/crm/", "/crm/embudo/", "/crm/clientes/", "/crm/requerimientos/", "/crm/alertas/"])

    def test_cada_entrada_lleva_icono(self):
        nav = _nav(self.html("/crm/"), "Secciones del CRM")
        self.assertGreaterEqual(nav.count('class="ico"'), 5)

    def test_subpestanas_solo_dentro_del_grupo(self):
        self.assertEqual(_hrefs(_nav(self.html("/crm/cobranza/"), "Subsecciones")), ["/crm/clientes/", "/crm/solicitudes/", "/crm/cobranza/"])
        panel = self.html("/crm/")
        self.assertEqual(_nav(panel, "Subsecciones"), "")
        self.assertNotIn("/crm/cobranza/", _nav(panel, "Secciones del CRM"))

    def test_grupo_activo(self):
        pk = Prospecto.objects.first().pk
        for url, grupo in ((f"/crm/prospectos/{pk}/", "/crm/embudo/"), ("/crm/demanda/", "/crm/embudo/"), ("/crm/ia/", "/crm/requerimientos/"), ("/crm/solicitudes/", "/crm/clientes/")):
            nav = _nav(self.html(url), "Secciones del CRM")
            self.assertRegex(nav, r'<a href="' + grupo + r'" class="activo"', url)

    def test_subpestana_actual_marcada(self):
        sub = _nav(self.html("/crm/ia/"), "Subsecciones")
        self.assertRegex(sub, r'<a href="/crm/ia/" class="activo" aria-current="page"')

    def test_despachador_solo_ve_lo_suyo(self):
        html = self.html("/crm/alertas/", "despacho@cofrial.cl")
        self.assertEqual([h for h in _hrefs(_nav(html, "Secciones del CRM")) if h.startswith("/crm/")], ["/crm/demanda/", "/crm/alertas/"])
        self.assertEqual(_nav(html, "Subsecciones"), "")

    def test_contador_de_solicitudes_en_clientes(self):
        u = get_user_model().objects.create_user("nueva@empresa.test", password=CLAVE, is_active=False)
        Cliente.objects.create(usuario=u, tipo_cliente=TipoCliente.objects.get(codigo="B2B"), rut="76.086.428-5", nombre="Empresa Nueva", email="nueva@empresa.test")
        nav = _nav(self.html("/crm/"), "Secciones del CRM")
        self.assertRegex(nav, r'href="/crm/clientes/".*?class="chip alerta"')

    def test_sin_chip_de_rol(self):
        self.assertNotIn("Rol:", self.html("/crm/"))
