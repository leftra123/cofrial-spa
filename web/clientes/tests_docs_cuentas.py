"""Los documentos de cuentas no deben contradecir al sistema: RUT de ejemplo válidos y todas las cuentas demo listadas (revisión del 8-nov-2026).
Leen docs/ junto a web/ (en la imagen de Docker no está: ahí se saltan)."""
import re
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from clientes import cuentas_demo, rut

DOCS = Path(settings.BASE_DIR).parent / "docs"


@unittest.skipUnless((DOCS / "credenciales-y-cuentas.md").exists(), "docs/ no está junto a web/")
class DocumentosDeCuentasTests(SimpleTestCase):
    def test_los_rut_de_los_ejemplos_son_validos(self):
        texto = (DOCS / "credenciales-y-cuentas.md").read_text(encoding="utf-8")
        encontrados = re.findall(r"--rut ([\d.]+-[\dkK])", texto)
        self.assertTrue(encontrados)
        for valor in encontrados:
            self.assertTrue(rut.es_valido(valor), f"El RUT de ejemplo {valor} no tiene dígito verificador válido: el formulario web lo rechaza")

    def test_todas_las_cuentas_demo_estan_documentadas(self):
        for archivo in ("credenciales-y-cuentas.md", "cuentas-y-permisos.md"):
            texto = (DOCS / archivo).read_text(encoding="utf-8")
            faltan = [usuario for usuario, _perfil, _muestra in cuentas_demo.CUENTAS if usuario not in texto]
            self.assertEqual(faltan, [], f"{archivo} no menciona estas cuentas demo")
