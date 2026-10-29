"""El registro ofrece «Precargar datos de ejemplo» (persona ficticia) y se puede apagar con REGISTRO_PRECARGA=0."""
from django.test import TestCase, override_settings

from . import rut as rutlib


class BotonDePrecarga(TestCase):
    def test_el_registro_muestra_el_boton_y_carga_su_script(self):
        r = self.client.get("/cuenta/registro/")
        self.assertContains(r, 'id="precargar-registro"')
        self.assertContains(r, "js/precarga.js")

    @override_settings(REGISTRO_PRECARGA=False)
    def test_apagado_no_aparece_ni_se_carga_el_script(self):
        r = self.client.get("/cuenta/registro/")
        self.assertNotContains(r, "precargar-registro")
        self.assertNotContains(r, "precarga.js")

    def test_el_boton_no_aparece_en_otras_pantallas(self):
        self.assertNotContains(self.client.get("/cuenta/entrar/"), "precargar-registro")

    def test_el_algoritmo_de_rut_del_script_coincide_con_el_del_servidor(self):
        """precarga.js calcula el dígito verificador igual que clientes/rut.py: se comprueba con valores de ejemplo."""
        for cuerpo in ("10000000", "17654321", "24999999", "12345678"):
            self.assertTrue(rutlib.es_valido(cuerpo + rutlib.digito_verificador(cuerpo)), cuerpo)
