"""Cuentas: recuperar la clave por correo."""
import re

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

CLAVE = "demo-cofrial-2026"


def enlace(correo):
    return re.search(r"https?://[^/\s]+(/cuenta/recuperar/[^\s]+/)", correo.body).group(1)


class RecuperarClaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_el_enlace_del_correo_cambia_la_clave_una_sola_vez(self):
        self.assertContains(self.client.get("/cuenta/entrar/"), 'href="/cuenta/recuperar/"')
        r = self.client.post("/cuenta/recuperar/", {"email": "ana@correo.test"})
        self.assertRedirects(r, "/cuenta/recuperar/enviado/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@correo.test"])
        url = enlace(mail.outbox[0])
        r = self.client.get(url, follow=True)
        self.assertContains(r, "Elegir clave nueva")
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "ana-recupero-clave-61", "new_password2": "ana-recupero-clave-61"})
        self.assertRedirects(r, "/cuenta/recuperar/listo/")
        self.assertTrue(self.client.login(username="ana@correo.test", password="ana-recupero-clave-61"))
        self.assertFalse(self.client.login(username="ana@correo.test", password=CLAVE))
        self.client.logout()
        self.assertContains(self.client.get(url, follow=True), "<h1>El enlace ya no sirve</h1>", html=False)

    def test_responde_igual_si_el_correo_no_existe_y_no_envia_nada(self):
        r = self.client.post("/cuenta/recuperar/", {"email": "nadie@nada.test"})
        self.assertRedirects(r, "/cuenta/recuperar/enviado/")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(CSRF_TRUSTED_ORIGINS=["http://54.10.20.30"])
    def test_el_enlace_usa_la_direccion_publica_y_no_el_host_del_pedido(self):
        self.client.post("/cuenta/recuperar/", {"email": "ana@correo.test"}, HTTP_HOST="sitio-falso.example")
        self.assertIn("http://54.10.20.30/cuenta/recuperar/", mail.outbox[0].body)
        self.assertNotIn("sitio-falso", mail.outbox[0].body)
