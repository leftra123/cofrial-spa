"""Semáforo de formularios (static/js/semaforo.js): el RUT se juzga igual en el navegador y en el servidor, y las dos plantillas base cargan
el script. Las reglas en JavaScript se prueban aparte, sin navegador:  node --test web/herramientas/pruebas-js/*.test.mjs  (usan estos mismos casos)."""
import json
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from clientes import rut

CASOS = json.loads((Path(__file__).parent / "rut_casos.json").read_text(encoding="utf-8"))
CLAVE = "demo-cofrial-2026"


class CasosDeRut(TestCase):
    def test_los_validos_lo_son_para_el_servidor(self):
        for caso in CASOS["validos"]:
            self.assertTrue(rut.es_valido(caso), caso)

    def test_los_invalidos_los_rechaza_el_servidor(self):
        for caso in CASOS["invalidos"]:
            self.assertFalse(rut.es_valido(caso), caso)

    def test_hay_casos_de_cada_verificador_especial(self):
        self.assertTrue(any(c.upper().endswith("K") for c in CASOS["validos"]))
        self.assertTrue(any(c.endswith("-0") for c in CASOS["validos"]))


class ElScriptSeCarga(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_en_la_tienda(self):
        for ruta in ("/cuenta/registro/", "/cuenta/registro/empresa/", "/cuenta/entrar/"):
            self.assertContains(self.client.get(ruta), "js/semaforo.js", msg_prefix=ruta)

    def test_en_las_pantallas_internas(self):
        self.client.login(username="admin@cofrial.cl", password=CLAVE)
        self.assertContains(self.client.get("/operacion/cuentas/nueva/"), "js/semaforo.js")

    def test_el_registro_marca_los_obligatorios(self):
        """El contador del semáforo cuenta los campos con `required`: el formulario debe seguir marcándolos."""
        html = self.client.get("/cuenta/registro/").content.decode()
        for campo in ("nombre", "rut", "email", "direccion", "clave", "clave2"):
            self.assertRegex(html, rf'name="{campo}"[^>]*\brequired\b', campo)
        self.assertNotRegex(html, r'name="telefono"[^>]*\brequired\b')
