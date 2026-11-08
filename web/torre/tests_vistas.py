"""Rutas, permisos, menú e inicio de la Torre de control."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase

from torre import servicios
from torre.vistas import ROTULO

CLAVE = "demo-cofrial-2026"
CUENTAS = {"vendedor": "vendedora@cofrial.cl", "gerencia": "gerencia@cofrial.cl", "despachador": "despacho@cofrial.cl", "admin": "admin@cofrial.cl",
           "B2B": "abastecimiento@hospital.test", "B2C": "ana@correo.test"}


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        cache.clear()

    def como(self, rol):
        c = Client()
        self.assertTrue(c.login(username=CUENTAS[rol], password=CLAVE), rol)
        return c


class Permisos(Base):
    def test_permisos(self):
        for url in ("/torre/", "/torre/pulso/"):
            for rol in ("gerencia", "admin"):
                self.assertEqual(self.como(rol).get(url).status_code, 200, f"{rol} {url}")
            for rol in ("vendedor", "despachador", "B2B", "B2C"):
                self.assertEqual(self.como(rol).get(url).status_code, 403, f"{rol} {url}")
            r = Client().get(url)
            self.assertEqual(r.status_code, 302)
            self.assertIn("/cuenta/entrar/", r["Location"])

    def test_post_405(self):
        for url in ("/torre/", "/torre/pulso/"):
            self.assertEqual(Client().post(url).status_code, 405)
            self.assertEqual(self.como("gerencia").post(url).status_code, 405)


class InicioYMenu(Base):
    def test_gerencia_inicia_en_torre(self):
        r = Client().post("/cuenta/entrar/", {"username": CUENTAS["gerencia"], "password": CLAVE})
        self.assertRedirects(r, "/torre/", fetch_redirect_response=False)

    def test_admin_sigue_en_crm(self):
        r = Client().post("/cuenta/entrar/", {"username": CUENTAS["admin"], "password": CLAVE})
        self.assertRedirects(r, "/crm/", fetch_redirect_response=False)

    def test_anonimo_que_pide_la_torre_vuelve_a_ella_tras_entrar(self):
        r = Client().post("/cuenta/entrar/?next=/torre/", {"username": CUENTAS["gerencia"], "password": CLAVE})
        self.assertRedirects(r, "/torre/", fetch_redirect_response=False)

    def test_menu(self):
        self.assertIn('href="/torre/"', self.como("gerencia").get("/crm/").content.decode())
        self.assertIn('href="/torre/"', self.como("admin").get("/crm/").content.decode())
        for rol in ("vendedor", "despachador"):
            self.assertNotIn('href="/torre/"', self.como(rol).get("/crm/alertas/").content.decode(), rol)

    def test_menu_marca_la_torre_como_actual_y_va_primero(self):
        html = self.como("gerencia").get("/torre/").content.decode()
        self.assertRegex(html, r'href="/torre/" class="activo" aria-current="page"')
        self.assertLess(html.index('href="/torre/"'), html.index('href="/flota/"'))


class Respuestas(Base):
    def test_pulso_json(self):
        r = self.como("gerencia").get("/torre/pulso/")
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual(r["Cache-Control"], "no-store")
        d = r.json()
        for clave in ("lectura", "rubrica", "embudo", "ahora", "generado_en", "camiones", "clientes_mapa", "frecuentes"):
            self.assertIn(clave, d)
        self.assertEqual(len(d["rubrica"]), 5)
        self.assertIsNone(d["front_back"])
        self.assertIsNone(d["pedido_trazado"])

    def test_panel_lleva_rotulo(self):
        self.assertContains(self.como("admin").get("/torre/"), ROTULO)
        self.assertEqual(ROTULO, "Clientes ilustrativos: nombres públicos usados como ejemplo; ninguno es cliente confirmado de Cofrial")

    def test_pulso_cacheado(self):
        """La vista gasta consultas en la sesión y el permiso; el cálculo de la Torre, ninguna si la caché está viva."""
        usuario = get_user_model().objects.get(username=CUENTAS["gerencia"])
        primero = servicios.pulso(usuario, "gerencia")
        with self.assertNumQueries(0):
            segundo = servicios.pulso(usuario, "gerencia")
        self.assertEqual(primero["generado_en"], segundo["generado_en"])


class Pantalla(Base):
    def test_panel_incluye_supuestos_y_datos(self):
        r = self.como("gerencia").get("/torre/")
        self.assertContains(r, "Reconstrucción ilustrativa, no son datos de Cofrial")
        self.assertContains(r, "La merma evitada se medirá con datos de Cofrial")
        self.assertContains(r, 'id="pulso-inicial"')
        self.assertContains(r, "js/torre.js")

    def test_antes_no_inventa_tasa(self):
        self.assertContains(self.como("gerencia").get("/torre/"), "alta tasa según el caso; nadie la registra")

    def test_supuestos_del_antes_llegan_al_pulso_inicial_y_cuadran(self):
        from torre import antes
        self.assertEqual(len(antes.REGISTRO), 6)
        s = antes.SUPUESTOS
        self.assertEqual((s["merma_bajo_mm"], s["merma_base_mm"], s["merma_alto_mm"]), (13.5, 22.5, 36))
        self.assertEqual(s["viajes_semana"] * s["min_coordinacion"] / 60, s["horas_semana"])
        inicial = self.como("gerencia").get("/torre/").context["inicial"]
        self.assertEqual(inicial["antes"]["supuestos"], s)
        self.assertEqual(len(inicial["antes"]["registro"]), 6)
        self.assertIn("rubrica", inicial)
