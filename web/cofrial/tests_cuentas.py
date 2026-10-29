"""Cuentas: recuperar la clave por correo y pedir una cuenta de empresa que ventas aprueba en el CRM."""
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from clientes.models import Cliente, Comuna, Vendedor
from crm.models import Interaccion

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
        r = self.client.get(url, follow=True)                      # Django cambia el token por una URL sin él (set-password)
        self.assertContains(r, "Elegir clave nueva")
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "ana-recupero-clave-61", "new_password2": "ana-recupero-clave-61"})
        self.assertRedirects(r, "/cuenta/recuperar/listo/")
        self.assertTrue(self.client.login(username="ana@correo.test", password="ana-recupero-clave-61"))
        self.assertFalse(self.client.login(username="ana@correo.test", password=CLAVE))
        self.client.logout()
        self.assertContains(self.client.get(url, follow=True), "<h1>El enlace ya no sirve</h1>", html=False)       # un solo uso

    def test_responde_igual_si_el_correo_no_existe_y_no_envia_nada(self):
        r = self.client.post("/cuenta/recuperar/", {"email": "nadie@nada.test"})
        self.assertRedirects(r, "/cuenta/recuperar/enviado/")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(CSRF_TRUSTED_ORIGINS=["http://54.10.20.30"])
    def test_el_enlace_usa_la_direccion_publica_y_no_el_host_del_pedido(self):
        self.client.post("/cuenta/recuperar/", {"email": "ana@correo.test"}, HTTP_HOST="sitio-falso.example")
        self.assertIn("http://54.10.20.30/cuenta/recuperar/", mail.outbox[0].body)
        self.assertNotIn("sitio-falso", mail.outbox[0].body)


class RegistroEmpresaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def datos(self, **cambios):
        return {"nombre": "Hotel Villarrica SpA", "rut": "77.123.456-9", "email": "Compras@HotelVillarrica.test", "telefono": "",
                "direccion": "Pedro de Valdivia 100", "comuna": Comuna.objects.get(nombre="Temuco").pk,
                "clave": "hotel-clave-larga-73", "clave2": "hotel-clave-larga-73", **cambios}

    def pedir(self):
        r = self.client.post("/cuenta/registro/empresa/", self.datos())
        self.assertContains(r, "Solicitud enviada")
        return Cliente.objects.get(rut="77.123.456-9")

    def test_la_solicitud_queda_inactiva_y_sin_vendedor_y_lo_explica_al_ingresar(self):
        self.assertContains(self.client.get("/cuenta/entrar/"), 'href="/cuenta/registro/empresa/"')
        c = self.pedir()
        self.assertEqual((c.tipo_cliente.codigo, c.vendedor, c.usuario.is_active, c.usuario.username), ("B2B", None, False, "compras@hotelvillarrica.test"))
        r = self.client.post("/cuenta/entrar/", {"username": "compras@hotelvillarrica.test", "password": "hotel-clave-larga-73"})
        self.assertContains(r, "aún no está activa")
        r = self.client.post("/cuenta/entrar/", {"username": "compras@hotelvillarrica.test", "password": "otra-clave-mala-1"})
        self.assertContains(r, "no coinciden")                       # sin la clave correcta no se revela que la cuenta existe
        self.client.post("/cuenta/recuperar/", {"email": "compras@hotelvillarrica.test"})
        self.assertEqual(len(mail.outbox), 0)                        # una cuenta pendiente no recupera clave

    def test_rut_o_correo_repetidos_se_rechazan(self):
        self.assertContains(self.client.post("/cuenta/registro/empresa/", self.datos(rut="12.345.678-5")), "Ya existe una cuenta con ese RUT")
        self.assertContains(self.client.post("/cuenta/registro/empresa/", self.datos(email="ana@correo.test")), "Ya existe una cuenta con ese correo")

    def test_la_vendedora_aprueba_y_queda_en_su_cartera(self):
        c = self.pedir()
        self.assertTrue(self.client.login(username="vendedora@cofrial.cl", password=CLAVE))
        r = self.client.get("/crm/solicitudes/")
        self.assertContains(r, "Hotel Villarrica SpA")
        self.assertContains(r, "Aprobar y asignármela")
        self.assertContains(self.client.get("/crm/"), 'aria-label="1 pendiente"')
        r = self.client.post(f"/crm/solicitudes/{c.pk}/aprobar/", follow=True)
        self.assertContains(r, "ya puede ingresar")
        self.assertContains(r, "No hay solicitudes pendientes")
        c.refresh_from_db()
        self.assertEqual(c.vendedor.usuario.username, "vendedora@cofrial.cl")
        self.assertTrue(c.usuario.is_active)
        self.assertTrue(Interaccion.objects.filter(cliente=c, detalle__contains="aprobada").exists())
        self.client.logout()
        self.assertTrue(self.client.login(username="compras@hotelvillarrica.test", password="hotel-clave-larga-73"))
        self.assertContains(self.client.get("/catalogo/"), 'class="perfil-b2b"')          # compra con el perfil institucional

    def test_gerencia_solo_mira_y_el_admin_elige_el_vendedor(self):
        c = self.pedir()
        self.assertTrue(self.client.login(username="gerencia@cofrial.cl", password=CLAVE))
        r = self.client.get("/crm/solicitudes/")
        self.assertContains(r, "Hotel Villarrica SpA")
        self.assertNotContains(r, "/aprobar/")
        self.assertContains(self.client.post(f"/crm/solicitudes/{c.pk}/aprobar/", follow=True), "solo puede revisar")
        self.client.logout()
        self.assertTrue(self.client.login(username="admin@cofrial.cl", password=CLAVE))
        self.assertContains(self.client.post(f"/crm/solicitudes/{c.pk}/aprobar/", follow=True), "Elige el vendedor")
        pedro = Vendedor.objects.get(usuario__username="vendedor2@cofrial.cl")
        self.client.post(f"/crm/solicitudes/{c.pk}/aprobar/", {"vendedor": pedro.pk})
        c.refresh_from_db()
        self.assertEqual((c.vendedor, c.usuario.is_active), (pedro, True))

    def test_rechazar_borra_la_solicitud_y_la_cuenta(self):
        c = self.pedir()
        self.assertTrue(self.client.login(username="vendedora@cofrial.cl", password=CLAVE))
        self.assertContains(self.client.post(f"/crm/solicitudes/{c.pk}/rechazar/", follow=True), "rechazada")
        self.assertFalse(Cliente.objects.filter(pk=c.pk).exists())
        self.assertFalse(get_user_model().objects.filter(username="compras@hotelvillarrica.test").exists())
        self.assertContains(self.client.post(f"/crm/solicitudes/{c.pk}/rechazar/", follow=True), "ya no está pendiente")
