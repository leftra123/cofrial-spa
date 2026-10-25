"""Seguridad de /avisos/ y de /admin/: sin redirección abierta, sin rebote al login con sesión abierta y admin de Django solo para el superusuario."""
from django.core.management import call_command
from django.test import TestCase

CLAVE = "demo-cofrial-2026"


class AvisosYAdmin(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario):
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def test_volver_no_permite_salir_del_sitio(self):
        self.entrar("ana@correo.test")
        for malo in ("//evil.example/x", "/\\evil.example", "/\\\\evil.example", "https://evil.example/", "javascript:alert(1)", "evil.example"):
            r = self.client.post("/avisos/pedir/", {"producto": 1, "cantidad": 1, "volver": malo})
            self.assertEqual(r["Location"], "/avisos/", malo)
        r = self.client.post("/avisos/pedir/", {"producto": 1, "cantidad": 1, "volver": "/catalogo/1/"})
        self.assertEqual(r["Location"], "/catalogo/1/")

    def test_el_equipo_no_rebota_al_login_desde_avisos(self):
        for usuario, destino in (("vendedora@cofrial.cl", "/crm/"), ("gerencia@cofrial.cl", "/crm/"), ("despacho@cofrial.cl", "/crm/"), ("admin@cofrial.cl", "/crm/")):
            self.client.logout()
            self.entrar(usuario)
            r = self.client.get("/avisos/")
            self.assertEqual(r["Location"], destino, usuario)
        self.client.logout()
        self.assertEqual(self.client.get("/avisos/")["Location"], "/cuenta/entrar/?next=/avisos/")       # el visitante sí va al login

    def test_el_admin_de_django_es_solo_del_superusuario(self):
        for usuario in ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl", "ana@correo.test"):
            self.client.logout()
            self.entrar(usuario)
            r = self.client.get("/admin/")
            self.assertEqual(r.status_code, 302, usuario)
            self.assertIn("/admin/login/", r["Location"], usuario)
        self.client.logout()
        self.entrar("admin@cofrial.cl")
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_el_menu_no_muestra_administracion_al_equipo(self):
        self.entrar("vendedora@cofrial.cl")
        self.assertNotIn('href="/admin/"', self.client.get("/crm/").content.decode())
        self.client.logout()
        self.entrar("admin@cofrial.cl")
        self.assertIn('href="/admin/"', self.client.get("/crm/").content.decode())
